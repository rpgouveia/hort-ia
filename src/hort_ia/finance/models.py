"""Forecasting methods (decision record 9.6.1-3). Each takes the history and the horizon in months."""

from __future__ import annotations

from collections.abc import Callable, Sequence

SEASON = 12
_ALPHAS = [i / 10 for i in range(1, 10)]


def naive(y: Sequence[float], h: int) -> float:
    return y[-1]


def seasonal_naive(y: Sequence[float], h: int) -> float:
    """Value of the same month one year earlier (falls back to naive without a full year)."""
    idx = len(y) + h - 1 - SEASON
    return y[idx] if 0 <= idx < len(y) else y[-1]


def moving_average(y: Sequence[float], h: int, window: int = 3) -> float:
    tail = y[-window:]
    return sum(tail) / len(tail)


def _ses_level(y: Sequence[float], alpha: float) -> float:
    level = y[0]
    for v in y[1:]:
        level = alpha * v + (1 - alpha) * level
    return level


def fit_ses_alpha(y: Sequence[float]) -> float:
    """Pick alpha minimising the one-step squared error on the history."""

    def sse(alpha: float) -> float:
        total, level = 0.0, y[0]
        for v in y[1:]:
            total += (v - level) ** 2
            level = alpha * v + (1 - alpha) * level
        return total

    return min(_ALPHAS, key=sse)


def ses(y: Sequence[float], h: int) -> float:
    """Simple exponential smoothing: the forecast is flat at the last smoothed level."""
    return _ses_level(y, fit_ses_alpha(y))


Method = Callable[[Sequence[float], int], float]

METHODS: dict[str, Method] = {
    "naive": naive,
    "seasonal_naive": seasonal_naive,
    "moving_average": moving_average,
    "ses": ses,
}

# Candidates for automatic selection; moving_average stays available as an alternative.
CANDIDATES = ("naive", "seasonal_naive", "ses")
