"""`python -m hort_ia.finance.calibration`: calibration of alpha and of the validation window (9.6.1-5).

Scope set in the schedule (v7, 10/10/2026): only the SES alpha and the validation window.
Prints JSON; the decision based on it is in docs/finance/9.6.1-5_Calibracao.md.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence

from ..market import get_market_dataset
from .backtest import HORIZONS, MIN_TRAIN, overall, run_backtest
from .models import ALPHA_GRID, CANDIDATES, fit_ses_alpha, ses_level
from .series import SeriesKey, build_series

WINDOWS = (12, 15, 18)

Series = dict[SeriesKey, list[float]]


def score(series: Series, forecast: Callable[[Sequence[float], int], float], h: int, min_train: int = MIN_TRAIN) -> dict:
    """Pooled rolling-origin errors of a forecast function at one horizon."""
    absolute: list[float] = []
    percentage: list[float] = []
    for y in series.values():
        for origin in range(min_train, len(y) - h + 1):
            actual = y[origin + h - 1]
            error = abs(forecast(y[:origin], h) - actual)
            absolute.append(error)
            percentage.append(error / actual)
    return {
        "mape": round(sum(percentage) / len(percentage), 4),
        "mae": round(sum(absolute) / len(absolute), 4),
        "n": len(absolute),
    }


def alpha_report(series: Series, horizons: tuple[int, ...] = HORIZONS) -> dict:
    """SES errors with each fixed alpha, with alpha fitted one step ahead and fitted h steps ahead."""
    return {
        str(h): {
            "fixed": {str(a): score(series, lambda y, _h, a=a: ses_level(y, a), h) for a in ALPHA_GRID},
            "fitted_1_step": score(series, lambda y, _h: ses_level(y, fit_ses_alpha(y, 1)), h),
            "fitted_h_steps": score(series, lambda y, _h: ses_level(y, fit_ses_alpha(y, _h)), h),
        }
        for h in horizons
    }


def window_report(series: Series, windows: tuple[int, ...] = WINDOWS, horizons: tuple[int, ...] = HORIZONS) -> dict:
    """For each minimum training window: errors of the candidates and the method selected per product."""
    report = {}
    products = sorted({p for p, _ in series})
    for window in windows:
        result = run_backtest(series, methods=CANDIDATES, horizons=horizons, min_train=window)
        report[str(window)] = {
            str(h): {
                "n": overall(result, h, CANDIDATES[0]).n,
                "mape": {m: round(overall(result, h, m).mape, 4) for m in CANDIDATES},
                "selected": {p: min(CANDIDATES, key=lambda m: result[(p, h, m)].mae) for p in products},
            }
            for h in horizons
        }
    return report


def main() -> None:
    series, _ = build_series(get_market_dataset())
    print(json.dumps({"alpha": alpha_report(series), "window": window_report(series)}, indent=2))


if __name__ == "__main__":
    main()
