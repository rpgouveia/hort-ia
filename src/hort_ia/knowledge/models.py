"""Pydantic models for the Hort.IA agronomic knowledge base.

Every record carries `sources` (traceability) and `validation_status`, so the
knowledge base can be aligned later with the Technical Assistance team: records
stay as `draft` until reviewed, and only reviewed records must be complete.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ID_PATTERN = r"^[a-z][a-z0-9_]*$"


class ValidationStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    VALIDATED_BY_ATD = "validated_by_atd"


class Region(StrEnum):
    NORTE = "norte"
    NORDESTE = "nordeste"
    CENTRO_OESTE = "centro_oeste"
    SUDESTE = "sudeste"
    SUL = "sul"


class CropGroup(StrEnum):
    """Grouping by edible part (Embrapa CT 47, p. 2)."""

    LEAFY = "leafy"
    FLOWER = "flower"
    FRUIT = "fruit"
    TUBER = "tuber"
    ROOT = "root"
    BULB = "bulb"
    RHIZOME = "rhizome"
    STEM = "stem"
    CONDIMENT = "condiment"


class Propagation(StrEnum):
    SEEDLING = "seedling"  # transplanted seedlings (mudas)
    DIRECT = "direct"  # direct seeding or planting material in the bed


class FrostTolerance(StrEnum):
    NONE = "none"
    LIGHT = "light"
    TOLERANT = "tolerant"


class YieldUnit(StrEnum):
    KG = "kg"
    PLANTS = "plants"  # "pés"
    BUNCHES = "bunches"  # "molhos"


class EntryType(StrEnum):
    DISEASE = "disease"
    PEST = "pest"
    HEALTHY = "healthy"


class ManagementType(StrEnum):
    PREVENTIVE = "preventive"
    CULTURAL = "cultural"
    BIOLOGICAL = "biological"
    ALTERNATIVE = "alternative"


class CompanionRelation(StrEnum):
    HELPS = "helps"
    HARMS = "harms"


class Evidence(StrEnum):
    """How well supported a statement is, from strongest to weakest."""

    TECHNICAL = "technical"  # official technical publication (e.g. Embrapa)
    RESEARCH = "research"  # field trial or peer-reviewed study
    TRADITIONAL = "traditional"  # gardening tradition (e.g. Wikipedia list)


class CompanionMechanism(StrEnum):
    PEST_REPELLENT = "pest_repellent"
    BENEFICIAL_HABITAT = "beneficial_habitat"  # shelter for natural enemies, pollinators
    SPACE_USE = "space_use"  # intercropping that uses space/time better
    ALLELOPATHY = "allelopathy"
    COMPETITION = "competition"
    SHARED_PESTS = "shared_pests"
    UNKNOWN = "unknown"


class CompanionRoleType(StrEnum):
    PEST_REPELLENT = "pest_repellent"


class KBModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- Sources -----------------------------------------------------------------


class Source(KBModel):
    id: str = Field(pattern=ID_PATTERN)
    title: str
    publisher: str
    year: int | None = None
    url: str | None = None
    license: str | None = None
    verified: bool = False  # existence and license confirmed by the team
    notes: str | None = None


class SourceRef(KBModel):
    source_id: str
    pages: str | None = None  # e.g. "45" or "45-47"


# --- Crops -------------------------------------------------------------------


class IntRange(KBModel):
    min: int = Field(ge=0)
    max: int = Field(ge=0)

    @model_validator(mode="after")
    def _min_le_max(self) -> Self:
        if self.min > self.max:
            raise ValueError(f"min ({self.min}) is greater than max ({self.max})")
        return self


class TempRange(KBModel):
    """Optimal temperature in °C; sources sometimes give only an upper bound."""

    min: float | None = None
    max: float | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.min is None and self.max is None:
            raise ValueError("temperature range needs min or max")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"min ({self.min}) is greater than max ({self.max})")
        return self


class PlantingWindow(KBModel):
    """Recommended planting months per region for one cultivar type.

    A region mapped to [] means the source marks it as "não recomendável";
    a region absent from the dict means the source has no data for it.
    """

    variant: str | None = None  # e.g. "inverno", "verao" (cultivar type)
    months_by_region: dict[Region, list[int]]
    harvest_start_days: IntRange  # "início de colheita (após o plantio)"
    source: SourceRef
    notes: str | None = None  # interpretation of the source, secondary sources

    @field_validator("months_by_region")
    @classmethod
    def _valid_months(cls, value: dict[Region, list[int]]) -> dict[Region, list[int]]:
        if not value:
            raise ValueError("planting window without regions")
        for region, months in value.items():
            if any(m < 1 or m > 12 for m in months):
                raise ValueError(f"months must be between 1 and 12 (region '{region}')")
            if len(set(months)) != len(months):
                raise ValueError(f"duplicate months for region '{region}'")
        return value


class SpacingCm(KBModel):
    between_rows_cm: int = Field(gt=0)
    between_plants_cm: int = Field(gt=0)


class Spacing(KBModel):
    conventional: SpacingCm
    small_spaces: SpacingCm | None = None  # "horta em pequenos espaços" (~70% of conventional)
    source: SourceRef


class YieldEstimate(KBModel):
    min: float = Field(gt=0)
    max: float = Field(gt=0)
    unit: YieldUnit
    area_m2: float = Field(default=10, gt=0)
    source: SourceRef


class CompanionRole(KBModel):
    """A role the crop plays for the garden as a whole, not for a specific partner."""

    role: CompanionRoleType
    evidence: Evidence
    source: SourceRef


class Crop(KBModel):
    id: str = Field(pattern=ID_PATTERN)
    name_pt: str
    scientific_name: str
    family: str
    aliases: list[str] = []
    names_en: list[str] = []  # used to map the English companion-planting datasets
    crop_groups: list[CropGroup] = []
    propagation: list[Propagation] = []
    seedling_days: IntRange | None = None  # days to produce seedlings before transplant
    planting_windows: list[PlantingWindow] = []
    spacing: Spacing | None = None
    optimal_temp_c: TempRange | None = None
    frost_tolerance: FrostTolerance | None = None
    small_space_recommended: bool | None = None
    yield_estimate: YieldEstimate | None = None
    companion_roles: list[CompanionRole] = []  # role in the garden as a whole
    sources: list[SourceRef] = []  # sources for the descriptive fields
    validation_status: ValidationStatus = ValidationStatus.DRAFT
    notes: str | None = None

    @field_validator("planting_windows")
    @classmethod
    def _no_overlapping_windows(cls, value: list[PlantingWindow]) -> list[PlantingWindow]:
        """A crop may combine windows from several sources, but each
        (variant, region) pair must be defined by exactly one of them."""
        seen: set[tuple[str | None, Region]] = set()
        for window in value:
            for region in window.months_by_region:
                key = (window.variant, region)
                if key in seen:
                    raise ValueError(f"region '{region}' defined twice for variant '{window.variant}'")
                seen.add(key)
        return value

    def all_source_refs(self) -> list[SourceRef]:
        refs = list(self.sources)
        refs += [w.source for w in self.planting_windows]
        if self.spacing:
            refs.append(self.spacing.source)
        if self.yield_estimate:
            refs.append(self.yield_estimate.source)
        refs += [r.source for r in self.companion_roles]
        return refs

    def missing_fields(self) -> list[str]:
        """Fields that must be filled before the record leaves `draft`."""
        missing = []
        if not self.crop_groups:
            missing.append("crop_groups")
        if not self.propagation:
            missing.append("propagation")
        if not self.planting_windows:
            missing.append("planting_windows")
        if self.spacing is None:
            missing.append("spacing")
        if not self.sources:
            missing.append("sources")
        return missing

    @model_validator(mode="after")
    def _complete_unless_draft(self) -> Self:
        if self.validation_status != ValidationStatus.DRAFT and (missing := self.missing_fields()):
            raise ValueError(
                f"crop '{self.id}' is '{self.validation_status}' but is missing: {', '.join(missing)}"
            )
        return self


# --- General guidelines --------------------------------------------------------


class Guideline(KBModel):
    """Cross-crop rule from a source (sun exposure, irrigation, soil...)."""

    id: str = Field(pattern=ID_PATTERN)
    topic: str
    statement_pt: str  # paraphrased, never copied verbatim from the source
    applies_to_groups: list[CropGroup] = []  # empty (and no crops) = all crops
    applies_to_crops: list[str] = []  # crop-specific rule (takes precedence over group rules)
    values: dict[str, float | int | str] = {}
    source: SourceRef
    validation_status: ValidationStatus = ValidationStatus.DRAFT


# --- Pests and diseases ------------------------------------------------------


class ManagementAction(KBModel):
    type: ManagementType
    description: str
    source: SourceRef


class PestDisease(KBModel):
    id: str = Field(pattern=ID_PATTERN)
    cv_dataset: Literal["new_plant_diseases_dataset", "agricultural_pests_dataset"]
    cv_label: str  # exact class name produced by the CV model
    type: EntryType
    name_pt: str | None = None
    causal_agent: str | None = None
    crop_ids: list[str] = []  # empty = generic (not tied to a crop)
    beneficial: bool | None = None  # pests only; True = never recommend control
    symptoms: str | None = None
    management: list[ManagementAction] = []
    sources: list[SourceRef] = []
    validation_status: ValidationStatus = ValidationStatus.DRAFT
    notes: str | None = None

    def missing_fields(self) -> list[str]:
        if self.type == EntryType.HEALTHY:
            return []
        missing = []
        if self.name_pt is None:
            missing.append("name_pt")
        if self.symptoms is None:
            missing.append("symptoms")
        if self.type == EntryType.PEST and self.beneficial is None:
            missing.append("beneficial")
        if not self.beneficial and not self.management:
            missing.append("management")
        if not self.sources:
            missing.append("sources")
        return missing

    @model_validator(mode="after")
    def _consistency(self) -> Self:
        if self.type != EntryType.PEST and self.beneficial is not None:
            raise ValueError(f"'{self.id}': 'beneficial' only applies to pests")
        if self.beneficial and self.management:
            raise ValueError(f"'{self.id}' is beneficial and must not have control actions")
        if self.validation_status != ValidationStatus.DRAFT and (missing := self.missing_fields()):
            raise ValueError(
                f"'{self.id}' is '{self.validation_status}' but is missing: {', '.join(missing)}"
            )
        return self


# --- Companion planting ------------------------------------------------------


class Companion(KBModel):
    """`crop_a` helps/harms `crop_b`; with `mutual`, the relation holds both ways."""

    crop_a: str
    crop_b: str
    relation: CompanionRelation
    mutual: bool = False
    mechanism: CompanionMechanism = CompanionMechanism.UNKNOWN
    evidence: Evidence
    source_id: str
    pages: str | None = None
    validation_status: ValidationStatus = ValidationStatus.DRAFT
    notes: str | None = None

    @model_validator(mode="after")
    def _distinct_crops(self) -> Self:
        if self.crop_a == self.crop_b:
            raise ValueError(f"companion relation with itself: '{self.crop_a}'")
        return self

    def involves(self, crop_a: str, crop_b: str) -> bool:
        """True if this relation applies from `crop_a` to `crop_b`."""
        if (self.crop_a, self.crop_b) == (crop_a, crop_b):
            return True
        return self.mutual and (self.crop_b, self.crop_a) == (crop_a, crop_b)


# --- Aggregate ---------------------------------------------------------------


class KnowledgeBase(KBModel):
    sources: dict[str, Source]
    crops: dict[str, Crop]
    guidelines: dict[str, Guideline]
    pests_diseases: dict[str, PestDisease]
    companions: list[Companion]

    @model_validator(mode="after")
    def _referential_integrity(self) -> Self:
        errors: list[str] = []

        def check_source(ref_id: str, owner: str) -> None:
            if ref_id not in self.sources:
                errors.append(f"{owner}: unknown source '{ref_id}'")

        def check_crop(crop_id: str, owner: str) -> None:
            if crop_id not in self.crops:
                errors.append(f"{owner}: unknown crop '{crop_id}'")

        for crop in self.crops.values():
            for ref in crop.all_source_refs():
                check_source(ref.source_id, f"crop '{crop.id}'")

        for guideline in self.guidelines.values():
            check_source(guideline.source.source_id, f"guideline '{guideline.id}'")
            for crop_id in guideline.applies_to_crops:
                check_crop(crop_id, f"guideline '{guideline.id}'")

        labels: set[tuple[str, str]] = set()
        for entry in self.pests_diseases.values():
            owner = f"pest_disease '{entry.id}'"
            key = (entry.cv_dataset, entry.cv_label)
            if key in labels:
                errors.append(f"{owner}: duplicate cv_label '{entry.cv_label}'")
            labels.add(key)
            for crop_id in entry.crop_ids:
                check_crop(crop_id, owner)
            for ref in entry.sources:
                check_source(ref.source_id, owner)
            for action in entry.management:
                check_source(action.source.source_id, owner)

        pairs: set[tuple[tuple[str, ...], str]] = set()
        for i, comp in enumerate(self.companions, start=2):  # CSV line number
            owner = f"companions.csv line {i}"
            check_crop(comp.crop_a, owner)
            check_crop(comp.crop_b, owner)
            check_source(comp.source_id, owner)
            pair = tuple(sorted((comp.crop_a, comp.crop_b)))
            key = (pair, comp.source_id)
            if key in pairs:
                errors.append(f"{owner}: pair {pair} appears twice for source '{comp.source_id}'")
            pairs.add(key)

        if errors:
            raise ValueError("referential integrity errors:\n- " + "\n- ".join(errors))
        return self

    def companions_of(self, crop_id: str) -> list[Companion]:
        """Relations in which `crop_id` affects or is affected by another crop."""
        return [c for c in self.companions if crop_id in (c.crop_a, c.crop_b)]

    def by_cv_label(self, cv_label: str) -> PestDisease | None:
        """Resolve a CV model output to its knowledge base entry."""
        return next((e for e in self.pests_diseases.values() if e.cv_label == cv_label), None)
