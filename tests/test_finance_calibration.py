"""Unit tests of the calibration (9.6.1-5) and of the error validation (9.6.2-4). Plan: docs/finance/9.6.2-1."""

import pytest

from hort_ia.finance import Forecaster
from hort_ia.finance.calibration import alpha_report, score, window_report
from hort_ia.finance.models import fit_ses_alpha, naive, ses, ses_level
from hort_ia.finance.series import build_series
from hort_ia.finance.validation import TARGETS, out_of_sample, run
from hort_ia.market import get_market_dataset


@pytest.fixture(scope="module")
def series():
    return build_series(get_market_dataset())[0]


@pytest.fixture(scope="module")
def forecaster():
    return Forecaster(get_market_dataset())


@pytest.fixture(scope="module")
def report(forecaster):
    return run(forecaster)


# --- alpha ---


def test_alpha_follows_the_signal_on_a_step_series():
    assert fit_ses_alpha([1.0] * 10 + [5.0] * 10) == 0.9


def test_alpha_prefers_smoothing_on_alternating_noise():
    assert fit_ses_alpha([1.0, 3.0] * 10) <= 0.2


def test_alpha_depends_on_the_horizon():
    """Period 2: one step ahead the last value misleads, two steps ahead it repeats."""
    y = [1.0, 3.0] * 10
    assert fit_ses_alpha(y, 1) <= 0.2
    assert fit_ses_alpha(y, 2) == 0.9


def test_alpha_of_one_step_is_the_default():
    y = [3.0, 4.0, 3.5, 5.0, 4.5, 4.0, 3.8, 4.2]
    assert fit_ses_alpha(y) == fit_ses_alpha(y, 1)


def test_alpha_survives_a_history_shorter_than_the_horizon():
    assert 0 < fit_ses_alpha([2.0, 3.0], 3) < 1


def test_ses_uses_the_alpha_of_the_horizon():
    y = [1.0, 3.0] * 10
    assert ses(y, 2) == pytest.approx(ses_level(y, 0.9))


def test_ses_at_three_months_stays_between_min_and_max():
    y = [3.0, 4.0, 3.5, 5.0, 4.5, 4.0, 3.8, 4.2]
    assert min(y) <= ses(y, 3) <= max(y)


# --- calibration report ---


def test_score_of_a_perfect_forecast_is_zero():
    result = score({("p", "e"): [2.0] * 20}, naive, 1)
    assert result == {"mape": 0.0, "mae": 0.0, "n": 5}


def test_horizon_fit_improves_ses_at_three_months(series):
    report = alpha_report(series)["3"]
    assert report["fitted_h_steps"]["mape"] < report["fitted_1_step"]["mape"]


def test_horizon_fit_changes_nothing_at_one_month(series):
    report = alpha_report(series)["1"]
    assert report["fitted_h_steps"] == report["fitted_1_step"]


def test_window_of_15_keeps_the_selection_of_18_with_more_errors(series):
    report = window_report(series)
    for h in ("1", "3"):
        assert report["15"][h]["selected"] == report["18"][h]["selected"]
        assert report["15"][h]["n"] > report["18"][h]["n"]


def test_calibration_keeps_the_selected_methods(forecaster):
    """Calibrating SES must not change the methods the service returns (proposal of 10/10/2026)."""
    expected = {
        ("alface", 1): "naive",
        ("batata", 1): "naive",
        ("cebola", 1): "naive",
        ("cenoura", 1): "naive",
        ("tomate", 1): "seasonal_naive",
        ("alface", 3): "seasonal_naive",
        ("batata", 3): "seasonal_naive",
        ("cebola", 3): "naive",
        ("cenoura", 3): "naive",
        ("tomate", 3): "seasonal_naive",
    }
    assert {key: forecaster.best_method(*key) for key in expected} == expected


# --- error validation ---


def test_validated_average_meets_the_targets_on_the_selection_data(report):
    for h, target in TARGETS.items():
        assert report["horizons"][str(h)]["selected_average_mape"] <= target


def test_no_product_is_worse_than_naive(report):
    for horizon in report["horizons"].values():
        assert all(p["not_worse_than_naive"] for p in horizon["products"].values())


def test_only_the_products_reported_apart_miss_the_target(report):
    """Decision record 9.6.1-3: tomato and carrot have higher errors and are reported apart."""
    missed = {
        (h, name)
        for h, horizon in report["horizons"].items()
        for name, product in horizon["products"].items()
        if not product["meets_target"]
    }
    assert missed == {("1", "tomate"), ("3", "cenoura")}


def test_out_of_sample_recorded_in_the_validation_document(forecaster):
    """Pins docs/finance/9.6.2-4: update the document if these numbers change."""
    one, three = out_of_sample(forecaster, 1), out_of_sample(forecaster, 3)
    assert (one["n"], three["n"]) == (430, 210)
    assert one["mape"] == pytest.approx(0.2038, abs=0.001)
    assert three["mape"] == pytest.approx(0.3664, abs=0.001)
    assert one["interval_coverage"] == pytest.approx(0.5605, abs=0.001)
    assert three["interval_coverage"] == pytest.approx(0.3619, abs=0.001)


def test_special_series_are_flagged(report):
    special = report["special_series"]
    assert special["stale"]["reference_month"] == "2026-06" and "stale" in special["stale"]["warning"]
    assert special["degraded"]["degraded"] and not special["degraded"]["has_interval"]
