import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { api, ApiError } from '../api/client';
import type { AssessmentState, Results } from '../api/types';
import { Alert, Loading } from '../components/Feedback';
import { formatDateTime, formatPercent, formatTheta } from '../lib/format';
import { clearHistory, loadHistory, removeHistoryEntry, type HistoryEntry } from '../lib/history';

type Row =
  | { entry: HistoryEntry; kind: 'loading' }
  | { entry: HistoryEntry; kind: 'missing' }
  | { entry: HistoryEntry; kind: 'error'; message: string }
  | { entry: HistoryEntry; kind: 'state'; state: AssessmentState; results: Results | null };

async function loadRow(entry: HistoryEntry): Promise<Row> {
  try {
    const state = await api.getAssessment(entry.id);
    const results = state.status === 'completed' ? await api.results(entry.id) : null;
    return { entry, kind: 'state', state, results };
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 404) return { entry, kind: 'missing' };
    return { entry, kind: 'error', message: caught instanceof ApiError ? caught.message : 'Could not load.' };
  }
}

/**
 * Compare with the previous completed attempt. A change only counts as real when it exceeds the
 * combined 95% uncertainty of both estimates; otherwise it is reported as no clear change.
 */
export function describeChange(current: Results, before: Results | undefined) {
  if (!before) return null;
  const delta = current.ability.theta - before.ability.theta;
  const margin = 1.96 * Math.hypot(current.ability.se, before.ability.se);
  if (Math.abs(delta) < margin) {
    return {
      text: `no clear change from previous, ${formatTheta(delta)} is within the margin of error`,
      className: 'muted',
    };
  }
  return delta > 0
    ? { text: `up ${delta.toFixed(2)} from previous`, className: 'delta-up' }
    : { text: `down ${Math.abs(delta).toFixed(2)} from previous`, className: 'delta-down' };
}

function StatusBadge({ row }: { row: Row }) {
  if (row.kind === 'missing') return <span className="badge">Unavailable</span>;
  if (row.kind === 'error') return <span className="badge badge-danger">Error</span>;
  if (row.kind === 'loading') return <span className="badge">Loading</span>;
  const map = {
    completed: ['badge-success', 'Completed'],
    active: ['badge-primary', 'In progress'],
    expired: ['', 'Expired'],
  } as const;
  const [tone, label] = map[row.state.status];
  return <span className={`badge ${tone}`}>{label}</span>;
}

export function HistoryPage() {
  const [entries, setEntries] = useState<HistoryEntry[]>(() => loadHistory());
  const [rows, setRows] = useState<Record<string, Row>>({});
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    let active = true;
    for (const entry of entries) {
      if (rows[entry.id]) continue;
      void loadRow(entry).then((row) => active && setRows((current) => ({ ...current, [entry.id]: row })));
    }
    return () => {
      active = false;
    };
  }, [entries, rows]);

  if (entries.length === 0) {
    return (
      <div className="card empty-state">
        <h1>No assessments yet</h1>
        <p className="muted">
          Assessments you start in this browser appear here so you can resume them or compare results.
        </p>
        <Link to="/start" className="button button-primary">
          Start your first assessment
        </Link>
      </div>
    );
  }

  const completed = entries
    .map((entry) => rows[entry.id])
    .filter((row): row is Extract<Row, { kind: 'state' }> => row?.kind === 'state' && row.results !== null)
    .reverse(); // oldest first
  const previous = new Map<string, Results>();
  completed.forEach((row, index) => {
    const before = completed[index - 1];
    if (before?.results) previous.set(row.entry.id, before.results);
  });

  return (
    <div className="stack">
      <header className="page-header" style={{ marginBottom: 0 }}>
        <span className="eyebrow">Your attempts</span>
        <h1>Assessment history</h1>
        <p className="lead">
          Resume unfinished assessments and see how your estimate changes between attempts.
        </p>
      </header>

      <Alert tone="info" title="Where this history is stored">
        This list is kept in this browser only; there are no accounts. Anyone with an assessment link can open
        its results, so share links only with people you trust. Removing an entry here does not delete it from
        the server.
      </Alert>

      <section className="card">
        <div className="table-scroll">
          <table className="history-table">
            <caption className="visually-hidden">Assessments started in this browser, newest first</caption>
            <thead>
              <tr>
                <th scope="col">Started</th>
                <th scope="col">Topics</th>
                <th scope="col">Status</th>
                <th scope="col">Result</th>
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => {
                const row: Row = rows[entry.id] ?? { entry, kind: 'loading' };
                const results = row.kind === 'state' ? row.results : null;
                const change = results ? describeChange(results, previous.get(entry.id)) : null;
                return (
                  <tr key={entry.id}>
                    <td>{formatDateTime(entry.createdAt)}</td>
                    <td>{entry.topics.join(', ')}</td>
                    <td>
                      <StatusBadge row={row} />
                    </td>
                    <td>
                      {results ? (
                        <>
                          <strong>{results.ability.band}</strong> {formatTheta(results.ability.theta)}
                          <span className="muted small">
                            {' '}
                            &middot; {formatPercent(results.accuracy)} correct
                          </span>
                          {change && <span className={`small ${change.className}`}> ({change.text})</span>}
                        </>
                      ) : row.kind === 'loading' ? (
                        <span className="muted">Loading...</span>
                      ) : row.kind === 'error' ? (
                        <span className="muted">{row.message}</span>
                      ) : row.kind === 'missing' ? (
                        <span className="muted">No longer on the server</span>
                      ) : (
                        <span className="muted">
                          {row.state.progress.answered} of up to {row.state.progress.max_questions} answered
                        </span>
                      )}
                    </td>
                    <td>
                      <div className="button-row" style={{ justifyContent: 'flex-end', flexWrap: 'nowrap' }}>
                        {row.kind === 'state' && row.state.status === 'completed' && (
                          <Link className="button button-secondary" to={`/results/${entry.id}`}>
                            View results
                          </Link>
                        )}
                        {row.kind === 'state' && row.state.status === 'active' && (
                          <Link className="button button-primary" to={`/assessment/${entry.id}`}>
                            Resume
                          </Link>
                        )}
                        <button
                          type="button"
                          className="button button-ghost"
                          aria-label={`Remove assessment started ${formatDateTime(entry.createdAt)} from history`}
                          onClick={() => setEntries(removeHistoryEntry(entry.id))}
                        >
                          Remove
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {Object.keys(rows).length < entries.length && <Loading label="Checking assessment status..." />}
      </section>

      <div className="no-print">
        {confirming ? (
          <Alert
            tone="warning"
            title={`Remove all ${entries.length} entries from this browser?`}
            action={
              <div className="button-row">
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => setConfirming(false)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="button button-danger"
                  onClick={() => {
                    clearHistory();
                    setEntries([]);
                    setConfirming(false);
                  }}
                >
                  Remove all
                </button>
              </div>
            }
          >
            Results stay on the server, but you will need the original links to reopen them.
          </Alert>
        ) : (
          <button type="button" className="button button-secondary" onClick={() => setConfirming(true)}>
            Clear history
          </button>
        )}
      </div>
    </div>
  );
}
