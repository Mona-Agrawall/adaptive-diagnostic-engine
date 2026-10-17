// Assessment history lives in this browser only. The server has no user accounts, so it never
// lists assessments; each entry is just an assessment ID this browser created.

import { ASSESSMENT_ID } from '../api/client';

export interface HistoryEntry {
  id: string;
  createdAt: string;
  topics: string[];
  maxQuestions: number;
}

const KEY = 'ade.history.v1';
const MAX_ENTRIES = 50;

function isEntry(value: unknown): value is HistoryEntry {
  const entry = value as HistoryEntry;
  return (
    typeof entry === 'object' &&
    entry !== null &&
    typeof entry.id === 'string' &&
    ASSESSMENT_ID.test(entry.id) &&
    typeof entry.createdAt === 'string' &&
    Array.isArray(entry.topics) &&
    entry.topics.every((topic) => typeof topic === 'string') &&
    typeof entry.maxQuestions === 'number'
  );
}

export function loadHistory(): HistoryEntry[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(KEY) ?? '[]');
    return Array.isArray(parsed) ? parsed.filter(isEntry) : [];
  } catch {
    return [];
  }
}

function save(entries: HistoryEntry[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(entries.slice(0, MAX_ENTRIES)));
  } catch {
    // Storage can be unavailable (private mode, quota); history is a convenience only.
  }
}

export function addHistoryEntry(entry: HistoryEntry): void {
  save([entry, ...loadHistory().filter((existing) => existing.id !== entry.id)]);
}

/** Adds the entry only if it is not already recorded, preserving the existing order. */
export function ensureHistoryEntry(entry: HistoryEntry): void {
  if (!loadHistory().some((existing) => existing.id === entry.id)) addHistoryEntry(entry);
}

export function removeHistoryEntry(id: string): HistoryEntry[] {
  const next = loadHistory().filter((entry) => entry.id !== id);
  save(next);
  return next;
}

export function clearHistory(): void {
  save([]);
}
