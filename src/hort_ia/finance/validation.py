"""`python -m hort_ia.finance.validation`: error margin per test scenario (WBS 9.6.2-4).

Prints JSON; the results are recorded in docs/finance/9.6.2-4_Validacao_Margem_Erro.md.
"""

from __future__ import annotations

import json

from ..market import get_market_dataset
from .backtest import HORIZONS, MIN_TRAIN, ErrorStats
from .forecast import INTERVAL, Forecaster, _quantile
from .models import CANDIDATES, METHODS
from .series import SeriesKey

TARGETS = {1: 0.20, 3: 0.30}  # MAPE targets of the decision record 9.6.1-3
PRODUCTS_REPORTED_APART = ("tomate", "cenoura")  # decision record 9.6.1-3
MIN_SELECTION_ERRORS = 15  # pooled errors of a product needed before an out-of-sample selection


def _origins(series: dict[SeriesKey, list[float]], product: str, h: int) -> list[tuple[int, list[float], float]]:
    """(time index, history, actual) of each rolling origin of a product, in time order."""
    rows = [
        (origin, y[:origin], y[origin + h - 1])
        for (p, _), y in series.items()
        if p == product
        for origin in range(MIN_TRAIN, len(y) - h + 1)
    ]
    return sorted(rows, key=lambda row: row[0])


def out_of_sample(f: Forecaster, h: int) -> dict:
    """Walk-forward check: method and interval come only from errors known before each forecast.

    A product enters once it has MIN_SELECTION_ERRORS, so these results cover the later origins only.
    """
    percentage: list[float] = []
    naive_percentage: list[float] = []
    inside = 0
    for product in sorted({p for p, _ in f.series}):
        known = {m: ErrorStats() for m in CANDIDATES}
        origins = _origins(f.series, product, h)
        for time in sorted({row[0] for row in origins}):
            batch = [row for row in origins if row[0] == time]
            # an error is known only after its target month has been observed
            ready = known[CANDIDATES[0]].n >= MIN_SELECTION_ERRORS
            if ready:
                best = min(CANDIDATES, key=lambda m: known[m].mae)
                lo, hi = (_quantile(known[best].relative, q) for q in INTERVAL)
            for _, history, actual in batch:
                if ready:
                    forecast = METHODS[best](history, h)
                    percentage.append(abs(forecast - actual) / actual)
                    naive_percentage.append(abs(history[-1] - actual) / actual)
                    inside += forecast * (1 + lo) <= actual <= forecast * (1 + hi)
            matured = [row for row in origins if row[0] == time - h + 1]
            for _, history, actual in matured:
                for m in CANDIDATES:
                    known[m].add(METHODS[m](history, h), actual)
    n = len(percentage)
    return {
        "n": n,
        "mape": round(sum(percentage) / n, 4),
        "naive_mape_same_origins": round(sum(naive_percentage) / n, 4),
        "interval_coverage": round(inside / n, 4),
    }


def per_product(f: Forecaster, h: int) -> dict:
    report = {}
    for product in sorted({p for p, _ in f.series}):
        method = f.best_method(product, h)
        stats, naive = f.backtest[(product, h, method)], f.backtest[(product, h, "naive")]
        report[product] = {
            "method": method,
            "mape": round(stats.mape, 4),
            "mae": round(stats.mae, 4),
            "naive_mae": round(naive.mae, 4),
            "n": stats.n,
            "meets_target": stats.mape <= TARGETS[h],
            "not_worse_than_naive": stats.mae <= naive.mae,
        }
    return report


def selected_average(products: dict) -> float:
    return round(sum(p["mape"] for p in products.values()) / len(products), 4)


def special_series(f: Forecaster) -> dict:
    stale = f.forecast("tomate", "ceasa_go_goiania", 1)
    degraded = f.forecast("alface", "ceasa_df_brasilia", 1)
    return {
        "stale": {"case": "tomate, CEASA/GO", "reference_month": stale.reference_month, "warning": stale.warning},
        "degraded": {
            "case": "alface, CEASA/DF",
            "degraded": degraded.degraded,
            "has_interval": degraded.lower_brl_kg is not None,
            "warning": degraded.warning,
        },
    }


def extreme_changes(f: Forecaster, h: int, limit: float = 0.30) -> list[dict]:
    """Current forecasts whose change exceeds the price shocks seen in one month (decision record)."""
    rows = []
    for product, entrepost in sorted(f.series):
        forecast = f.forecast(product, entrepost, h)
        if abs(forecast.change_pct) > limit:
            rows.append({
                "product_id": product,
                "entrepost_id": entrepost,
                "change_pct": forecast.change_pct,
                "method": forecast.method,
            })
    return rows


def run(f: Forecaster | None = None) -> dict:
    f = f or Forecaster(get_market_dataset())
    report: dict = {"series": len(f.series), "latest_month": f.latest, "horizons": {}}
    for h in HORIZONS:
        products = per_product(f, h)
        extreme = extreme_changes(f, h)
        report["horizons"][str(h)] = {
            "target": TARGETS[h],
            "selected_average_mape": selected_average(products),
            "out_of_sample": out_of_sample(f, h),
            "products": products,
            "extreme_changes_over_30pct": {"count": len(extreme), "of": len(f.series), "rows": extreme},
        }
    report["reported_apart"] = list(PRODUCTS_REPORTED_APART)
    report["special_series"] = special_series(f)
    return report


def main() -> None:
    print(json.dumps(run(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
