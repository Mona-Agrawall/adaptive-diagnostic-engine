import { act, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { addHistoryEntry, loadHistory } from '../lib/history';
import { apiError, deferred, ID, mockApi, question, renderApp, results, state, TOPICS } from './helpers';

const topicsOk = { 'GET /api/topics': { status: 200, body: { topics: TOPICS } } };
const answerKey = `POST /api/assessments/${ID}/answers`;
const stateKey = `GET /api/assessments/${ID}`;
const location = () => screen.getAllByTestId('location')[0]!.textContent;

describe('landing page', () => {
  it('renders the value proposition with live topic data and working links', async () => {
    mockApi(topicsOk);
    const { user } = renderApp('/');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('GRE preparation');
    expect(await screen.findByText('23 items')).toBeInTheDocument();
    await user.click(screen.getByRole('link', { name: 'Start a diagnostic' }));
    expect(location()).toBe('/start');
  });

  it('shows navigation and an accessible skip link', () => {
    mockApi(topicsOk);
    renderApp('/');
    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute('href', '#main');
    const nav = screen.getByRole('navigation', { name: 'Primary' });
    expect(within(nav).getByRole('link', { name: 'History' })).toHaveAttribute('href', '/history');
  });
});

describe('setup page', () => {
  it('validates that at least one topic is selected', async () => {
    const { calls } = mockApi(topicsOk);
    const { user } = renderApp('/start');
    await user.click(await screen.findByRole('button', { name: 'Clear all' }));
    await user.click(screen.getByRole('button', { name: 'Start assessment' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Select at least one topic.');
    expect(calls.filter((c) => c.method === 'POST')).toHaveLength(0);
  });

  it('starts an assessment with the chosen topics and length, once, and records history', async () => {
    const pending = deferred<{ status: number; body: unknown }>();
    const { calls } = mockApi({
      ...topicsOk,
      'POST /api/assessments': () => pending.promise,
      [stateKey]: { status: 200, body: state() },
    });
    const { user } = renderApp('/start');
    await user.click(await screen.findByRole('checkbox', { name: /Geometry/ }));
    await user.click(screen.getByRole('radio', { name: /Quick/ }));
    const start = screen.getByRole('button', { name: 'Start assessment' });
    await user.click(start);
    expect(screen.getByRole('button', { name: 'Starting...' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Starting...' }));
    await act(async () => pending.resolve({ status: 201, body: state() }));
    const posts = calls.filter((c) => c.method === 'POST');
    expect(posts).toHaveLength(1);
    expect(posts[0]!.body).toEqual({ topics: ['Algebra'], max_questions: 10 });
    await waitFor(() => expect(location()).toBe(`/assessment/${ID}`));
    expect(loadHistory()[0]?.id).toBe(ID);
  });

  it('shows a retryable error when topics fail to load', async () => {
    mockApi({
      'GET /api/topics': (_body, call) =>
        call === 1
          ? apiError(503, 'database_unavailable', 'The database is temporarily unavailable.')
          : topicsOk['GET /api/topics'],
    });
    const { user } = renderApp('/start');
    expect(await screen.findByText('The database is temporarily unavailable.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByRole('checkbox', { name: /Algebra/ })).toBeChecked();
  });

  it('reports server-side validation errors from creation', async () => {
    mockApi({
      ...topicsOk,
      'POST /api/assessments': apiError(422, 'unknown_topic', 'Unknown topic: Algebra'),
    });
    const { user } = renderApp('/start');
    await user.click(await screen.findByRole('button', { name: 'Start assessment' }));
    expect(await screen.findByText('Unknown topic: Algebra')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start assessment' })).toBeEnabled();
  });
});

describe('assessment page', () => {
  it('shows a loading state, then the question without answer keys or difficulty', async () => {
    const pending = deferred<{ status: number; body: unknown }>();
    mockApi({ [stateKey]: () => pending.promise });
    renderApp(`/assessment/${ID}`);
    expect(screen.getByRole('status')).toHaveTextContent('Loading your assessment');
    await act(async () => pending.resolve({ status: 200, body: state() }));
    expect(screen.getByRole('heading', { name: 'Question stem number 1?' })).toBeInTheDocument();
    expect(screen.getAllByRole('radio')).toHaveLength(4);
    expect(document.body.textContent).not.toMatch(/difficulty/i);
    expect(screen.getByRole('button', { name: 'Submit answer' })).toBeDisabled();
  });

  it('submits once even when clicked repeatedly, then shows feedback and the next question', async () => {
    const pending = deferred<{ status: number; body: unknown }>();
    const next = state({
      progress: { answered: 1, max_questions: 10, min_questions: 6 },
      current_question: question(2),
    });
    const { calls } = mockApi({
      [stateKey]: { status: 200, body: state() },
      [answerKey]: () => pending.promise,
    });
    const { user } = renderApp(`/assessment/${ID}`);
    await user.click(await screen.findByRole('radio', { name: /Two/ }));
    await user.click(screen.getByRole('button', { name: 'Submit answer' }));
    expect(screen.getByRole('button', { name: 'Submitting...' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Submitting...' }));
    await user.keyboard('{Enter}');
    await act(async () =>
      pending.resolve({
        status: 200,
        body: {
          feedback: {
            question_id: 'alg-001',
            correct: false,
            selected_index: 1,
            correct_index: 2,
            explanation: 'Because.',
          },
          assessment: next,
        },
      }),
    );
    expect(calls.filter((c) => c.method === 'POST')).toHaveLength(1);
    expect(calls.find((c) => c.method === 'POST')!.body).toEqual({ question_id: 'alg-001', option_index: 1 });
    expect(screen.getByRole('heading', { name: 'Not quite' })).toHaveFocus();
    expect(screen.getByText('Correct answer')).toBeInTheDocument();
    expect(screen.getByText('Your answer')).toBeInTheDocument();
    for (const radio of screen.getAllByRole('radio')) expect(radio).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Next question' }));
    expect(screen.getByRole('heading', { name: 'Question stem number 2?' })).toHaveFocus();
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '1');
  });

  it('goes to results after the final answer', async () => {
    const done = state({ status: 'completed', current_question: null, stop_reason: 'precision_reached' });
    mockApi({
      [stateKey]: { status: 200, body: state() },
      [answerKey]: {
        status: 200,
        body: {
          feedback: {
            question_id: 'alg-001',
            correct: true,
            selected_index: 0,
            correct_index: 0,
            explanation: 'Yes.',
          },
          assessment: done,
        },
      },
      [`GET /api/assessments/${ID}/results`]: { status: 200, body: results() },
    });
    const { user } = renderApp(`/assessment/${ID}`);
    await user.click(await screen.findByRole('radio', { name: /One/ }));
    await user.click(screen.getByRole('button', { name: 'Submit answer' }));
    await user.click(await screen.findByRole('button', { name: 'See my results' }));
    expect(location()).toBe(`/results/${ID}`);
    expect(await screen.findByRole('heading', { name: 'Your results' })).toBeInTheDocument();
  });

  it('recovers from a duplicate submission by reloading the current state', async () => {
    mockApi({
      [stateKey]: (_b, call) => ({
        status: 200,
        body: call === 1 ? state() : state({ current_question: question(2) }),
      }),
      [answerKey]: apiError(409, 'already_answered', 'This question has already been answered.'),
    });
    const { user } = renderApp(`/assessment/${ID}`);
    await user.click(await screen.findByRole('radio', { name: /One/ }));
    await user.click(screen.getByRole('button', { name: 'Submit answer' }));
    expect(await screen.findByRole('heading', { name: 'Question stem number 2?' })).toBeInTheDocument();
    expect(screen.getByText(/already recorded/)).toBeInTheDocument();
  });

  it('lets the student retry after a network failure', async () => {
    mockApi({
      [stateKey]: { status: 200, body: state() },
      [answerKey]: (_b, call) =>
        call === 1
          ? { status: 0, body: null }
          : {
              status: 200,
              body: {
                feedback: {
                  question_id: 'alg-001',
                  correct: true,
                  selected_index: 0,
                  correct_index: 0,
                  explanation: 'Ok.',
                },
                assessment: state({ current_question: question(2) }),
              },
            },
    });
    const { user } = renderApp(`/assessment/${ID}`);
    await user.click(await screen.findByRole('radio', { name: /One/ }));
    await user.click(screen.getByRole('button', { name: 'Submit answer' }));
    expect(await screen.findByText(/Could not reach the server/)).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /One/ })).toBeChecked();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByRole('heading', { name: 'Correct' })).toBeInTheDocument();
  });

  it('explains expired assessments', async () => {
    mockApi({
      [stateKey]: { status: 200, body: state() },
      [answerKey]: apiError(410, 'assessment_expired', 'Expired.'),
    });
    const { user } = renderApp(`/assessment/${ID}`);
    await user.click(await screen.findByRole('radio', { name: /One/ }));
    await user.click(screen.getByRole('button', { name: 'Submit answer' }));
    expect(await screen.findByRole('heading', { name: 'This assessment expired' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Start a new assessment' })).toHaveAttribute('href', '/start');
  });

  it('handles unknown and malformed assessment links', async () => {
    mockApi({ [stateKey]: apiError(404, 'assessment_not_found', 'Assessment not found.') });
    renderApp(`/assessment/${ID}`);
    expect(await screen.findByRole('heading', { name: 'Assessment not found' })).toBeInTheDocument();
  });

  it('does not call the API for malformed ids', () => {
    const { fetchMock } = mockApi({});
    renderApp('/assessment/../../etc');
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
    renderApp('/assessment/not-an-id');
    expect(screen.getByRole('heading', { name: 'Assessment not found' })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('results page', () => {
  const resultsKey = `GET /api/assessments/${ID}/results`;
  const planKey = `POST /api/assessments/${ID}/study-plan`;

  it('renders ability, uncertainty, topics, chart, and review', async () => {
    mockApi({ [resultsKey]: { status: 200, body: results() } });
    renderApp(`/results/${ID}`);
    expect(await screen.findByText('Proficient', { selector: '.band-label' })).toBeInTheDocument();
    expect(screen.getByText(/95% interval −0.46 to \+1.30/)).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Ability estimate \+0.42/ })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /After question 2: \+0.42/ })).toBeInTheDocument();
    expect(screen.getAllByText('Limited data')).toHaveLength(2);
    expect(screen.getByText('Provisional, uncalibrated item parameters.')).toBeInTheDocument();
    expect(screen.getByText('Stopped at the maximum number of questions you chose.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Download JSON' })).toHaveAttribute(
      'href',
      `/api/assessments/${ID}/export`,
    );
  });

  it('filters the question review', async () => {
    mockApi({ [resultsKey]: { status: 200, body: results() } });
    const { user } = renderApp(`/results/${ID}`);
    await user.click(await screen.findByRole('button', { name: 'Correct (1)' }));
    expect(screen.queryAllByText(/Solve for x/)).toHaveLength(0);
    expect(screen.getAllByText(/other acute angle/).length).toBeGreaterThan(0);
    await user.click(screen.getByRole('button', { name: 'Incorrect (1)' }));
    expect(screen.getAllByText(/Solve for x/).length).toBeGreaterThan(0);
    expect(screen.queryAllByText(/other acute angle/)).toHaveLength(0);
    expect(screen.getByRole('button', { name: 'Incorrect (1)' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('generates a study plan once, links evidence, and labels its source', async () => {
    const pending = deferred<{ status: number; body: unknown }>();
    const { calls } = mockApi({
      [resultsKey]: { status: 200, body: results() },
      [planKey]: () => pending.promise,
    });
    const { user } = renderApp(`/results/${ID}`);
    await user.click(await screen.findByRole('button', { name: 'Generate study plan' }));
    await user.click(screen.getByRole('button', { name: 'Generating plan...' }));
    await act(async () =>
      pending.resolve({
        status: 200,
        body: {
          source: 'rule_based',
          generated_at: '2026-01-01T12:20:00Z',
          summary: 'Focus on algebra fundamentals first.',
          steps: [
            {
              title: 'Close the gaps in Algebra',
              topic: 'Algebra',
              rationale: 'You missed the algebra item.',
              actions: ['Review linear equations.'],
              evidence_positions: [1],
            },
          ],
          notice: 'The AI service was unavailable, so this plan was generated from rules. You can try again.',
          model: null,
        },
      }),
    );
    expect(calls.filter((c) => c.method === 'POST')).toHaveLength(1);
    expect(screen.getByText('Rule-based')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'question 1' })).toHaveAttribute('href', '#question-1');
    expect(screen.getByRole('button', { name: 'Try AI plan again' })).toBeInTheDocument();
  });

  it('shows study plan errors without losing results', async () => {
    mockApi({
      [resultsKey]: { status: 200, body: results() },
      [planKey]: apiError(429, 'rate_limited', 'Too many requests. Please wait and try again.'),
    });
    const { user } = renderApp(`/results/${ID}`);
    await user.click(await screen.findByRole('button', { name: 'Generate study plan' }));
    expect(await screen.findByText('Too many requests. Please wait and try again.')).toBeInTheDocument();
    expect(screen.getByText('Proficient', { selector: '.band-label' })).toBeInTheDocument();
  });

  it('shows a cached AI plan without regenerating', async () => {
    const { calls } = mockApi({
      [resultsKey]: {
        status: 200,
        body: results({
          study_plan: {
            source: 'ai',
            generated_at: '2026-01-01T12:20:00Z',
            summary: 'AI summary of the results.',
            steps: [
              {
                title: 'Retest',
                topic: 'All topics',
                rationale: 'Measure progress again.',
                actions: ['Retake'],
                evidence_positions: [],
              },
            ],
            notice: null,
            model: 'openai/gpt-oss-120b',
          },
        }),
      },
    });
    renderApp(`/results/${ID}`);
    expect(await screen.findByText('AI-generated')).toBeInTheDocument();
    expect(screen.getByText(/with openai\/gpt-oss-120b/)).toBeInTheDocument();
    expect(calls.some((c) => c.method === 'POST')).toBe(false);
  });

  it('sends unfinished assessments back to the question flow', async () => {
    mockApi({ [resultsKey]: apiError(409, 'assessment_not_completed', 'Finish first.') });
    renderApp(`/results/${ID}`);
    expect(await screen.findByRole('link', { name: 'Continue the assessment' })).toHaveAttribute(
      'href',
      `/assessment/${ID}`,
    );
  });

  it('offers retry for transient failures', async () => {
    mockApi({
      [resultsKey]: (_b, call) =>
        call === 1
          ? apiError(503, 'database_unavailable', 'Database down.')
          : { status: 200, body: results() },
    });
    const { user } = renderApp(`/results/${ID}`);
    await user.click(await screen.findByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('Proficient', { selector: '.band-label' })).toBeInTheDocument();
  });
});

describe('history page', () => {
  const second = 'b'.repeat(32);

  it('shows an empty state', () => {
    mockApi({});
    renderApp('/history');
    expect(screen.getByRole('heading', { name: 'No assessments yet' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Start your first assessment' })).toHaveAttribute(
      'href',
      '/start',
    );
  });

  it('lists attempts with their status and actions', async () => {
    addHistoryEntry({ id: ID, createdAt: '2026-01-01T12:00:00Z', topics: ['Algebra'], maxQuestions: 10 });
    addHistoryEntry({
      id: second,
      createdAt: '2026-01-02T12:00:00Z',
      topics: ['Geometry'],
      maxQuestions: 10,
    });
    mockApi({
      [stateKey]: { status: 200, body: state({ status: 'completed', current_question: null }) },
      [`GET /api/assessments/${ID}/results`]: { status: 200, body: results() },
      [`GET /api/assessments/${second}`]: {
        status: 200,
        body: state({
          assessment_id: second,
          progress: { answered: 3, max_questions: 10, min_questions: 6 },
        }),
      },
    });
    renderApp('/history');
    expect(await screen.findByText('In progress')).toBeInTheDocument();
    expect(await screen.findByText('Completed')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Resume' })).toHaveAttribute('href', `/assessment/${second}`);
    expect(screen.getByRole('link', { name: 'View results' })).toHaveAttribute('href', `/results/${ID}`);
    expect(screen.getByText('3 of up to 10 answered')).toBeInTheDocument();
  });

  it('marks entries missing on the server and supports removal and confirmed clearing', async () => {
    addHistoryEntry({ id: ID, createdAt: '2026-01-01T12:00:00Z', topics: ['Algebra'], maxQuestions: 10 });
    addHistoryEntry({
      id: second,
      createdAt: '2026-01-02T12:00:00Z',
      topics: ['Geometry'],
      maxQuestions: 10,
    });
    mockApi({
      [stateKey]: apiError(404, 'assessment_not_found', 'Not found'),
      [`GET /api/assessments/${second}`]: { status: 200, body: state({ assessment_id: second }) },
    });
    const { user } = renderApp('/history');
    expect(await screen.findByText('No longer on the server')).toBeInTheDocument();
    await user.click(screen.getAllByRole('button', { name: /^Remove assessment/ })[1]!);
    expect(screen.queryByText('No longer on the server')).not.toBeInTheDocument();
    expect(loadHistory()).toHaveLength(1);

    await user.click(screen.getByRole('button', { name: 'Clear history' }));
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(loadHistory()).toHaveLength(1);
    await user.click(screen.getByRole('button', { name: 'Clear history' }));
    await user.click(screen.getByRole('button', { name: 'Remove all' }));
    expect(screen.getByRole('heading', { name: 'No assessments yet' })).toBeInTheDocument();
    expect(loadHistory()).toHaveLength(0);
  });
});
