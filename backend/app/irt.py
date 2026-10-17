"""Two-parameter logistic (2PL) item response theory utilities.

Ability (theta) is on the standard logit scale. Estimation uses expected a posteriori (EAP)
with a standard normal prior, evaluated on a fixed quadrature grid. The prior keeps estimates
finite for all-correct and all-incorrect response patterns, and the grid bounds the result.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

THETA_MIN = -4.0
THETA_MAX = 4.0
GRID_STEP = 0.05
GRID: tuple[float, ...] = tuple(
    round(THETA_MIN + i * GRID_STEP, 10) for i in range(round((THETA_MAX - THETA_MIN) / GRID_STEP) + 1)
)

A_MIN, A_MAX = 0.2, 3.0
B_MIN, B_MAX = -3.5, 3.5

PRIOR_MEAN = 0.0
PRIOR_SD = 1.0


@dataclass(frozen=True, slots=True)
class ItemParams:
    a: float  # discrimination
    b: float  # difficulty

    def __post_init__(self) -> None:
        if not (math.isfinite(self.a) and A_MIN <= self.a <= A_MAX):
            raise ValueError(f"discrimination a={self.a} outside [{A_MIN}, {A_MAX}]")
        if not (math.isfinite(self.b) and B_MIN <= self.b <= B_MAX):
            raise ValueError(f"difficulty b={self.b} outside [{B_MIN}, {B_MAX}]")


@dataclass(frozen=True, slots=True)
class Response:
    item: ItemParams
    correct: bool


@dataclass(frozen=True, slots=True)
class AbilityEstimate:
    theta: float
    se: float

    @property
    def ci95(self) -> tuple[float, float]:
        low = max(THETA_MIN, self.theta - 1.96 * self.se)
        high = min(THETA_MAX, self.theta + 1.96 * self.se)
        return low, high


def _log_sigmoid(z: float) -> float:
    """Numerically stable log(1 / (1 + exp(-z)))."""
    if z >= 0:
        return -math.log1p(math.exp(-z))
    return z - math.log1p(math.exp(z))


def probability_correct(theta: float, item: ItemParams) -> float:
    """P(correct | theta) under the 2PL model."""
    z = item.a * (theta - item.b)
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def item_information(theta: float, item: ItemParams) -> float:
    """Fisher information of a 2PL item at theta: a^2 * P * (1 - P)."""
    p = probability_correct(theta, item)
    return item.a * item.a * p * (1.0 - p)


def log_likelihood(theta: float, responses: Iterable[Response]) -> float:
    total = 0.0
    for response in responses:
        z = response.item.a * (theta - response.item.b)
        total += _log_sigmoid(z) if response.correct else _log_sigmoid(-z)
    return total


def estimate_ability(responses: Sequence[Response]) -> AbilityEstimate:
    """EAP estimate of theta and its posterior standard deviation (used as the standard error)."""
    log_post = [-0.5 * ((theta - PRIOR_MEAN) / PRIOR_SD) ** 2 + log_likelihood(theta, responses) for theta in GRID]
    peak = max(log_post)
    weights = [math.exp(value - peak) for value in log_post]
    total = math.fsum(weights)
    mean = math.fsum(w * t for w, t in zip(weights, GRID, strict=True)) / total
    variance = math.fsum(w * (t - mean) ** 2 for w, t in zip(weights, GRID, strict=True)) / total
    return AbilityEstimate(theta=round(mean, 4), se=round(math.sqrt(max(variance, 0.0)), 4))


BANDS: tuple[tuple[float, str, str], ...] = (
    (-1.0, "Foundational", "Core concepts need focused review before timed practice."),
    (0.0, "Developing", "Basic skills are in place; medium-difficulty items are inconsistent."),
    (1.0, "Proficient", "Handles most medium-difficulty items; harder items are the next step."),
    (math.inf, "Advanced", "Consistently answers difficult items in the assessed topics."),
)


def ability_band(theta: float) -> tuple[str, str]:
    for upper, label, description in BANDS:
        if theta < upper:
            return label, description
    raise AssertionError("unreachable")  # pragma: no cover
