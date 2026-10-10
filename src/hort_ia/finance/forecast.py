"""Price forecast service: picks the best validated method per product and horizon."""

from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel

from ..market import MarketDataset, get_market_dataset
from .backtest import HORIZONS, BacktestResult, ErrorStats, run_backtest
from .models import CANDIDATES, METHODS
from .series import SeriesKey, add_months, build_series, latest_month

INTERVAL = (0.1, 0.9)  # 80% interval from the empirical distribution of validation errors


class ForecastError(Exception):
    """The forecast cannot be produced."""


class UnknownIdError(ForecastError):
    """Unknown product or entrepost, or no price data for the pair."""


class UnsupportedHorizonError(ForecastError):
    """Horizon outside the validated ones."""


class PriceForecast(BaseModel):
    product_id: str
    entrepost_id: str
    horizon_months: int
    reference_month: str  # last observed month
    target_month: str
    last_price_brl_kg: float
    forecast_price_brl_kg: float
    change_pct: float  # forecast / last price - 1, as a fraction
    lower_brl_kg: float | None
    upper_brl_kg: float | None
    method: str
    validation_mape: float | None
    degraded: bool = False
    warning: str | None = None


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    pos = q * (len(ordered) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (pos - lo) * (ordered[hi] - ordered[lo])


class Forecaster:
    def __init__(self, dataset: MarketDataset, horizons: tuple[int, ...] = HORIZONS):
        self.dataset = dataset
        self.horizons = horizons
        self.series, self.last_month = build_series(dataset)
        self.latest = latest_month(dataset)
        self.backtest: BacktestResult = run_backtest(self.series, horizons=horizons)
        self._best: dict[tuple[str, int], str] = {}
        for product in {p for p, _ in self.series}:
            for h in horizons:
                self._best[(product, h)] = min(
                    CANDIDATES, key=lambda m: self.backtest[(product, h, m)].mae
                )

    def best_method(self, product_id: str, horizon: int) -> str:
        return self._best[(product_id, horizon)]

    def _check_ids(self, product_id: str, entrepost_id: str) -> None:
        if product_id not in self.dataset.products:
            raise UnknownIdError(f"unknown product: {product_id}")
        if entrepost_id not in self.dataset.entrepostos:
            raise UnknownIdError(f"unknown entrepost: {entrepost_id}")

    def forecast(self, product_id: str, entrepost_id: str, horizon: int = 1) -> PriceForecast:
        self._check_ids(product_id, entrepost_id)
        if horizon not in self.horizons:
            raise UnsupportedHorizonError(f"unsupported horizon: {horizon} (use one of {list(self.horizons)})")
        key: SeriesKey = (product_id, entrepost_id)
        y = self.series.get(key)
        if y is None:
            return self._degraded(product_id, entrepost_id, horizon)

        method = self.best_method(product_id, horizon)
        stats: ErrorStats = self.backtest[(product_id, horizon, method)]
        price = METHODS[method](y, horizon)
        lo, hi = (_quantile(stats.relative, q) for q in INTERVAL)
        reference = self.last_month[key]
        stale = reference != self.latest
        return PriceForecast(
            product_id=product_id,
            entrepost_id=entrepost_id,
            horizon_months=horizon,
            reference_month=reference,
            target_month=add_months(reference, horizon),
            last_price_brl_kg=round(y[-1], 2),
            forecast_price_brl_kg=round(price, 2),
            change_pct=round(price / y[-1] - 1, 4),
            lower_brl_kg=round(price * (1 + lo), 2),
            upper_brl_kg=round(price * (1 + hi), 2),
            method=method,
            validation_mape=round(stats.mape, 4),
            warning=f"stale series: last observed month is {reference}, dataset goes to {self.latest}"
            if stale
            else None,
        )

    def _degraded(self, product_id: str, entrepost_id: str, horizon: int) -> PriceForecast:
        """Series too short for validation: naive forecast, flagged, no interval."""
        observed = sorted(
            (p.month, p.price_brl_kg)
            for p in self.dataset.prices
            if p.product_id == product_id and p.entrepost_id == entrepost_id
        )
        if not observed:
            raise UnknownIdError(f"no price data for {product_id} at {entrepost_id}")
        month, last = observed[-1]
        return PriceForecast(
            product_id=product_id,
            entrepost_id=entrepost_id,
            horizon_months=horizon,
            reference_month=month,
            target_month=add_months(month, horizon),
            last_price_brl_kg=round(last, 2),
            forecast_price_brl_kg=round(last, 2),
            change_pct=0.0,
            lower_brl_kg=None,
            upper_brl_kg=None,
            method="naive",
            validation_mape=None,
            degraded=True,
            warning=f"only {len(observed)} months of data: naive forecast without validation"
            + (f"; stale series: last observed month is {month}, dataset goes to {self.latest}" if month != self.latest else ""),
        )


@lru_cache(maxsize=1)
def get_forecaster() -> Forecaster:
    """Cached instance for the FastAPI app (use as a dependency)."""
    return Forecaster(get_market_dataset())
