"""Adaptive item selection and stopping rules."""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from .irt import ItemParams, item_information

RANDOMESQUE_POOL = 3


@dataclass(frozen=True, slots=True)
class Candidate:
    question_id: str
    topic: str
    params: ItemParams


class StopReason(StrEnum):
    PRECISION_REACHED = "precision_reached"
    MAX_QUESTIONS = "max_questions"
    ITEM_BANK_EXHAUSTED = "item_bank_exhausted"


def select_next_item(
    theta: float,
    candidates: Sequence[Candidate],
    administered_topics: Sequence[str],
    topics: Sequence[str],
    rng: random.Random,
) -> Candidate | None:
    """Choose the next item.

    1. Content balancing: restrict to the selected topics that have been administered the
       fewest times and still have unused items.
    2. Maximum information: rank those items by Fisher information at the current theta.
    3. Randomesque exposure control: pick uniformly among the top few, so every test-taker
       does not see the identical sequence.
    """
    if not candidates:
        return None
    counts = Counter(administered_topics)
    available_topics = {c.topic for c in candidates if c.topic in topics}
    if not available_topics:
        return None
    fewest = min(counts.get(topic, 0) for topic in available_topics)
    target_topics = {t for t in available_topics if counts.get(t, 0) == fewest}
    pool = [c for c in candidates if c.topic in target_topics]
    pool.sort(key=lambda c: (-item_information(theta, c.params), c.question_id))
    return rng.choice(pool[:RANDOMESQUE_POOL])


def stop_reason(
    answered: int,
    se: float,
    remaining_items: int,
    min_questions: int,
    max_questions: int,
    se_target: float,
) -> StopReason | None:
    if answered >= max_questions:
        return StopReason.MAX_QUESTIONS
    if answered >= min_questions and se <= se_target:
        return StopReason.PRECISION_REACHED
    if remaining_items == 0:
        return StopReason.ITEM_BANK_EXHAUSTED
    return None
