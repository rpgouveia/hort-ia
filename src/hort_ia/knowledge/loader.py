"""Load and validate the knowledge base from data/knowledge/.

Run `python -m hort_ia.knowledge` to print a completeness report.
"""

from __future__ import annotations

import csv
import json
import os
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import (
    Companion,
    Crop,
    Guideline,
    KnowledgeBase,
    PestDisease,
    Source,
    ValidationStatus,
)

# src/hort_ia/knowledge/loader.py -> repository root is parents[3]
DEFAULT_KB_DIR = Path(__file__).resolve().parents[3] / "data" / "knowledge"


def kb_dir() -> Path:
    return Path(os.environ.get("HORTIA_KB_DIR", DEFAULT_KB_DIR))


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


def _read_companions(path: Path) -> list[Companion]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return [
        Companion(**{key: (value.strip() or None) for key, value in row.items()})
        for row in rows
    ]


def load_knowledge_base(directory: Path | None = None) -> KnowledgeBase:
    directory = directory or kb_dir()
    sources = [Source(**s) for s in _read_json_list(directory / "sources.json")]
    crops = [Crop(**c) for c in _read_json_list(directory / "crops.json")]
    guidelines = [Guideline(**g) for g in _read_json_list(directory / "guidelines.json")]
    pests = [PestDisease(**p) for p in _read_json_list(directory / "pests_diseases.json")]
    return KnowledgeBase(
        sources=_index_unique(sources, "sources.json"),
        crops=_index_unique(crops, "crops.json"),
        guidelines=_index_unique(guidelines, "guidelines.json"),
        pests_diseases=_index_unique(pests, "pests_diseases.json"),
        companions=_read_companions(directory / "companions.csv"),
    )


@lru_cache(maxsize=1)
def get_knowledge_base() -> KnowledgeBase:
    """Cached instance for the FastAPI app (use as a dependency)."""
    return load_knowledge_base()


def completeness_report(kb: KnowledgeBase) -> str:
    lines: list[str] = []
    for title, records in (("Crops", kb.crops), ("Pests/diseases", kb.pests_diseases)):
        status = Counter(r.validation_status for r in records.values())
        lines.append(
            f"{title}: {len(records)} records | "
            + " | ".join(f"{s.value}: {status.get(s, 0)}" for s in ValidationStatus)
        )
        for record in records.values():
            if missing := record.missing_fields():
                lines.append(f"  - {record.id}: {', '.join(missing)}")
    ready = [
        r.id
        for records in (kb.crops, kb.pests_diseases)
        for r in records.values()
        if r.validation_status == ValidationStatus.DRAFT and not r.missing_fields()
    ]
    lines.append(f"Complete drafts awaiting review ({len(ready)}): {', '.join(ready)}")
    lines.append(f"Guidelines: {len(kb.guidelines)}")
    evidence = Counter(c.evidence for c in kb.companions)
    lines.append(
        f"Companion relations: {len(kb.companions)} | "
        + " | ".join(f"{e}: {n}" for e, n in sorted(evidence.items()))
    )
    without = [c for c in kb.crops if not kb.companions_of(c)]
    if without:
        lines.append(f"  crops without companion relations: {', '.join(without)}")
    unverified = [s.id for s in kb.sources.values() if not s.verified]
    lines.append(f"Unverified sources ({len(unverified)}): {', '.join(unverified)}")
    return "\n".join(lines)

