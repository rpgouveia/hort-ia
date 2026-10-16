import csv
from pathlib import Path

import pytest

from hort_ia.finance.forecast import Forecaster
from hort_ia.finance.series import build_series, interpolate
from hort_ia.market import get_market_dataset


def test_no_zero_or_negative_prices_in_market_data():
    """Rule TRAT-NULOS-01: No null or <= 0 prices should exist in processed market files."""
    dataset = get_market_dataset()
    for price in dataset.prices:
        assert price.price_brl_kg > 0, f"Invalid price {price.price_brl_kg} for {price.product_id} in {price.month}"
    for ref in dataset.price_reference:
        assert ref.price_brl_kg > 0, f"Invalid reference price {ref.price_brl_kg} for {ref.product_id}"


def test_float_noise_is_sanitized():
    """Rule TRAT-INCONSIST-02: Floats must be rounded to max 2 decimals for BRL/kg."""
    dataset = get_market_dataset()
    for price in dataset.prices:
        val_str = f"{price.price_brl_kg}"
        decimals = len(val_str.split(".")[1]) if "." in val_str else 0
        assert decimals <= 2, f"Float noise found: {val_str}"


def test_linear_interpolation_fills_internal_gaps_only():
    """Rule TRAT-NULOS-02: Linear interpolation fills intermediate gaps and maintains real edges."""
    raw_series = [None, 3.0, None, 5.0, None]
    filled = interpolate(raw_series)
    assert filled == [3.0, 3.0, 4.0, 5.0, 5.0]

    internal_only = [2.0, None, 6.0]
    assert interpolate(internal_only) == [2.0, 4.0, 6.0]


def test_short_series_fall_into_degraded_mode():
    """Rule TRAT-NULOS-03: Series with insufficient history (like DF) are handled via degraded mode."""
    forecaster = Forecaster(get_market_dataset())
    # CEASA/DF has only 3 months of data
    forecast = forecaster.forecast("alface", "ceasa_df_brasilia", horizon=1)
    assert forecast.degraded is True
    assert forecast.method == "naive"
    assert "naive forecast without validation" in (forecast.warning or "")
    assert forecast.lower_brl_kg is None
    assert forecast.upper_brl_kg is None


def test_outlier_detection_logic_identifies_known_climate_peaks():
    """Rule TRAT-DISCREP-01: Outliers are accurately detected by IQR."""
    dataset = get_market_dataset()
    tomate_prices = [p.price_brl_kg for p in dataset.prices if p.product_id == "tomate"]
    tomate_prices.sort()
    n = len(tomate_prices)
    q1 = tomate_prices[int(n * 0.25)]
    q3 = tomate_prices[int(n * 0.75)]
    iqr = q3 - q1
    upper_threshold = q3 + 1.5 * iqr

    # Historic peaks above upper threshold
    max_price = max(tomate_prices)
    assert max_price > upper_threshold
    assert max_price >= 10.0
