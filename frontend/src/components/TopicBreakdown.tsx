import type { TopicResult } from '../api/types';
import { formatPercent, formatTheta } from '../lib/format';

/** Per-topic accuracy and ability estimate, flagging topics with too few items to trust. */
export function TopicBreakdown({ topics }: { topics: TopicResult[] }) {
  const ranked = [...topics].sort((a, b) => b.theta - a.theta);
  return (
    <div className="table-scroll">
      <table className="topic-table">
        <caption className="visually-hidden">Results by topic, strongest first</caption>
        <thead>
          <tr>
            <th scope="col">Topic</th>
            <th scope="col">Correct</th>
            <th scope="col">Accuracy</th>
            <th scope="col">Topic estimate</th>
          </tr>
        </thead>
        <tbody>
          {ranked.map((topic) => (
            <tr key={topic.topic}>
              <th scope="row" style={{ fontWeight: 600 }}>
                {topic.topic}
                {!topic.sufficient_data && (
                  <>
                    {' '}
                    <span className="badge badge-warning" title="Fewer than 3 questions: treat as tentative">
                      Limited data
                    </span>
                  </>
                )}
              </th>
              <td>
                {topic.correct} / {topic.answered}
              </td>
              <td>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div className="bar" style={{ flex: 1 }} aria-hidden="true">
                    <div className="bar-fill" style={{ width: formatPercent(topic.accuracy) }} />
                  </div>
                  <span>{topic.answered ? formatPercent(topic.accuracy) : 'n/a'}</span>
                </div>
              </td>
              <td>
                {topic.answered ? (
                  <>
                    {formatTheta(topic.theta)}{' '}
                    <span className="muted small">&plusmn; {(1.96 * topic.se).toFixed(2)}</span>
                  </>
                ) : (
                  <span className="muted">Not assessed</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
