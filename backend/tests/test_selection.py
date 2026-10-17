from __future__ import annotations

import random

import pytest

from app.irt import ItemParams, item_information
from app.selection import Candidate, StopReason, select_next_item, stop_reason


def _pool() -> list[Candidate]:
    return [
        Candidate(f"alg-00{i}", "Algebra", ItemParams(1.2, b)) for i, b in enumerate([-2.0, -1.0, 0.0, 1.0, 2.0])
    ] + [Candidate(f"geo-00{i}", "Geometry", ItemParams(1.2, b)) for i, b in enumerate([-1.5, 0.2, 1.5])]


def test_returns_none_without_candidates() -> None:
    assert select_next_item(0.0, [], [], ["Algebra"], random.Random(1)) is None


def test_ignores_topics_outside_the_assessment() -> None:
    pool = [Candidate("geo-001", "Geometry", ItemParams(1.0, 0.0))]
    assert select_next_item(0.0, pool, [], ["Algebra"], random.Random(1)) is None


def test_content_balancing_prefers_least_administered_topic() -> None:
    for seed in range(20):
        chosen = select_next_item(0.0, _pool(), ["Algebra", "Algebra"], ["Algebra", "Geometry"], random.Random(seed))
        assert chosen is not None and chosen.topic == "Geometry"


def test_topic_balance_falls_back_when_a_topic_is_exhausted() -> None:
    algebra_only = [c for c in _pool() if c.topic == "Algebra"]
    chosen = select_next_item(0.0, algebra_only, ["Algebra"] * 3, ["Algebra", "Geometry"], random.Random(1))
    assert chosen is not None and chosen.topic == "Algebra"


@pytest.mark.parametrize("theta", [-2.0, -0.5, 0.0, 1.0, 2.0])
def test_selects_among_the_most_informative_items(theta: float) -> None:
    pool = [c for c in _pool() if c.topic == "Algebra"]
    ranked = sorted(pool, key=lambda c: -item_information(theta, c.params))
    top_three = {c.question_id for c in ranked[:3]}
    seen = {select_next_item(theta, pool, [], ["Algebra"], random.Random(seed)).question_id for seed in range(50)}  # type: ignore[union-attr]
    assert seen <= top_three
    assert ranked[0].question_id in seen


def test_harder_items_follow_higher_ability() -> None:
    pool = [c for c in _pool() if c.topic == "Algebra"]
    low = [select_next_item(-2.0, pool, [], ["Algebra"], random.Random(s)).params.b for s in range(30)]  # type: ignore[union-attr]
    high = [select_next_item(2.0, pool, [], ["Algebra"], random.Random(s)).params.b for s in range(30)]  # type: ignore[union-attr]
    assert sum(high) / len(high) > sum(low) / len(low) + 1.5


@pytest.mark.parametrize(
    ("answered", "se", "remaining", "expected"),
    [
        (15, 0.9, 10, StopReason.MAX_QUESTIONS),
        (6, 0.39, 10, StopReason.PRECISION_REACHED),
        (5, 0.30, 10, None),  # below the minimum, precision alone cannot stop
        (7, 0.55, 10, None),
        (7, 0.55, 0, StopReason.ITEM_BANK_EXHAUSTED),
    ],
)
def test_stop_rules(answered: int, se: float, remaining: int, expected: StopReason | None) -> None:
    assert stop_reason(answered, se, remaining, min_questions=6, max_questions=15, se_target=0.4) == expected
