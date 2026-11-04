"""Forecasting methods (decision record 9.6.1-3). Each takes the history and the horizon in months."""

from __future__ import annotations

from collections.abc import Callable, Sequence

SEASON = 12
ALPHA_GRID = [i / 10 for i in range(1, 10)]


def naive(y: Sequence[float], h: int) -> float:
    return y[-1]


def seasonal_naive(y: Sequence[float], h: int) -> float:
    """Value of the same month one year earlier (falls back to naive without a full year)."""
    idx = len(y) + h - 1 - SEASON
    return y[idx] if 0 <= idx < len(y) else y[-1]


def moving_average(y: Sequence[float], h: int, window: int = 3) -> float:
    tail = y[-window:]
    return sum(tail) / len(tail)


def ses_level(y: Sequence[float], alpha: float) -> float:
    level = y[0]
    for v in y[1:]:
        level = alpha * v + (1 - alpha) * level
    return level


def fit_ses_alpha(y: Sequence[float], h: int = 1) -> float:
    """Pick alpha minimising the h-step squared error on the history (calibration 9.6.1-5)."""

    def sse(alpha: float) -> float:
        total, level = 0.0, y[0]
        for i, v in enumerate(y[1:], start=1):
            if i + h - 1 < len(y):
                total += (y[i + h - 1] - level) ** 2
            level = alpha * v + (1 - alpha) * level
        return total

    return min(ALPHA_GRID, key=sse)


def ses(y: Sequence[float], h: int) -> float:
    """Simple exponential smoothing: the forecast is flat at the last smoothed level."""
    return ses_level(y, fit_ses_alpha(y, h))


Method = Callable[[Sequence[float], int], float]

METHODS: dict[str, Method] = {
    "naive": naive,
    "seasonal_naive": seasonal_naive,
    "moving_average": moving_average,
    "ses": ses,
}

# Candidates for automatic selection; moving_average stays available as an alternative.
CANDIDATES = ("naive", "seasonal_naive", "ses")
