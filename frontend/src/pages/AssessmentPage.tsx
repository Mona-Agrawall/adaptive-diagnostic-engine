import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { api, ApiError, ASSESSMENT_ID } from '../api/client';
import type { AnswerFeedback, AssessmentState, ServedQuestion } from '../api/types';
import { Alert, ErrorState, Loading, Spinner } from '../components/Feedback';
import { OPTION_LETTERS } from '../lib/format';
import { ensureHistoryEntry } from '../lib/history';

type Phase =
  | { kind: 'loading' }
  | { kind: 'error'; error: ApiError }
  | { kind: 'missing' }
  | { kind: 'expired' }
  | { kind: 'question'; state: AssessmentState }
  | { kind: 'feedback'; question: ServedQuestion; feedback: AnswerFeedback; next: AssessmentState };

const RECOVERABLE_CONFLICTS = new Set(['already_answered', 'question_not_current', 'conflict']);

const asApiError = (error: unknown) =>
  error instanceof ApiError ? error : new ApiError(0, 'unknown_error', 'Something went wrong.');

export function AssessmentPage() {
  const { id = '' } = useParams();
  if (!ASSESSMENT_ID.test(id)) return <MissingAssessment />;
  // Keyed so navigating to a different assessment starts from a clean state.
  return <AssessmentView key={id} id={id} />;
}

function MissingAssessment() {
  return (
    <div className="card empty-state">
      <h1>Assessment not found</h1>
      <p className="muted">This link does not match an assessment on this server.</p>
      <Link to="/start" className="button button-primary">
        Start a new assessment
      </Link>
    </div>
  );
}

