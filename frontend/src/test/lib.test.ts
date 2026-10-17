import { describe, expect, it, vi } from 'vitest';
import { api, ApiError } from '../api/client';
import {
  addHistoryEntry,
  clearHistory,
  ensureHistoryEntry,
  loadHistory,
  removeHistoryEntry,
} from '../lib/history';
import { formatDuration, formatTheta } from '../lib/format';
import { describeChange } from '../pages/HistoryPage';
import { apiError, ID, mockApi, results } from './helpers';

const entry = (id: string) => ({
  id,
  createdAt: '2026-01-01T00:00:00Z',
  topics: ['Algebra'],
  maxQuestions: 10,
});

describe('api client', () => {
  it('returns parsed JSON on success', async () => {
    mockApi({ 'GET /api/topics': { status: 200, body: { topics: [] } } });
    await expect(api.topics()).resolves.toEqual([]);
  });

  it('turns the error envelope into an ApiError', async () => {
    mockApi({
      [`GET /api/assessments/${ID}`]: apiError(404, 'assessment_not_found', 'Assessment not found.'),
    });
    const error = await api.getAssessment(ID).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 404,
      code: 'assessment_not_found',
      message: 'Assessment not found.',
    });
    expect((error as ApiError).retryable).toBe(false);
  });

  it('reports network failures as retryable', async () => {
    mockApi({ 'GET /api/topics': { status: 0, body: null } });
    const error = (await api.topics().catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe('network_error');
    expect(error.retryable).toBe(true);
  });

  it('handles non-JSON error bodies', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('<html>Bad gateway</html>', { status: 502 })),
    );
    const error = (await api.topics().catch((e: unknown) => e)) as ApiError;
    expect(error).toMatchObject({ status: 502, code: 'http_error', retryable: true });
  });

  it('sends JSON bodies for answers', async () => {
    const { calls } = mockApi({ [`POST /api/assessments/${ID}/answers`]: { status: 200, body: {} } });
    await api.submitAnswer(ID, 'alg-001', 2);
    expect(calls[0]!.body).toEqual({ question_id: 'alg-001', option_index: 2 });
  });
});

describe('history store', () => {
  it('starts empty and ignores corrupt or invalid data', () => {
    expect(loadHistory()).toEqual([]);
    localStorage.setItem('ade.history.v1', '{not json');
    expect(loadHistory()).toEqual([]);
    localStorage.setItem('ade.history.v1', JSON.stringify([entry('bad-id'), entry(ID), { id: 5 }]));
    expect(loadHistory().map((e) => e.id)).toEqual([ID]);
  });

  it('adds newest first without duplicates, removes, and clears', () => {
    const second = 'b'.repeat(32);
    addHistoryEntry(entry(ID));
    addHistoryEntry(entry(second));
    ensureHistoryEntry(entry(ID));
    expect(loadHistory().map((e) => e.id)).toEqual([second, ID]);
    expect(removeHistoryEntry(second).map((e) => e.id)).toEqual([ID]);
    clearHistory();
    expect(loadHistory()).toEqual([]);
  });

  it('survives unavailable storage', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });
    expect(() => addHistoryEntry(entry(ID))).not.toThrow();
  });
});

describe('formatting and comparisons', () => {
  it('formats ability and durations', () => {
    expect(formatTheta(0.5)).toBe('+0.50');
    expect(formatTheta(-1.234)).toBe('−1.23');
    expect(formatDuration(42)).toBe('42s');
    expect(formatDuration(125)).toBe('2m 5s');
  });

  it('only reports changes larger than the combined uncertainty', () => {
    const at = (theta: number, se = 0.3) => results({ ability: { ...results().ability, theta, se } });
    expect(describeChange(at(0.5), undefined)).toBeNull();
    expect(describeChange(at(0.5), at(0.3))?.className).toBe('muted');
    expect(describeChange(at(1.8), at(0.2))).toMatchObject({
      className: 'delta-up',
      text: 'up 1.60 from previous',
    });
    expect(describeChange(at(-1.5), at(0.5))?.className).toBe('delta-down');
  });
});
