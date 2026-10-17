import { useEffect, useState } from 'react';
import { flushSync } from 'react-dom';
import type { ReviewItem } from '../api/types';
import { formatDuration, OPTION_LETTERS } from '../lib/format';

type Filter = 'all' | 'incorrect' | 'correct';

const QUESTION_HASH = /^#question-\d+$/;

function revealQuestion(hash: string) {
  const element = document.getElementById(hash.slice(1));
  if (element instanceof HTMLDetailsElement) {
    element.open = true;
    element.scrollIntoView?.({ block: 'start' });
    element.querySelector('summary')?.focus();
  }
}

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'incorrect', label: 'Incorrect' },
  { value: 'correct', label: 'Correct' },
];

/** Every administered question with the student's answer, the key, and the explanation. */
export function QuestionReview({ items }: { items: ReviewItem[] }) {
  const [filter, setFilter] = useState<Filter>('all');

  // Links such as "#question-3" (from the study plan) reveal and open the referenced question,
  // even if the current filter hides it.
  useEffect(() => {
    const onHash = () => {
      const hash = window.location.hash;
      if (!QUESTION_HASH.test(hash)) return;
      flushSync(() => setFilter('all'));
      revealQuestion(hash);
    };
    if (QUESTION_HASH.test(window.location.hash)) revealQuestion(window.location.hash);
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const visible = items.filter((item) => filter === 'all' || (filter === 'correct') === item.correct);
  const counts = {
    all: items.length,
    correct: items.filter((item) => item.correct).length,
    incorrect: items.filter((item) => !item.correct).length,
  };

  return (
    <div>
      <div className="tabs no-print" role="group" aria-label="Filter questions">
        {FILTERS.map(({ value, label }) => (
          <button key={value} type="button" aria-pressed={filter === value} onClick={() => setFilter(value)}>
            {label} ({counts[value]})
          </button>
        ))}
      </div>
      <div className="review-list" style={{ marginTop: 16 }}>
        {visible.length === 0 && <p className="muted">No questions match this filter.</p>}
        {visible.map((item) => (
          <details key={item.question_id} className="review-item" id={`question-${item.position}`}>
            <summary>
              <span className={`badge ${item.correct ? 'badge-success' : 'badge-danger'}`}>
                {item.correct ? 'Correct' : 'Incorrect'}
              </span>
              <span className="review-summary-text">
                <strong>Q{item.position}.</strong> {item.stem}
              </span>
            </summary>
            <div className="review-body">
              <p className="muted small" style={{ margin: '0 0 8px' }}>
                {item.topic}
                {item.tags.length > 0 && <> &middot; {item.tags.join(', ')}</>}
                {item.time_seconds !== null && <> &middot; answered in {formatDuration(item.time_seconds)}</>}
              </p>
              <p style={{ fontWeight: 500 }}>{item.stem}</p>
              <ol aria-label="Options">
                {item.options.map((option, index) => {
                  const isKey = index === item.correct_index;
                  const isPick = index === item.selected_index;
                  return (
                    <li key={option} className={isKey ? 'is-correct' : isPick ? 'is-wrong' : undefined}>
                      <strong>{OPTION_LETTERS[index]}.</strong> {option}
                      {isKey && <strong> (correct answer)</strong>}
                      {isPick && !isKey && <strong> (your answer)</strong>}
                      {isPick && isKey && <strong> (your answer)</strong>}
                    </li>
                  );
                })}
              </ol>
              <p style={{ margin: '12px 0 0' }}>
                <strong>Explanation:</strong> {item.explanation}
              </p>
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}
