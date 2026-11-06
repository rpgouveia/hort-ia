"""Input and output contract of the recommendation engine (9.3.1-3, sections 4.1 and 5)."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.geo import Region


class RecommenderError(ValueError):
    """Invalid profile; the API turns it into 422."""


class ReasonCode(StrEnum):
    IN_SEASON = "in_season"
    SEASON_ENDING = "season_ending"
    COMPANION_GOOD = "companion_good"
    PEST_REPELLENT = "pest_repellent"
    COMPANION_BAD = "companion_bad"  # used in `warnings`


class ExclusionReason(StrEnum):
    """Filters F1 to F5 of section 4.2, in the order they are applied."""

    NO_REGION_DATA = "no_region_data"
    OUT_OF_SEASON = "out_of_season"
    NOT_FOR_SMALL_SPACE = "not_for_small_space"
    NO_SMALL_SPACE_INFO = "no_small_space_info"
    ALREADY_PLANTED = "already_planted"
    SAME_FAMILY_AS_PREVIOUS = "same_family_as_previous"


class Profile(BaseModel):
    """What the platform knows about the garden. Section 4.1."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ibge_code: int | str | None = None  # municipality (7 digits) or UF (2 digits); wins over `region`
    region: Region | None = None
    month: int = Field(ge=1, le=12)
    small_space: bool = False
    planted: list[str] = []  # crops in the garden now
    previous_crop: str | None = None  # last crop of the bed where the user will plant

    @model_validator(mode="after")
    def _location(self) -> Self:
        if self.ibge_code is None and self.region is None:
            raise ValueError("informe 'ibge_code' ou 'region'")
        return self


class Reason(BaseModel):
    code: ReasonCode
    text: str
    source: str | None = None  # human-readable citation, as in the conversational assistant


class Exclusion(BaseModel):
    crop_id: str
    reason: ExclusionReason


class RecommendedCrop(BaseModel):
    rank: int
    crop_id: str
    crop_name_pt: str
    score: float
    variants: list[str] = []  # cultivar types in season ("verao"); empty when the crop has none
    reasons: list[Reason]
    warnings: list[Reason] = []


class RecommendationResult(BaseModel):
    region: Region
    month: int
    small_space: bool
    recommendations: list[RecommendedCrop]
    excluded: list[Exclusion]
    warnings: list[str] = []
    approach: str = "knowledge_based"
    model_version: str
