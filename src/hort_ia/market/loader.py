"""Load and validate the market dataset from data/market/.

The dataset has its own source registry (`sources.json` in the same directory); it
only touches the agronomic knowledge base to check `crop_id` links in the report.

Run `python -m hort_ia.market` to print a coverage report.
"""

from __future__ import annotations

import csv
import json
import os
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..core.sources import Source
from .models import (
    Entrepost,
    MarketDataset,
    MarketProduct,
    MarketVolume,
    MicroregionSupply,
    PriceObservation,
    PriceReference,
    QuantityObservation,
    UfSupply,
    check_crop_links,
)

# src/hort_ia/market/loader.py -> repository root is parents[3]
DEFAULT_MARKET_DIR = Path(__file__).resolve().parents[3] / "data" / "market"


def market_dir() -> Path:
    return Path(os.environ.get("HORTIA_MARKET_DIR", DEFAULT_MARKET_DIR))


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path.name}: expected a JSON list")
    return data


def _index_unique(items: list[Any], filename: str) -> dict[str, Any]:
    """Index records by id, failing on duplicates (a dict would silently overwrite)."""
    counts = Counter(item.id for item in items)
    duplicates = [i for i, n in counts.items() if n > 1]
    if duplicates:
        raise ValueError(f"{filename}: duplicate ids {duplicates}")
    return {item.id: item for item in items}


def _read_csv(path: Path, model: type) -> list[Any]:
    """Read a tidy CSV into records; an empty cell becomes None (pydantic coerces the rest)."""
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return [
        model(**{key: (value.strip() or None) for key, value in row.items()}) for row in rows
    ]


def load_market_dataset(directory: Path | None = None) -> MarketDataset:
    directory = directory or market_dir()
    sources = [Source(**s) for s in _read_json_list(directory / "sources.json")]
    products = [MarketProduct(**p) for p in _read_json_list(directory / "products.json")]
    entrepostos = [Entrepost(**e) for e in _read_json_list(directory / "entrepostos.json")]
    return MarketDataset(
        sources=_index_unique(sources, "sources.json"),
        products=_index_unique(products, "products.json"),
        entrepostos=_index_unique(entrepostos, "entrepostos.json"),
        prices=_read_csv(directory / "prices_monthly.csv", PriceObservation),
        price_reference=_read_csv(directory / "prices_reference.csv", PriceReference),
        quantities=_read_csv(directory / "quantities.csv", QuantityObservation),
        volumes=_read_csv(directory / "volume_totals.csv", MarketVolume),
        microregion_supply=_read_csv(directory / "supply_microregions.csv", MicroregionSupply),
        uf_supply=_read_csv(directory / "supply_uf.csv", UfSupply),
    )


@lru_cache(maxsize=1)
def get_market_dataset() -> MarketDataset:
    """Cached instance for the FastAPI app (use as a dependency)."""
    return load_market_dataset()


def coverage_report(dataset: MarketDataset) -> str:
    months = sorted({p.month for p in dataset.prices})
    lines = [
        f"Products: {len(dataset.products)} | Entrepostos: {len(dataset.entrepostos)}",
        f"Price series: {len(dataset.prices)} observations, {months[0]} to {months[-1]} "
        f"({len(months)} months)",
    ]
    cells = len(dataset.products) * len(dataset.entrepostos) * len(months)
    lines.append(f"Price matrix fill rate: {len(dataset.prices) / cells:.0%} of {cells} cells")

    for product in dataset.products.values():
        missing = [
            e.id
            for e in dataset.entrepostos.values()
            if not any(
                p.product_id == product.id and p.entrepost_id == e.id for p in dataset.prices
            )
        ]
        if missing:
            lines.append(f"  - {product.id}: no price from {', '.join(missing)}")

    quantity_months = sorted({q.month for q in dataset.quantities})
    lines.append(
        f"Quantities: {len(dataset.quantities)} observations for {', '.join(quantity_months)}"
    )
    lines.append(
        f"Volume totals: {len(dataset.volumes)} months | "
        f"Supply: {len(dataset.microregion_supply)} microregions, {len(dataset.uf_supply)} UFs"
    )
    unlinked = [p.id for p in dataset.products.values() if p.crop_id is None]
    lines.append(f"Products without an agronomic record ({len(unlinked)}): {', '.join(unlinked)}")

    try:
        from ..knowledge import load_knowledge_base

        broken = check_crop_links(dataset, load_knowledge_base())
        lines.append(f"Broken crop links: {len(broken)}" + ("" if not broken else "\n  - " + "\n  - ".join(broken)))
    except Exception as error:  # the market dataset must stay usable on its own
        lines.append(f"Crop links not checked (knowledge base unavailable: {error})")
    return "\n".join(lines)
