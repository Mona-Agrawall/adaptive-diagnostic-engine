import type { ReactNode } from 'react';
import type { ApiError } from '../api/client';

type Tone = 'error' | 'info' | 'warning' | 'success';

export function Alert({
  tone,
  title,
  children,
  action,
}: {
  tone: Tone;
  title?: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className={`alert alert-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <div className="alert-body">
        {title && <p className="alert-title">{title}</p>}
        {children && <div>{children}</div>}
      </div>
      {action}
    </div>
  );
}

export function Loading({ label }: { label: string }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function Spinner() {
  return <span className="spinner" aria-hidden="true" />;
}

export function ErrorState({
  error,
  onRetry,
  children,
}: {
  error: ApiError;
  onRetry?: () => void;
  children?: ReactNode;
}) {
  return (
    <Alert
      tone="error"
      title={error.status === 0 ? 'Connection problem' : 'Something went wrong'}
      action={
        onRetry && error.retryable ? (
          <button type="button" className="button button-secondary" onClick={onRetry}>
            Try again
          </button>
        ) : undefined
      }
    >
      <p>{error.message}</p>
      {children}
    </Alert>
  );
}
