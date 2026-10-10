"""Rolling-origin validation: errors per method, product and horizon (no look-ahead)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import METHODS
from .series import SeriesKey

MIN_TRAIN = 15
HORIZONS = (1, 3)


@dataclass
class ErrorStats:
    """Accumulated errors; `relative` are signed (actual / forecast - 1) for the intervals."""

    absolute: list[float] = field(default_factory=list)
    percentage: list[float] = field(default_factory=list)
    relative: list[float] = field(default_factory=list)

    def add(self, forecast: float, actual: float) -> None:
        self.absolute.append(abs(forecast - actual))
        self.percentage.append(abs(forecast - actual) / actual)
        self.relative.append(actual / forecast - 1)

    @property
    def n(self) -> int:
        return len(self.absolute)

    @property
    def mae(self) -> float:
        return sum(self.absolute) / self.n

    @property
    def mape(self) -> float:
        return sum(self.percentage) / self.n


# (product_id, horizon, method) -> pooled errors over every entrepost of that product
BacktestResult = dict[tuple[str, int, str], ErrorStats]


def run_backtest(
    series: dict[SeriesKey, list[float]],
    methods: tuple[str, ...] = tuple(METHODS),
    horizons: tuple[int, ...] = HORIZONS,
    min_train: int = MIN_TRAIN,
) -> BacktestResult:
    result: BacktestResult = {}
    for (product, _entrepost), y in series.items():
        for h in horizons:
            for origin in range(min_train, len(y) - h + 1):
                history, actual = y[:origin], y[origin + h - 1]
                for name in methods:
                    stats = result.setdefault((product, h, name), ErrorStats())
                    stats.add(METHODS[name](history, h), actual)
    return result


def overall(result: BacktestResult, horizon: int, method: str) -> ErrorStats:
    """Errors of one method at one horizon pooled across all products."""
    pooled = ErrorStats()
    for (_product, h, name), stats in result.items():
        if h == horizon and name == method:
            pooled.absolute += stats.absolute
            pooled.percentage += stats.percentage
            pooled.relative += stats.relative
    return pooled
