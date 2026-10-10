"""Tests for the price forecasting module (WBS 9.6.1-4; decision record 9.6.1-3)."""

import asyncio

import pytest
from fastapi import HTTPException

from hort_ia.api.main import app
from hort_ia.finance import (
    MODEL_VERSION,
    ForecastError,
    Forecaster,
    UnknownIdError,
    UnsupportedHorizonError,
    get_forecaster,
)
from hort_ia.finance.backtest import overall, run_backtest
from hort_ia.finance.models import moving_average, naive, seasonal_naive, ses
from hort_ia.finance.series import add_months, build_series, interpolate
from hort_ia.market import get_market_dataset


@pytest.fixture(scope="module")
def forecaster() -> Forecaster:
    return get_forecaster()


# --- methods on synthetic series with known results ---


def test_naive_repeats_last_value():
    assert naive([1.0, 2.0, 3.0], 1) == 3.0


def test_seasonal_naive_uses_same_month_last_year():
    y = [float(i) for i in range(1, 25)]  # 24 months
    assert seasonal_naive(y, 1) == y[12]  # target month 25 -> month 13
    assert seasonal_naive(y, 3) == y[14]


def test_seasonal_naive_falls_back_to_naive_on_short_history():
    assert seasonal_naive([1.0, 2.0, 3.0], 1) == 3.0


def test_moving_average_of_last_three():
    assert moving_average([1.0, 5.0, 6.0, 7.0], 1) == 6.0


def test_ses_constant_series_is_constant():
    assert ses([4.0] * 20, 1) == pytest.approx(4.0)


def test_ses_stays_between_min_and_max():
    y = [3.0, 4.0, 3.5, 5.0, 4.5, 4.0, 3.8, 4.2]
    assert min(y) <= ses(y, 1) <= max(y)


# --- series ---


def test_interpolate_fills_internal_and_edge_gaps():
    assert interpolate([None, 2.0, None, 4.0, None]) == [2.0, 2.0, 3.0, 4.0, 4.0]


def test_add_months_crosses_year():
    assert add_months("2026-11", 3) == "2027-02"


def test_build_series_drops_short_series():
    series, last_month = build_series(get_market_dataset())
    assert ("alface", "ceasa_df_brasilia") not in series  # DF has only 3 months
    assert set(series) == set(last_month)


def test_build_series_does_not_extend_edges():
    """CEASA/GO stopped publishing after 2026-06: the series must end there, not repeat the price."""
    series, last_month = build_series(get_market_dataset())
    assert last_month[("tomate", "ceasa_go_goiania")] == "2026-06"
    assert len(series[("tomate", "ceasa_go_goiania")]) == 23
    assert last_month[("tomate", "ceagesp_sp")] == "2026-08"
    assert len(series[("tomate", "ceagesp_sp")]) == 25


# --- validation without look-ahead ---


def test_backtest_does_not_use_future_values():
    # A series that jumps at the end: naive forecasts for earlier origins cannot know it.
    y = [1.0] * 20 + [10.0] * 3
    res = run_backtest({("p", "e"): y}, methods=("naive",), horizons=(1,), min_train=15)
    stats = res[("p", 1, "naive")]
    assert stats.n == len(y) - 15
    assert max(stats.absolute) == pytest.approx(9.0)  # only at the jump
    assert sum(1 for e in stats.absolute if e > 0) == 1


def test_backtest_matches_decision_record(forecaster):
    """Numbers recorded in 9.6.1-1 (55 series, rolling origin, >= 15 months of training).

    Pinned to the dataset of the decision record: update together with the market dataset.
    """
    assert len(forecaster.series) == 55
    naive_1 = overall(forecaster.backtest, 1, "naive")
    snaive_3 = overall(forecaster.backtest, 3, "seasonal_naive")
    assert naive_1.n == 540 and snaive_3.n == 430
    assert naive_1.mape == pytest.approx(0.186, abs=0.005)
    assert snaive_3.mape == pytest.approx(0.282, abs=0.005)


