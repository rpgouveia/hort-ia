"""Pydantic models for the Hort.IA agronomic knowledge base.

Every record carries `sources` (traceability) and `validation_status`:

- `draft`: curated by the AI module, not yet checked by anyone else;
- `validated_by_atd`: checked by the Digital Technical Assistance team (ATD) against the cited source
  and page. It is NOT an agronomic endorsement (the ATD has no licensed professional), so consumers
  treat it like `draft`: it does not release homemade preparations nor remove the handoff;
- `reviewed`: endorsed by an agronomist. Only `reviewed` records must be complete, and only they
  release the full pest management in the assistant.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..core.geo import Region
from ..core.sources import ID_PATTERN, Source, SourceRef


class ValidationStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    VALIDATED_BY_ATD = "validated_by_atd"


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
    BENEFICIAL = "beneficial"  # natural enemy (e.g. wasps): never recommend control


class CropScope(StrEnum):
    """Which crops a pest or disease entry covers."""

    ALL_VEGETABLES = "all_vegetables"  # the source speaks of vegetables in general (crop_ids stays empty)
    SPECIFIC = "specific"  # the crops listed in crop_ids


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


class SunRequirement(StrEnum):
    FULL_SUN = "full_sun"


class KBModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


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
    notes: str | None = None


# Crop facts added with the ATD delivery v3 (germination, irrigation, soil, sun, rotation...). They
# share one rule: every filled value needs a `source` with a page, and a block with no value must say
# in `notes` where the search was made and why there is nothing (so nobody repeats the same search).


def _has_page(ref: SourceRef | None) -> bool:
    return ref is not None and bool(ref.pages and ref.pages.strip())


class SourcedFacts(KBModel):
    """Base of the crop fact blocks: subclasses declare the value fields and the (min, max) pairs."""

    source: SourceRef | None = None
    notes: str | None = None

    NOT_VALUES: ClassVar[frozenset[str]] = frozenset({"source", "notes", "alt_source"})
    RANGES: ClassVar[tuple[tuple[str, str], ...]] = ()

    def filled(self) -> list[str]:
        """Value fields with data (an empty list counts as no data)."""
        return [
            name
            for name in type(self).model_fields
            if name not in self.NOT_VALUES and getattr(self, name) not in (None, [])
        ]

    @model_validator(mode="after")
    def _sourced_or_explained(self) -> Self:
        if self.filled() and not _has_page(self.source):
            raise ValueError(f"{', '.join(self.filled())} filled without a source with page")
        if not self.filled() and not (self.notes and self.notes.strip()):
            raise ValueError("block without values must explain the gap in 'notes'")
        for low, high in self.RANGES:
            a, b = getattr(self, low), getattr(self, high)
            if a is not None and b is not None and a > b:
                raise ValueError(f"{low} ({a}) is greater than {high} ({b})")
        return self


class GerminationAltSource(KBModel):
    """Values of a source that lost a conflict, kept for traceability (not used by consumers)."""

    source: SourceRef
    temp_min_c: float | None = None
    temp_max_c: float | None = None
    temp_ideal_min_c: float | None = None
    temp_ideal_max_c: float | None = None
    soil_temp_ideal_min_c: float | None = None
    soil_temp_ideal_max_c: float | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _page(self) -> Self:
        if not _has_page(self.source):
            raise ValueError("alt_source needs a source with page")
        return self


class Germination(SourcedFacts):
    temp_min_c: float | None = None
    temp_max_c: float | None = None
    temp_ideal_c: float | None = None  # single optimum, when the source gives one
    temp_ideal_min_c: float | None = None
    temp_ideal_max_c: float | None = None
    emergence_days_min: int | None = Field(default=None, ge=0)
    emergence_days_max: int | None = Field(default=None, ge=0)
    alt_source: GerminationAltSource | None = None

    RANGES = (
        ("temp_min_c", "temp_max_c"),
        ("temp_ideal_min_c", "temp_ideal_max_c"),
        ("emergence_days_min", "emergence_days_max"),
    )


class SowingDepth(SourcedFacts):
    min: float | None = Field(default=None, ge=0)
    max: float | None = Field(default=None, ge=0)

    RANGES = (("min", "max"),)


class Irrigation(SourcedFacts):
    turn_days_min: int | None = Field(default=None, ge=0)
    turn_days_max: int | None = Field(default=None, ge=0)
    blade_mm_net: float | None = Field(default=None, ge=0)  # lâmina líquida por rega
    blade_mm_gross: float | None = Field(default=None, ge=0)  # lâmina bruta por rega
    efficiency: float | None = Field(default=None, gt=0, le=1)  # efficiency of the irrigation system
    blade_mm_mild: str | None = Field(default=None, pattern=r"^\d+([.,]\d+)?(-\d+([.,]\d+)?)?$")  # e.g. "5-6"
    blade_mm_hot: str | None = Field(default=None, pattern=r"^\d+([.,]\d+)?(-\d+([.,]\d+)?)?$")
    season_total_mm_min: float | None = Field(default=None, ge=0)  # water need per cycle
    season_total_mm_max: float | None = Field(default=None, ge=0)
    root_zone_depth_cm: float | None = Field(default=None, gt=0)
    first_irrigation_wet_depth_cm: float | None = Field(default=None, gt=0)
    preplant_blade_mm: float | None = Field(default=None, ge=0)
    kc_initial: float | None = Field(default=None, gt=0)  # crop coefficients
    kc_mid: float | None = Field(default=None, gt=0)
    kc_final: float | None = Field(default=None, gt=0)
    nursery_liters_m2_min: float | None = Field(default=None, ge=0)
    nursery_liters_m2_max: float | None = Field(default=None, ge=0)

    RANGES = (
        ("turn_days_min", "turn_days_max"),
        ("season_total_mm_min", "season_total_mm_max"),
        ("nursery_liters_m2_min", "nursery_liters_m2_max"),
    )


class SoilPh(SourcedFacts):
    min: float | None = Field(default=None, ge=0, le=14)
    max: float | None = Field(default=None, ge=0, le=14)

    RANGES = (("min", "max"),)


class Sun(SourcedFacts):
    requirement: SunRequirement | None = None
    hours_min: float | None = Field(default=None, ge=0, le=24)
    max_radiation_mj_m2_dia: float | None = Field(default=None, gt=0)  # radiation, not hours of sun


class Rotation(SourcedFacts):
    """Rotation by botanical family (CT 47, pp. 10-11), materialized per crop."""

    rotation_group: str  # the botanical family
    avoid_after: list[str] = []  # crops of this base in the same family (checked against `family`)


class DevTemp(SourcedFacts):
    """Air temperature for plant development (°C)."""

    before_head_min_c: float | None = None  # brócolis: before / after the head forms
    before_head_max_c: float | None = None
    after_head_min_c: float | None = None
    after_head_max_c: float | None = None
    ideal_min_c: float | None = None
    ideal_max_c: float | None = None
    min_c: float | None = None
    max_c: float | None = None
    alt_range_min_c: float | None = None  # range from a second study, explained in notes
    alt_range_max_c: float | None = None

    RANGES = (
        ("before_head_min_c", "before_head_max_c"),
        ("after_head_min_c", "after_head_max_c"),
        ("ideal_min_c", "ideal_max_c"),
        ("min_c", "max_c"),
        ("alt_range_min_c", "alt_range_max_c"),
    )


class SoilTemp(SourcedFacts):
    """Soil temperature (°C)."""

    ideal_min_c: float | None = None
    ideal_max_c: float | None = None
    max_c: float | None = None
    root_damage_above_c: float | None = None

    RANGES = (("ideal_min_c", "ideal_max_c"),)


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
    # Facts added with the ATD delivery v3; not used by the engine nor the assistant yet.
    germination: Germination | None = None
    sowing_depth_cm: SowingDepth | None = None
    irrigation: Irrigation | None = None
    soil_ph: SoilPh | None = None
    sun: Sun | None = None
    rotation: Rotation | None = None
    dev_temp: DevTemp | None = None
    soil_temp: SoilTemp | None = None
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

    def planting_months(self, region: Region | str) -> dict[str | None, list[int]] | None:
        """Planting months in `region`, by cultivar type (variant).

        Returns None when no source covers the region; a variant mapped to [] means
        the source marks the region as "não recomendável" for it.
        """
        found = {
            w.variant: w.months_by_region[Region(region)]
            for w in self.planting_windows
            if Region(region) in w.months_by_region
        }
        return found or None

    def all_source_refs(self) -> list[SourceRef]:
        refs = list(self.sources)
        refs += [w.source for w in self.planting_windows]
        if self.spacing:
            refs.append(self.spacing.source)
        if self.yield_estimate:
            refs.append(self.yield_estimate.source)
        refs += [r.source for r in self.companion_roles]
        for block in self.fact_blocks():
            if block.source:
                refs.append(block.source)
            if isinstance(block, Germination) and block.alt_source:
                refs.append(block.alt_source.source)
        return refs

    def fact_blocks(self) -> list[SourcedFacts]:
        blocks = (self.germination, self.sowing_depth_cm, self.irrigation, self.soil_ph, self.sun,
                  self.rotation, self.dev_temp, self.soil_temp)  # fmt: skip
        return [b for b in blocks if b is not None]

    def missing_fields(self) -> list[str]:
        """Fields that must be filled before the record is `reviewed`."""
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
    def _complete_when_reviewed(self) -> Self:
        # Only an agronomist's review demands a complete record: `validated_by_atd` means "checked
        # against the source", and a checked record may still have gaps (e.g. hortelã has no window).
        if self.validation_status == ValidationStatus.REVIEWED and (missing := self.missing_fields()):
            raise ValueError(f"crop '{self.id}' is '{self.validation_status}' but is missing: {', '.join(missing)}")
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
    notes: str | None = None


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
    crop_scope: CropScope | None = None  # all_vegetables requires crop_ids empty; specific requires crop_ids
    beneficial: bool | None = None  # pests and beneficial entries; True = never recommend control
    symptoms: str | None = None
    symptoms_sources: list[SourceRef] = []  # also listed in `sources`; required whenever `symptoms` is set
    management: list[ManagementAction] = []
    sources: list[SourceRef] = []
    validation_status: ValidationStatus = ValidationStatus.DRAFT
    notes: str | None = None

    @property
    def is_beneficial(self) -> bool:
        """Natural enemy: `type` beneficial (ATD v3) or a pest marked `beneficial: true`."""
        return self.type == EntryType.BENEFICIAL or self.beneficial is True

    def missing_fields(self) -> list[str]:
        """Fields that must be filled before the entry is `reviewed`."""
        if self.type == EntryType.HEALTHY:
            return []
        missing = []
        if self.name_pt is None:
            missing.append("name_pt")
        if self.symptoms is None:
            missing.append("symptoms")
        if self.type == EntryType.PEST and self.beneficial is None:
            missing.append("beneficial")
        if not self.is_beneficial and not self.management:
            missing.append("management")
        if not self.sources:
            missing.append("sources")
        return missing

    @model_validator(mode="after")
    def _consistency(self) -> Self:
        if self.type not in (EntryType.PEST, EntryType.BENEFICIAL) and self.beneficial is not None:
            raise ValueError(f"'{self.id}': 'beneficial' only applies to pests and beneficial entries")
        if self.type == EntryType.BENEFICIAL and self.beneficial is False:
            raise ValueError(f"'{self.id}': type 'beneficial' with beneficial=false")
        if self.is_beneficial and self.management:
            raise ValueError(f"'{self.id}' is beneficial and must not have control actions")
        if self.symptoms and not self.symptoms_sources:  # any status: the assistant shows symptoms
            raise ValueError(f"'{self.id}' has symptoms without symptoms_sources")
        if self.crop_scope == CropScope.ALL_VEGETABLES and self.crop_ids:
            raise ValueError(f"'{self.id}': crop_scope 'all_vegetables' must leave crop_ids empty")
        if self.crop_scope == CropScope.SPECIFIC and not self.crop_ids:
            raise ValueError(f"'{self.id}': crop_scope 'specific' needs crop_ids")
        # Only an agronomist's review demands a complete entry; `validated_by_atd` keeps the gaps
        # the ATD could not fill (e.g. ants and beetles still without a pest/beneficial decision).
        if self.validation_status == ValidationStatus.REVIEWED and (missing := self.missing_fields()):
            raise ValueError(f"'{self.id}' is '{self.validation_status}' but is missing: {', '.join(missing)}")
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
            for other in crop.rotation.avoid_after if crop.rotation else []:
                check_crop(other, f"crop '{crop.id}' rotation")

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
            for ref in [*entry.sources, *entry.symptoms_sources]:
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
        """All relations in which `crop_id` affects or is affected by another crop (raw, for reports).

        Consumers that show or score relations must use `usable_companions_of` instead."""
        return [c for c in self.companions if crop_id in (c.crop_a, c.crop_b)]

    def is_usable(self, relation: Companion) -> bool:
        """Whether a relation may reach an automatic output (decision D6 of the ATD v3 integration).

        Kept in the base but withheld until the ATD confirms them:
        - `research` relations: the ones received are germination tests with plant extracts in a Petri
          dish, without growing the plants together, so they say nothing about planting side by side;
        - relations whose source is not registered as verified (title, publisher and license confirmed).
        This is the single point every consumer goes through (engine score, reasons and warnings,
        assistant and the companion-crops route), so the routes keep agreeing with each other.
        """
        source = self.sources.get(relation.source_id)
        return relation.evidence != Evidence.RESEARCH and source is not None and source.verified

    def usable_companions(self) -> list[Companion]:
        return [c for c in self.companions if self.is_usable(c)]

    def usable_companions_of(self, crop_id: str) -> list[Companion]:
        return [c for c in self.companions_of(crop_id) if self.is_usable(c)]

    def by_cv_label(self, cv_label: str) -> PestDisease | None:
        """Resolve a CV model output to its knowledge base entry."""
        return next((e for e in self.pests_diseases.values() if e.cv_label == cv_label), None)
