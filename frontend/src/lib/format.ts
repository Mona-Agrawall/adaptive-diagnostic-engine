import type { StopReason } from '../api/types';

export const formatTheta = (theta: number): string =>
  `${theta >= 0 ? '+' : '\u2212'}${Math.abs(theta).toFixed(2)}`;

export const formatPercent = (fraction: number): string => `${Math.round(fraction * 100)}%`;

export const formatDateTime = (iso: string): string =>
  new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });

export const formatDuration = (seconds: number): string => {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${Math.round(seconds % 60)}s`;
};

export const STOP_REASON_TEXT: Record<StopReason, string> = {
  precision_reached: 'Stopped early: the estimate reached the target precision.',
  max_questions: 'Stopped at the maximum number of questions you chose.',
  item_bank_exhausted: 'Stopped because every available question in your topics was used.',
};

export const OPTION_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F'];
