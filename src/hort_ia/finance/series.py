"""Build monthly price series per (product, entrepost) from the market dataset."""

from __future__ import annotations

from ..market import MarketDataset

# Series with fewer observed months are left out (e.g. CEASA/DF has only 3 of 25).
MIN_OBSERVATIONS = 22

SeriesKey = tuple[str, str]


def month_index(month: str) -> int:
    year, mon = month.split("-")
    return int(year) * 12 + int(mon) - 1


def month_label(index: int) -> str:
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def add_months(month: str, n: int) -> str:
    return month_label(month_index(month) + n)


def interpolate(values: list[float | None]) -> list[float]:
    """Fill gaps linearly; leading/trailing gaps take the nearest observed value."""
    known = [i for i, v in enumerate(values) if v is not None]
    if not known:
        return []
    out: list[float] = []
    for i, v in enumerate(values):
        if v is not None:
            out.append(v)
            continue
        prev = max((k for k in known if k < i), default=None)
        nxt = min((k for k in known if k > i), default=None)
        if prev is None:
            out.append(values[nxt])
        elif nxt is None:
            out.append(values[prev])
        else:
            w = (i - prev) / (nxt - prev)
            out.append(values[prev] + w * (values[nxt] - values[prev]))
    return out


def build_series(
    dataset: MarketDataset, min_observations: int = MIN_OBSERVATIONS
) -> tuple[dict[SeriesKey, list[float]], list[str]]:
    """Return {(product_id, entrepost_id): monthly prices} over a common month axis, plus that axis."""
    observed: dict[SeriesKey, dict[int, float]] = {}
    for p in dataset.prices:
        observed.setdefault((p.product_id, p.entrepost_id), {})[month_index(p.month)] = p.price_brl_kg
    if not observed:
        return {}, []
    first = min(i for cells in observed.values() for i in cells)
    last = max(i for cells in observed.values() for i in cells)
    months = [month_label(i) for i in range(first, last + 1)]
    series = {
        key: interpolate([cells.get(i) for i in range(first, last + 1)])
        for key, cells in observed.items()
        if len(cells) >= min_observations
    }
    return series, months
