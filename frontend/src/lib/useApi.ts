import { useCallback, useEffect, useState } from 'react';
import { ApiError } from '../api/client';

export type ApiState<T> =
  { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'success'; data: T };

const toApiError = (error: unknown): ApiError =>
  error instanceof ApiError ? error : new ApiError(0, 'unknown_error', 'Something went wrong.');

const LOADING = { status: 'loading' } as const;

/**
 * Runs `load` on mount and whenever `key` changes. Results are tagged with the request they
 * belong to, so a stale response can never overwrite a newer one and loading is derived.
 */
export function useApi<T>(load: () => Promise<T>, key: string): [ApiState<T>, () => void, (data: T) => void] {
  const [attempt, setAttempt] = useState(0);
  const token = `${key}#${attempt}`;
  const [stored, setStored] = useState<{ token: string; state: ApiState<T> } | null>(null);

  useEffect(() => {
    let active = true;
    load().then(
      (data) => active && setStored({ token, state: { status: 'success', data } }),
      (error: unknown) =>
        active && setStored({ token, state: { status: 'error', error: toApiError(error) } }),
    );
    return () => {
      active = false;
    };
    // `load` is keyed by `token` so callers can pass inline functions.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  const replace = useCallback((data: T) => setStored({ token, state: { status: 'success', data } }), [token]);
  return [stored?.token === token ? stored.state : LOADING, reload, replace];
}