def test_error_targets_of_decision_record(forecaster):
    """Targets of 9.6.1-3: MAPE <= 20% at 1 month and <= 30% at 3 months."""
    for horizon, target in ((1, 0.20), (3, 0.30)):
        best = min(overall(forecaster.backtest, horizon, m).mape for m in ("naive", "seasonal_naive", "ses"))
        assert best <= target


def test_selected_method_is_never_worse_than_naive(forecaster):
    for product in {p for p, _ in forecaster.series}:
        for h in (1, 3):
            chosen = forecaster.backtest[(product, h, forecaster.best_method(product, h))]
            assert chosen.mae <= forecaster.backtest[(product, h, "naive")].mae


# --- forecast service ---


def test_forecast_fields_and_interval(forecaster):
    f = forecaster.forecast("alface", "ceagesp_sp", 1)
    assert f.reference_month == "2026-08" and f.target_month == "2026-09"
    assert f.lower_brl_kg <= f.forecast_price_brl_kg <= f.upper_brl_kg
    assert f.change_pct == pytest.approx(f.forecast_price_brl_kg / f.last_price_brl_kg - 1, abs=1e-3)
    assert not f.degraded and f.validation_mape is not None


def test_forecast_identifies_origin(forecaster):
    """Contract with the finance team (item 5.2.3): every forecast names its source and model version."""
    for args in [("alface", "ceagesp_sp", 1), ("alface", "ceasa_df_brasilia", 1), ("tomate", "ceasa_go_goiania", 3)]:
        f = forecaster.forecast(*args)
        assert f.source == "conab_boletim_hortigranjeiro"
        assert f.model_version == MODEL_VERSION == "1.0.0"
        assert f.method in {"naive", "seasonal_naive", "ses"}


def test_forecast_three_months_ahead(forecaster):
    assert forecaster.forecast("tomate", "ceagesp_sp", 3).target_month == "2026-11"


def test_stale_series_is_flagged(forecaster):
    f = forecaster.forecast("tomate", "ceasa_go_goiania", 1)
    assert f.reference_month == "2026-06" and f.target_month == "2026-07"
    assert f.warning and "2026-06" in f.warning and not f.degraded


def test_fresh_series_has_no_warning(forecaster):
    assert forecaster.forecast("tomate", "ceagesp_sp", 1).warning is None


def test_degraded_forecast_for_short_series(forecaster):
    f = forecaster.forecast("alface", "ceasa_df_brasilia", 1)
    assert f.degraded and f.method == "naive" and f.lower_brl_kg is None and f.warning
    assert "stale" in f.warning  # the last observation is almost two years old


@pytest.mark.parametrize(
    "args,error",
    [
        (("banana", "ceagesp_sp", 1), UnknownIdError),
        (("alface", "ceasa_inexistente", 1), UnknownIdError),
        (("alface", "ceagesp_sp", 2), UnsupportedHorizonError),
    ],
)
def test_forecast_rejects_invalid_input(forecaster, args, error):
    with pytest.raises(error) as raised:
        forecaster.forecast(*args)
    assert isinstance(raised.value, ForecastError)


# --- API contract (route function called directly: TestClient would need a new dev dependency) ---


def _call(**params):
    from hort_ia.api.finance import price_forecast

    return asyncio.run(price_forecast(forecaster=get_forecaster(), **params))


def test_api_route_is_registered():
    assert "/finance/price-forecast" in app.openapi()["paths"]


def test_api_returns_forecast():
    body = _call(product_id="alface", entrepost_id="ceagesp_sp")
    assert body.horizon_months == 1 and body.method in {"naive", "seasonal_naive", "ses"}


def test_api_unknown_product_is_404():
    with pytest.raises(HTTPException) as error:
        _call(product_id="banana", entrepost_id="ceagesp_sp")
    assert error.value.status_code == 404


def test_api_unsupported_horizon_is_422():
    with pytest.raises(HTTPException) as error:
        _call(product_id="alface", entrepost_id="ceagesp_sp", horizon_months=2)
    assert error.value.status_code == 422
