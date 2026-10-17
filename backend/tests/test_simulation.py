"""Monte Carlo checks: simulated students answer the real item bank under the 2PL model.

The thresholds are deliberately modest. They verify that the engine recovers the ordering and
rough magnitude of ability, not that this small, uncalibrated bank is psychometrically precise.
"""

from __future__ import annotations

import random
import statistics

import pytest

from app.irt import Response, estimate_ability, probability_correct
from app.question_bank import load_bank
from app.selection import Candidate, select_next_item, stop_reason

BANK = load_bank()
TOPICS = list(BANK.topics)
CANDIDATES = [Candidate(q.question_id, q.topic, q.params) for q in BANK.questions]


def simulate(true_theta: float, rng: random.Random, max_questions: int = 20) -> tuple[float, float, int]:
    remaining = list(CANDIDATES)
    responses: list[Response] = []
    topics_seen: list[str] = []
    theta, se = 0.0, 1.0
    while True:
        item = select_next_item(theta, remaining, topics_seen, TOPICS, rng)
        if item is None:
            break
        remaining.remove(item)
        topics_seen.append(item.topic)
        responses.append(Response(item.params, rng.random() < probability_correct(true_theta, item.params)))
        estimate = estimate_ability(responses)
        theta, se = estimate.theta, estimate.se
        if stop_reason(len(responses), se, len(remaining), 6, max_questions, 0.4):
            break
    return theta, se, len(responses)


@pytest.mark.simulation
def test_estimates_recover_ability_ordering_and_magnitude() -> None:
    rng = random.Random(2026)
    true_levels = [-2.0, -1.0, 0.0, 1.0, 2.0]
    means = []
    errors = []
    pairs: list[tuple[float, float]] = []
    for level in true_levels:
        estimates = [simulate(level, rng)[0] for _ in range(80)]
        means.append(statistics.fmean(estimates))
        errors.extend(est - level for est in estimates)
        pairs.extend((level, est) for est in estimates)
    assert means == sorted(means), f"mean estimates must increase with true ability: {means}"
    assert means[-1] - means[0] > 2.5
    rmse = statistics.fmean(e * e for e in errors) ** 0.5
    assert rmse < 0.8, f"RMSE too high: {rmse:.3f}"
    correlation = statistics.correlation([p[0] for p in pairs], [p[1] for p in pairs])
    assert correlation > 0.85, f"correlation too low: {correlation:.3f}"


@pytest.mark.simulation
def test_reported_uncertainty_is_roughly_calibrated() -> None:
    rng = random.Random(99)
    covered = 0
    runs = 300
    for _ in range(runs):
        true_theta = rng.gauss(0, 1)
        theta, se, _ = simulate(true_theta, rng)
        covered += abs(theta - true_theta) <= 1.96 * se
    # Nominal 95%; allow slack for prior shrinkage and Monte Carlo noise.
    assert covered / runs > 0.85


@pytest.mark.simulation
def test_each_simulated_test_covers_every_topic_and_never_repeats() -> None:
    rng = random.Random(5)
    remaining = list(CANDIDATES)
    topics_seen: list[str] = []
    picked: list[str] = []
    for _ in range(10):
        item = select_next_item(0.0, remaining, topics_seen, TOPICS, rng)
        assert item is not None
        remaining.remove(item)
        topics_seen.append(item.topic)
        picked.append(item.question_id)
    assert len(set(picked)) == len(picked)
    assert {topic: topics_seen.count(topic) for topic in TOPICS} == dict.fromkeys(TOPICS, 2)


@pytest.mark.simulation
def test_extreme_students_produce_bounded_estimates() -> None:
    rng = random.Random(1)
    high = [simulate(6.0, rng)[0] for _ in range(20)]
    low = [simulate(-6.0, rng)[0] for _ in range(20)]
    assert min(high) > 1.0 and max(high) < 4.0
    assert max(low) < -1.0 and min(low) > -4.0
