import { useEffect } from 'react';
import { Link, useParams } from 'react-router';
import { api, ASSESSMENT_ID } from '../api/client';
import type { Results } from '../api/types';
import { AbilityScale } from '../components/AbilityScale';
import { Alert, ErrorState, Loading } from '../components/Feedback';
import { QuestionReview } from '../components/QuestionReview';
import { StudyPlanPanel } from '../components/StudyPlanPanel';
import { TopicBreakdown } from '../components/TopicBreakdown';
import { TrajectoryChart } from '../components/TrajectoryChart';
import { formatDateTime, formatDuration, formatPercent, formatTheta, STOP_REASON_TEXT } from '../lib/format';
import { useApi } from '../lib/useApi';

function openAllQuestions() {
  document.querySelectorAll('details.review-item').forEach((element) => {
    (element as HTMLDetailsElement).open = true;
  });
}

function interpretation(results: Results): string {
  const { theta, ci95_low, ci95_high } = results.ability;
  const width = ci95_high - ci95_low;
  const strongest = [...results.topic_results].filter((t) => t.answered).sort((a, b) => b.theta - a.theta);
  const parts = [
    `Your answers are most consistent with an ability around ${formatTheta(theta)} on the model's ability scale, where 0 sits at the middle of the question bank's difficulty range and most estimates fall between ${formatTheta(-2)} and ${formatTheta(2)}.`,
    width > 1.6
      ? 'The interval is still wide, so a longer assessment would sharpen this estimate.'
      : 'The interval is reasonably narrow for a short diagnostic.',
  ];
  if (strongest.length > 1) {
    parts.push(`Relative strength: ${strongest[0]!.topic}. Biggest opportunity: ${strongest.at(-1)!.topic}.`);
  }
  return parts.join(' ');
}

export function ResultsPage() {
  const { id = '' } = useParams();
  const [state, reload] = useApi(
    () => (ASSESSMENT_ID.test(id) ? api.results(id) : Promise.reject(new Error('invalid'))),
    id,
  );

  useEffect(() => {
    window.addEventListener('beforeprint', openAllQuestions);
    return () => window.removeEventListener('beforeprint', openAllQuestions);
  }, []);

  if (state.status === 'loading') return <Loading label="Loading results..." />;
  if (state.status === 'error') {
    const { error } = state;
    if (error.code === 'assessment_not_completed') {
      return (
        <div className="card empty-state">
          <h1>This assessment is still in progress</h1>
          <p className="muted">Results become available once the assessment is complete.</p>
          <Link to={`/assessment/${id}`} className="button button-primary">
            Continue the assessment
          </Link>
        </div>
      );
    }
    if (
      error.status === 404 ||
      error.status === 410 ||
      error.code === 'unknown_error' ||
      error.status === 422
    ) {
      return (
        <div className="card empty-state">
          <h1>{error.status === 410 ? 'This assessment expired' : 'Results not found'}</h1>
          <p className="muted">
            {error.status === 410
              ? 'It expired before it was completed, so no results were produced.'
              : 'This link does not match a completed assessment on this server.'}
          </p>
          <Link to="/start" className="button button-primary">
            Start a new assessment
          </Link>
        </div>
      );
    }
    return <ErrorState error={error} onRetry={reload} />;
  }

  const results = state.data;
  const totalTime = results.review.reduce((sum, item) => sum + (item.time_seconds ?? 0), 0);

  return (
    <div className="stack">
      <header className="page-header" style={{ marginBottom: 0 }}>
        <span className="eyebrow">Diagnostic results</span>
        <h1>Your results</h1>
        <p className="muted" style={{ marginBottom: 4 }}>
          Completed {results.completed_at ? formatDateTime(results.completed_at) : ''} &middot;{' '}
          {results.topics.join(', ')}
        </p>
        {results.stop_reason && <p className="muted small">{STOP_REASON_TEXT[results.stop_reason]}</p>}
        <div className="button-row no-print">
          <a className="button button-secondary" href={api.exportUrl(results.assessment_id)} download>
            Download JSON
          </a>
          <button
            type="button"
            className="button button-secondary"
            onClick={() => {
              openAllQuestions();
              window.print();
            }}
          >
            Print report
          </button>
          <Link to="/start" className="button button-ghost">
            Start another assessment
          </Link>
        </div>
      </header>

      <div className="results-hero">
        <section className="card" aria-labelledby="ability-heading">
          <h2 id="ability-heading" className="eyebrow" style={{ fontFamily: 'var(--font-sans)' }}>
            Estimated level
          </h2>
          <p className="band-label">{results.ability.band}</p>
          <p className="muted">{results.ability.band_description}</p>
          <p style={{ margin: 0 }}>
            Ability estimate <strong>{formatTheta(results.ability.theta)}</strong>{' '}
            <span className="muted">
              (95% interval {formatTheta(results.ability.ci95_low)} to{' '}
              {formatTheta(results.ability.ci95_high)})
            </span>
          </p>
          <AbilityScale
            theta={results.ability.theta}
            low={results.ability.ci95_low}
            high={results.ability.ci95_high}
          />
        </section>
        <section className="card" aria-labelledby="performance-heading">
          <h2 id="performance-heading" className="eyebrow" style={{ fontFamily: 'var(--font-sans)' }}>
            Performance
          </h2>
          <div className="grid grid-4" style={{ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}>
            <div className="metric">
              <span className="metric-value">{results.answered}</span>
              <span className="metric-label">Questions answered</span>
            </div>
            <div className="metric">
              <span className="metric-value">{results.correct}</span>
              <span className="metric-label">Correct</span>
            </div>
            <div className="metric">
              <span className="metric-value">{formatPercent(results.accuracy)}</span>
              <span className="metric-label">Accuracy</span>
            </div>
            <div className="metric">
              <span className="metric-value">{formatDuration(totalTime)}</span>
              <span className="metric-label">Time spent</span>
            </div>
          </div>
          <p className="small muted" style={{ marginTop: 16, marginBottom: 0 }}>
            Accuracy alone is misleading in an adaptive test: stronger students see harder questions, so
            similar accuracy can mean very different ability.
          </p>
        </section>
      </div>

      <section className="card" aria-labelledby="meaning-heading">
        <h2 id="meaning-heading">What this means</h2>
        <p>{interpretation(results)}</p>
        <Alert tone="warning">{results.model_notice}</Alert>
      </section>

      <section className="card" aria-labelledby="topics-heading">
        <h2 id="topics-heading">By topic</h2>
        <p className="muted small">
          Topic estimates use only that topic&apos;s questions, so they are less precise than the overall
          estimate.
        </p>
        <TopicBreakdown topics={results.topic_results} />
      </section>

      <section className="card" aria-labelledby="trajectory-heading">
        <h2 id="trajectory-heading">How the estimate evolved</h2>
        <p className="muted small">
          The shaded band narrows as each answer adds evidence. Large jumps come from unexpected answers.
        </p>
        <TrajectoryChart points={results.trajectory} />
      </section>

      <StudyPlanPanel assessmentId={results.assessment_id} initial={results.study_plan} />

      <section className="card" aria-labelledby="review-heading">
        <h2 id="review-heading">Question review</h2>
        <QuestionReview items={results.review} />
      </section>
    </div>
  );
}
