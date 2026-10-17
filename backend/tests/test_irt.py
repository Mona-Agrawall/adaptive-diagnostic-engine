from __future__ import annotations

import itertools
import math

import pytest

from app import irt
from app.irt import AbilityEstimate, ItemParams, Response, estimate_ability, item_information, probability_correct


def test_probability_is_half_at_difficulty_and_monotonic_in_theta() -> None:
    item = ItemParams(a=1.3, b=0.4)
    assert probability_correct(0.4, item) == pytest.approx(0.5)
    values = [probability_correct(t / 10, item) for t in range(-40, 41)]
    assert all(later > earlier for earlier, later in itertools.pairwise(values))


def test_probability_is_numerically_stable_at_extremes() -> None:
    item = ItemParams(a=3.0, b=0.0)
    assert probability_correct(1e6, item) == 1.0
    assert probability_correct(-1e6, item) == 0.0
    assert irt.log_likelihood(1e3, [Response(item, False)]) < 0
    assert math.isfinite(irt.log_likelihood(-1e3, [Response(item, True)]))


def test_higher_discrimination_gives_steeper_curve() -> None:
    flat, steep = ItemParams(0.6, 0.0), ItemParams(2.0, 0.0)
    assert probability_correct(1.0, steep) > probability_correct(1.0, flat)
    assert probability_correct(-1.0, steep) < probability_correct(-1.0, flat)


def test_information_peaks_at_item_difficulty() -> None:
    item = ItemParams(a=1.5, b=-0.7)
    peak = item_information(-0.7, item)
    assert peak == pytest.approx(1.5**2 / 4)
    assert item_information(-0.2, item) < peak
    assert item_information(-1.2, item) < peak


@pytest.mark.parametrize(("a", "b"), [(0.0, 0.0), (5.0, 0.0), (1.0, 9.0), (math.nan, 0.0), (1.0, math.inf)])
def test_invalid_item_parameters_are_rejected(a: float, b: float) -> None:
    with pytest.raises(ValueError, match="outside"):
        ItemParams(a=a, b=b)


def test_no_responses_returns_the_prior() -> None:
    estimate = estimate_ability([])
    assert estimate.theta == pytest.approx(0.0, abs=1e-6)
    assert estimate.se == pytest.approx(1.0, abs=0.01)


def test_all_correct_and_all_incorrect_stay_finite_and_bounded() -> None:
    items = [ItemParams(1.2, b / 2) for b in range(-4, 5)]
    high = estimate_ability([Response(item, True) for item in items])
    low = estimate_ability([Response(item, False) for item in items])
    assert 1.0 < high.theta < irt.THETA_MAX
    assert irt.THETA_MIN < low.theta < -1.0
    assert high.theta == pytest.approx(-low.theta, abs=0.15)
    for estimate in (high, low):
        assert math.isfinite(estimate.theta) and 0 < estimate.se < 1


def test_correct_answer_raises_and_incorrect_lowers_the_estimate() -> None:
    history = [Response(ItemParams(1.2, 0.0), True), Response(ItemParams(1.2, 0.5), False)]
    base = estimate_ability(history)
    assert estimate_ability([*history, Response(ItemParams(1.2, 0.3), True)]).theta > base.theta
    assert estimate_ability([*history, Response(ItemParams(1.2, 0.3), False)]).theta < base.theta


def test_correct_on_hard_item_moves_more_than_correct_on_easy_item() -> None:
    hard = estimate_ability([Response(ItemParams(1.2, 2.0), True)])
    easy = estimate_ability([Response(ItemParams(1.2, -2.0), True)])
    assert hard.theta > easy.theta > 0


def test_standard_error_shrinks_with_more_informative_responses() -> None:
    responses: list[Response] = []
    previous = estimate_ability(responses).se
    for i in range(12):
        responses.append(Response(ItemParams(1.4, 0.0), i % 2 == 0))
        current = estimate_ability(responses).se
        assert current < previous
        previous = current


def test_single_answer_moves_estimate_substantially() -> None:
    """Regression: the old rule moved ability by ~0.025 per answer, so it could not discriminate."""
    first = estimate_ability([Response(ItemParams(1.2, 0.0), True)])
    assert first.theta > 0.3


def test_ci95_is_clamped_to_grid() -> None:
    low, high = AbilityEstimate(theta=3.9, se=0.5).ci95
    assert high == irt.THETA_MAX and low == pytest.approx(3.9 - 0.98)


@pytest.mark.parametrize(
    ("theta", "band"),
    [(-2.0, "Foundational"), (-1.0, "Developing"), (-0.01, "Developing"), (0.0, "Proficient"), (1.5, "Advanced")],
)
def test_bands(theta: float, band: str) -> None:
    assert irt.ability_band(theta)[0] == band
