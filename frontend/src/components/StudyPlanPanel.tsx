import { useRef, useState } from 'react';
import { api, ApiError } from '../api/client';
import type { StudyPlan } from '../api/types';
import { formatDateTime } from '../lib/format';
import { Alert, ErrorState, Spinner } from './Feedback';

const AI_RETRYABLE = 'You can try again.';

export function StudyPlanPanel({
  assessmentId,
  initial,
}: {
  assessmentId: string;
  initial: StudyPlan | null;
}) {
  const [plan, setPlan] = useState<StudyPlan | null>(initial);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const inFlight = useRef(false);

  async function generate() {
    if (inFlight.current) return;
    inFlight.current = true;
    setPending(true);
    setError(null);
    try {
      setPlan(await api.studyPlan(assessmentId));
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught : new ApiError(0, 'unknown_error', 'Something went wrong.'),
      );
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }

  const canRetryAi = plan?.source === 'rule_based' && plan.notice?.endsWith(AI_RETRYABLE);

  return (
    <section className="card" aria-labelledby="plan-heading" aria-busy={pending}>
      <div className="section-title">
        <h2 id="plan-heading">Study plan</h2>
        {plan && (
          <span className={`badge ${plan.source === 'ai' ? 'badge-primary' : ''}`}>
            {plan.source === 'ai' ? 'AI-generated' : 'Rule-based'}
          </span>
        )}
      </div>

      {!plan && (
        <>
          <p className="muted">
            Turn these results into concrete next steps. Each recommendation links back to the questions that
            motivated it. If the AI service is unavailable, a rule-based plan is produced from the same data.
          </p>
          <button
            type="button"
            className="button button-primary no-print"
            onClick={generate}
            disabled={pending}
          >
            {pending && <Spinner />}
            {pending ? 'Generating plan...' : 'Generate study plan'}
          </button>
        </>
      )}

      {error && (
        <div style={{ marginTop: 16 }}>
          <ErrorState error={error} onRetry={generate} />
        </div>
      )}

      {plan && (
        <div className="stack">
          {plan.notice && <Alert tone="info">{plan.notice}</Alert>}
          <p>{plan.summary}</p>
          <ol className="stack" style={{ listStyle: 'none', padding: 0 }}>
            {plan.steps.map((step, index) => (
              <li key={`${step.title}-${index}`} className="plan-step">
                <h3>
                  {index + 1}. {step.title}
                </h3>
                <p className="muted small" style={{ margin: 0 }}>
                  {step.topic}
                </p>
                <p style={{ margin: '6px 0 0' }}>{step.rationale}</p>
                <ul>
                  {step.actions.map((action) => (
                    <li key={action}>{action}</li>
                  ))}
                </ul>
                {step.evidence_positions.length > 0 && (
                  <p className="small" style={{ margin: '8px 0 0' }}>
                    Based on{' '}
                    {step.evidence_positions.map((position, i) => (
                      <span key={position}>
                        {i > 0 && ', '}
                        <a href={`#question-${position}`}>question {position}</a>
                      </span>
                    ))}
                  </p>
                )}
              </li>
            ))}
          </ol>
          <div className="button-row">
            <span className="muted small">
              Generated {formatDateTime(plan.generated_at)}
              {plan.model ? ` with ${plan.model}` : ''}. AI suggestions never change your scores.
            </span>
            {canRetryAi && (
              <button
                type="button"
                className="button button-secondary no-print"
                onClick={generate}
                disabled={pending}
              >
                {pending && <Spinner />}
                Try AI plan again
              </button>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
