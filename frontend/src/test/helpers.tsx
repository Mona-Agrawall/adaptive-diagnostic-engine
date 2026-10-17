import { render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { vi } from 'vitest';
import { App } from '../App';
import type { AssessmentState, Results, ServedQuestion, TopicInfo } from '../api/types';

export const ID = 'a'.repeat(32);

type Handler = (
  body: unknown,
  call: number,
) => { status: number; body: unknown } | Promise<{ status: number; body: unknown }>;

/** Stubs `fetch` with "METHOD /path" handlers and records every call. */
export function mockApi(handlers: Record<string, Handler | { status: number; body: unknown }>) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const counts: Record<string, number> = {};
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const method = init?.method ?? 'GET';
    const path = String(input);
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, path, body });
    const key = `${method} ${path}`;
    const handler = handlers[key];
    if (!handler) throw new Error(`Unexpected request ${key}`);
    counts[key] = (counts[key] ?? 0) + 1;
    const result = typeof handler === 'function' ? await handler(body, counts[key]) : handler;
    if (result.status === 0) throw new TypeError('Failed to fetch');
    return new Response(JSON.stringify(result.body), {
      status: result.status,
      headers: { 'Content-Type': 'application/json' },
    });
  });
  vi.stubGlobal('fetch', fetchMock);
  return { calls, fetchMock };
}

export const apiError = (status: number, code: string, message = 'Error message') => ({
  status,
  body: { error: { code, message } },
});

export function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
}

export function renderApp(path: string) {
  const user = userEvent.setup();
  const utils = render(
    <MemoryRouter initialEntries={[path]}>
      <App />
      <Routes>
        <Route path="*" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>,
  );
  return { user, ...utils };
}

export const TOPICS: TopicInfo[] = [
  { name: 'Algebra', description: 'Equations and functions.', question_count: 11 },
  { name: 'Geometry', description: 'Shapes and angles.', question_count: 12 },
];

export const question = (position: number, overrides: Partial<ServedQuestion> = {}): ServedQuestion => ({
  question_id: `alg-00${position}`,
  position,
  topic: 'Algebra',
  stem: `Question stem number ${position}?`,
  options: ['One', 'Two', 'Three', 'Four'],
  ...overrides,
});

export const state = (overrides: Partial<AssessmentState> = {}): AssessmentState => ({
  assessment_id: ID,
  status: 'active',
  topics: ['Algebra', 'Geometry'],
  progress: { answered: 0, max_questions: 10, min_questions: 6 },
  current_question: question(1),
  stop_reason: null,
  created_at: '2026-01-01T12:00:00Z',
  updated_at: '2026-01-01T12:00:00Z',
  completed_at: null,
  expires_at: '2026-01-01T14:00:00Z',
  ...overrides,
});

export const results = (overrides: Partial<Results> = {}): Results => ({
  assessment_id: ID,
  status: 'completed',
  topics: ['Algebra', 'Geometry'],
  stop_reason: 'max_questions',
  created_at: '2026-01-01T12:00:00Z',
  completed_at: '2026-01-01T12:15:00Z',
  ability: {
    theta: 0.42,
    se: 0.45,
    ci95_low: -0.46,
    ci95_high: 1.3,
    band: 'Proficient',
    band_description: 'Handles most medium-difficulty items.',
  },
  answered: 2,
  correct: 1,
  accuracy: 0.5,
  topic_results: [
    { topic: 'Algebra', answered: 1, correct: 0, accuracy: 0, theta: -0.3, se: 0.9, sufficient_data: false },
    { topic: 'Geometry', answered: 1, correct: 1, accuracy: 1, theta: 0.5, se: 0.9, sufficient_data: false },
  ],
  trajectory: [
    { position: 0, theta: 0, se: 1 },
    { position: 1, theta: -0.4, se: 0.8 },
    { position: 2, theta: 0.42, se: 0.45 },
  ],
  review: [
    {
      position: 1,
      question_id: 'alg-001',
      topic: 'Algebra',
      stem: 'Solve for x in 2x + 5 = 15?',
      options: ['3', '5', '7', '10'],
      selected_index: 0,
      correct_index: 1,
      correct: false,
      explanation: 'Subtract 5 then divide by 2.',
      tags: ['linear equations'],
      time_seconds: 12,
    },
    {
      position: 2,
      question_id: 'geo-001',
      topic: 'Geometry',
      stem: 'What is the other acute angle?',
      options: ['30', '45', '60', '90'],
      selected_index: 2,
      correct_index: 2,
      correct: true,
      explanation: 'Acute angles sum to 90.',
      tags: [],
      time_seconds: 75,
    },
  ],
  study_plan: null,
  model_notice: 'Provisional, uncalibrated item parameters.',
  ...overrides,
});

export const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
};
