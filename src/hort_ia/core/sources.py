"""Source models shared by the Hort.IA datasets.

Each dataset (agronomic knowledge base, market...) keeps its own `sources.json`
registry, but all of them describe and cite sources with these models.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

ID_PATTERN = r"^[a-z][a-z0-9_]*$"


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=ID_PATTERN)
    title: str
    publisher: str
    year: int | None = None
    url: str | None = None
    license: str | None = None
    verified: bool = False  # existence and license confirmed by the team
    notes: str | None = None


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    pages: str | None = None  # e.g. "45" or "45-47"
