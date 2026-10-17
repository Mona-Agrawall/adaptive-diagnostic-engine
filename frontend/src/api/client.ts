import type { AnswerResponse, AssessmentState, Health, Results, StudyPlan, TopicInfo } from './types';

/** An error returned by the API ({"error": {"code", "message"}}) or a network failure. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }

  /** True when retrying the same request may succeed. */
  get retryable(): boolean {
    return this.status === 0 || this.status === 429 || this.status >= 500;
  }
}

const NETWORK_MESSAGE = 'Could not reach the server. Check your connection and try again.';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: { Accept: 'application/json', ...(init?.body ? { 'Content-Type': 'application/json' } : {}) },
    });
  } catch {
    throw new ApiError(0, 'network_error', NETWORK_MESSAGE);
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    const error = (body as { error?: { code?: string; message?: string } } | null)?.error;
    throw new ApiError(
      response.status,
      error?.code ?? 'http_error',
      error?.message ?? `Request failed with status ${response.status}.`,
    );
  }
  return body as T;
}

const post = <T>(path: string, payload?: unknown) =>
  request<T>(path, { method: 'POST', body: payload === undefined ? undefined : JSON.stringify(payload) });

const enc = encodeURIComponent;

export const api = {
  health: () => request<Health>('/api/health'),
  topics: () => request<{ topics: TopicInfo[] }>('/api/topics').then((body) => body.topics),
  createAssessment: (topics: string[], maxQuestions: number) =>
    post<AssessmentState>('/api/assessments', { topics, max_questions: maxQuestions }),
  getAssessment: (id: string) => request<AssessmentState>(`/api/assessments/${enc(id)}`),
  submitAnswer: (id: string, questionId: string, optionIndex: number) =>
    post<AnswerResponse>(`/api/assessments/${enc(id)}/answers`, {
      question_id: questionId,
      option_index: optionIndex,
    }),
  results: (id: string) => request<Results>(`/api/assessments/${enc(id)}/results`),
  studyPlan: (id: string) => post<StudyPlan>(`/api/assessments/${enc(id)}/study-plan`),
  exportUrl: (id: string) => `/api/assessments/${enc(id)}/export`,
};

export const ASSESSMENT_ID = /^[0-9a-f]{32}$/;
