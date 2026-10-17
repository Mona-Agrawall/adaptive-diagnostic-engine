import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router';
import { api, ApiError } from '../api/client';
import { Alert, ErrorState, Loading, Spinner } from '../components/Feedback';
import { addHistoryEntry } from '../lib/history';
import { useApi } from '../lib/useApi';

const LENGTHS = [
  { value: 10, title: 'Quick', detail: '10 questions, about 10 minutes' },
  { value: 15, title: 'Standard', detail: '15 questions, about 15 minutes' },
  { value: 20, title: 'Extended', detail: '20 questions, the most precise estimate' },
];

export function SetupPage() {
  const navigate = useNavigate();
  const [topics, reloadTopics] = useApi(api.topics, 'topics');
  const [selected, setSelected] = useState<string[] | null>(null);
  const [length, setLength] = useState(15);
  const [validation, setValidation] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  if (topics.status === 'loading') return <Loading label="Loading topics..." />;
  if (topics.status === 'error') return <ErrorState error={topics.error} onRetry={reloadTopics} />;

  const allNames = topics.data.map((topic) => topic.name);
  const chosen = selected ?? allNames;
  const available = topics.data
    .filter((t) => chosen.includes(t.name))
    .reduce((n, t) => n + t.question_count, 0);

  function toggle(name: string) {
    setValidation(null);
    setSelected(chosen.includes(name) ? chosen.filter((t) => t !== name) : [...chosen, name]);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting) return;
    if (chosen.length === 0) {
      setValidation('Select at least one topic.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const state = await api.createAssessment(chosen, length);
      addHistoryEntry({
        id: state.assessment_id,
        createdAt: state.created_at,
        topics: state.topics,
        maxQuestions: state.progress.max_questions,
      });
      navigate(`/assessment/${state.assessment_id}`);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught : new ApiError(0, 'unknown_error', 'Something went wrong.'),
      );
      setSubmitting(false);
    }
  }

  return (
    <div style={{ maxWidth: 860 }}>
      <header className="page-header">
        <span className="eyebrow">New assessment</span>
        <h1>Set up your diagnostic</h1>
        <p className="lead">Pick the areas you want measured and how long the assessment should be.</p>
      </header>

      <form onSubmit={onSubmit} noValidate className="stack">
        <fieldset aria-describedby={validation ? 'topic-error' : undefined}>
          <legend>Topics</legend>
          <div className="button-row" style={{ justifyContent: 'space-between' }}>
            <span className="muted small">
              {chosen.length} of {allNames.length} selected
            </span>
            <button
              type="button"
              className="button button-ghost"
              onClick={() => {
                setValidation(null);
                setSelected(chosen.length === allNames.length ? [] : allNames);
              }}
            >
              {chosen.length === allNames.length ? 'Clear all' : 'Select all'}
            </button>
          </div>
          <div className="choice-grid">
            {topics.data.map((topic) => (
              <label key={topic.name} className="choice">
                <input
                  type="checkbox"
                  name="topics"
                  value={topic.name}
                  checked={chosen.includes(topic.name)}
                  onChange={() => toggle(topic.name)}
                />
                <span>
                  <span className="choice-title">{topic.name}</span>
                  <span className="choice-detail">{topic.description}</span>
                  <span className="choice-detail">{topic.question_count} questions in the bank</span>
                </span>
              </label>
            ))}
          </div>
          {validation && (
            <p id="topic-error" className="field-error" role="alert">
              {validation}
            </p>
          )}
        </fieldset>

        <fieldset>
          <legend>Maximum length</legend>
          <div className="choice-grid">
            {LENGTHS.map((option) => (
              <label key={option.value} className="choice">
                <input
                  type="radio"
                  name="length"
                  value={option.value}
                  checked={length === option.value}
                  onChange={() => setLength(option.value)}
                />
                <span>
                  <span className="choice-title">{option.title}</span>
                  <span className="choice-detail">{option.detail}</span>
                </span>
              </label>
            ))}
          </div>
          {chosen.length > 0 && available < length && (
            <p className="muted small" style={{ marginTop: 8 }}>
              The selected topics contain {available} questions, so the assessment will end after at most{' '}
              {available}.
            </p>
          )}
        </fieldset>

        <Alert tone="info" title="Before you begin">
          <ul style={{ margin: '4px 0 0', paddingLeft: 20 }}>
            <li>You will see whether each answer was right, with an explanation, before moving on.</li>
            <li>The test may end early once your estimate is precise enough (after at least 6 questions).</li>
            <li>There is no time limit. Unfinished assessments expire after 2 hours without activity.</li>
            <li>Answers cannot be changed after you submit them.</li>
          </ul>
        </Alert>

        {error && <ErrorState error={error} />}

        <div className="button-row">
          <button type="submit" className="button button-primary button-large" disabled={submitting}>
            {submitting && <Spinner />}
            {submitting ? 'Starting...' : 'Start assessment'}
          </button>
        </div>
      </form>
    </div>
  );
}
