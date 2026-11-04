"""Tolerance band and staleness drift, both measured on the price series (9.5.1-3, D3 and D4).

Neither is a constant in the code, which is the point of D3: a fixed +-10% band would be tight for
tomate (16% of month-on-month noise) and loose for alface (8%). Both quantities are recomputed from
`prices_monthly.csv`, so they follow the dataset when the monthly Conab edition is loaded.

Gaps are *not* interpolated here: changes are taken between consecutive **observed** months of each
series, the same way `docs/commercial/exploratory_price_spread.py` measures them. Interpolating would
invent month-on-month changes of exactly the size the band is meant to measure. This is the one point
where the treatment deliberately differs from `hort_ia.finance.series`, which interpolates because a
forecasting method needs an evenly spaced series.
"""

from __future__ import annotations

from statistics import median

from ..market import MarketDataset

# Above this the entrepost is dropped and the ladder descends a level (9.5.1-3, section 5.3).
MAX_LAG_MONTHS = 3

SeriesKey = tuple[str, str]  # (product_id, entrepost_id)


def month_index(month: str) -> int:
    """'2026-08' -> absolute month number, so lags are a subtraction.

    `hort_ia.finance.series` has its own copy: decision D7 keeps 9.5 independent of 9.6 in v1.
    Move both to `hort_ia.core` if a third module needs month arithmetic.
    """
    year, mon = month.split("-")
    return int(year) * 12 + int(mon) - 1


def observed_series(dataset: MarketDataset) -> dict[SeriesKey, list[float]]:
    """Observed prices per (product, entrepost), oldest month first, gaps left out."""
    cells: dict[SeriesKey, dict[int, float]] = {}
    for p in dataset.prices:
        cells.setdefault((p.product_id, p.entrepost_id), {})[month_index(p.month)] = p.price_brl_kg
    return {key: [v for _, v in sorted(months.items())] for key, months in cells.items()}


def _relative_changes(series: list[float], step: int) -> list[float]:
    return [abs(series[i] / series[i - step] - 1) for i in range(step, len(series))]


def tolerance_bands(dataset: MarketDataset) -> dict[str, float]:
    """`band_pct` per product: median |month-on-month change|, rounded to the percentage point.

    Measured on every series of the product (55 series, 25 months in the September 2026 edition):
    alface 8%, batata 11%, cenoura 12%, cebola 13%, tomate 16%.
    """
    series = observed_series(dataset)
    bands: dict[str, float] = {}
    for product_id in dataset.products:
        changes = [
            change
            for (product, _), values in series.items()
            if product == product_id
            for change in _relative_changes(values, 1)
        ]
        if changes:
            bands[product_id] = round(median(changes), 2)
    return bands


def staleness_drift(dataset: MarketDataset, max_lag: int = MAX_LAG_MONTHS) -> dict[int, float]:
    """How far a reference price has drifted after *k* months, pooled over every series.

    Median |change| over k observations: 11.6% (1 month), 20.3% (2), 27.6% (3). Section 5.3 widens
    the band by this amount when the entrepost is 2 or 3 months behind; a lag of 0 or 1 is normal
    and widens nothing.
    """
    series = observed_series(dataset).values()
    return {
        k: round(median([c for values in series for c in _relative_changes(values, k)]), 3)
        for k in range(1, max_lag + 1)
    }