function AssessmentView({ id }: { id: string }) {
  const navigate = useNavigate();
  const [phase, setPhase] = useState<Phase>({ kind: 'loading' });
  const [selected, setSelected] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const inFlight = useRef(false);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const feedbackRef = useRef<HTMLHeadingElement>(null);

  const showState = useCallback(
    (state: AssessmentState) => {
      setSelected(null);
      setSubmitError(null);
      if (state.status === 'completed') {
        navigate(`/results/${state.assessment_id}`, { replace: true });
      } else if (state.status === 'expired') {
        setPhase({ kind: 'expired' });
      } else {
        setPhase({ kind: 'question', state });
      }
    },
    [navigate],
  );

  const applyLoaded = useCallback(
    (state: AssessmentState) => {
      ensureHistoryEntry({
        id: state.assessment_id,
        createdAt: state.created_at,
        topics: state.topics,
        maxQuestions: state.progress.max_questions,
      });
      showState(state);
    },
    [showState],
  );

  const applyLoadError = useCallback((caught: unknown) => {
    const error = asApiError(caught);
    setPhase(error.status === 404 ? { kind: 'missing' } : { kind: 'error', error });
  }, []);

  const fetchState = useCallback(
    () => api.getAssessment(id).then(applyLoaded, applyLoadError),
    [id, applyLoaded, applyLoadError],
  );

  const reload = useCallback(() => {
    setPhase({ kind: 'loading' });
    void fetchState();
  }, [fetchState]);

  useEffect(() => {
    let active = true;
    api.getAssessment(id).then(
      (state) => active && applyLoaded(state),
      (caught: unknown) => active && applyLoadError(caught),
    );
    return () => {
      active = false;
    };
  }, [id, applyLoaded, applyLoadError]);

  // Move focus to the new content so keyboard and screen reader users follow the flow.
  useEffect(() => {
    if (phase.kind === 'question') headingRef.current?.focus();
    if (phase.kind === 'feedback') feedbackRef.current?.focus();
  }, [phase]);

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    if (phase.kind !== 'question' || selected === null || inFlight.current) return;
    const question = phase.state.current_question;
    if (!question) return;
    inFlight.current = true;
    setSubmitting(true);
    setSubmitError(null);
    setNotice(null);
    try {
      const result = await api.submitAnswer(id, question.question_id, selected);
      setPhase({ kind: 'feedback', question, feedback: result.feedback, next: result.assessment });
    } catch (caught) {
      const error = asApiError(caught);
      if (error.status === 409 && RECOVERABLE_CONFLICTS.has(error.code)) {
        setNotice(
          'That answer was already recorded, so the assessment has moved on. Continue with this question.',
        );
        setPhase({ kind: 'loading' });
        await fetchState();
      } else if (error.status === 409 && error.code === 'assessment_completed') {
        navigate(`/results/${id}`, { replace: true });
      } else if (error.status === 410) {
        setPhase({ kind: 'expired' });
      } else {
        setSubmitError(error);
      }
    } finally {
      inFlight.current = false;
      setSubmitting(false);
    }
  }

  if (phase.kind === 'loading') return <Loading label="Loading your assessment..." />;
  if (phase.kind === 'error') return <ErrorState error={phase.error} onRetry={reload} />;
  if (phase.kind === 'missing') return <MissingAssessment />;
  if (phase.kind === 'expired') {
    return (
      <div className="card empty-state">
        <h1>This assessment expired</h1>
        <p className="muted">
          Unfinished assessments expire after 2 hours without activity, so the estimate stays based on one
          sitting.
        </p>
        <Link to="/start" className="button button-primary">
          Start a new assessment
        </Link>
      </div>
    );
  }

  const isFeedback = phase.kind === 'feedback';
  const question = isFeedback ? phase.question : phase.state.current_question;
  const progressState = isFeedback ? phase.next : phase.state;
  if (!question) return <Loading label="Preparing the next question..." />;

  const answered = progressState.progress.answered;
  const max = progressState.progress.max_questions;
  const finished = isFeedback && phase.next.status !== 'active';

  return (
    <div className="assessment">
      <div className="progress-meta">
        <span>
          Question {question.position} <span className="muted">of up to {max}</span>
        </span>
        <span className="badge badge-primary">{question.topic}</span>
      </div>
      <div
        className="progress-track"
        role="progressbar"
        aria-label="Assessment progress"
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={answered}
        aria-valuetext={`${answered} of up to ${max} questions answered`}
      >
        <div className="progress-fill" style={{ width: `${(answered / max) * 100}%` }} />
      </div>

      {notice && (
        <div style={{ marginBottom: 16 }}>
          <Alert tone="info">{notice}</Alert>
        </div>
      )}

      <form className="card" onSubmit={submit} aria-busy={submitting}>
        <fieldset disabled={isFeedback || submitting}>
          <legend className="visually-hidden">Question {question.position}</legend>
          <h1 className="question-stem" tabIndex={-1} ref={headingRef}>
            {question.stem}
          </h1>
          <div className="options">
            {question.options.map((option, index) => {
              let state = '';
              if (isFeedback && index === phase.feedback.correct_index) state = 'option-correct';
              else if (isFeedback && index === phase.feedback.selected_index) state = 'option-incorrect';
              return (
                <label key={option} className={`option ${state} ${isFeedback ? 'option-locked' : ''}`}>
                  <input
                    type="radio"
                    name="answer"
                    value={index}
                    checked={isFeedback ? phase.feedback.selected_index === index : selected === index}
                    onChange={() => setSelected(index)}
                  />
                  <span className="option-letter" aria-hidden="true">
                    {OPTION_LETTERS[index]}
                  </span>
                  <span>{option}</span>
                  {state === 'option-correct' && <span className="option-status">Correct answer</span>}
                  {state === 'option-incorrect' && <span className="option-status">Your answer</span>}
                </label>
              );
            })}
          </div>
        </fieldset>

        {isFeedback && (
          <div className="feedback" aria-live="polite">
            <Alert tone={phase.feedback.correct ? 'success' : 'error'}>
              <h2 className="feedback-title" tabIndex={-1} ref={feedbackRef}>
                {phase.feedback.correct ? 'Correct' : 'Not quite'}
              </h2>
              <p>{phase.feedback.explanation}</p>
            </Alert>
          </div>
        )}

        {submitError && (
          <div className="feedback">
            <ErrorState error={submitError} onRetry={() => void submit()}>
              {!submitError.retryable && (
                <p className="small" style={{ marginTop: 6 }}>
                  <button type="button" className="button button-ghost" onClick={reload}>
                    Reload assessment
                  </button>
                </p>
              )}
            </ErrorState>
          </div>
        )}

        <div className="assessment-actions">
          <span className="muted small">Progress is saved after every answer.</span>
          {isFeedback ? (
            <button type="button" className="button button-primary" onClick={() => showState(phase.next)}>
              {finished ? 'See my results' : 'Next question'}
            </button>
          ) : (
            <button
              type="submit"
              className="button button-primary"
              disabled={selected === null || submitting}
            >
              {submitting && <Spinner />}
              {submitting ? 'Submitting...' : 'Submit answer'}
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
