"""Knowledge-based recommendation engine (WBS 9.3.1-4), implementing section 4 of 9.3.1-3.

Given a garden profile, returns the crops worth planting now, best first, each with the rules that
put it there and their sources. Hard filters remove what cannot be planted (wrong season or region,
too little space, same family as the previous crop of the bed); a rule-based score orders the rest
by companion relations with what is already planted.

Deterministic and stateless: the same profile always gives the same list, and nothing is stored.
Nothing is learned: there is no interaction history to learn from (study 9.3.1-1/-2, section 4).
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from ..core.calendar import format_months
from ..core.geo import Region, region_from_ibge_code
from ..core.sources import SourceRef
from ..knowledge import KnowledgeBase, get_knowledge_base
from ..knowledge.models import CompanionRelation, CompanionRoleType, Crop, Evidence
from .models import (
    Exclusion,
    ExclusionReason,
    Profile,
    Reason,
    ReasonCode,
    RecommendationResult,
    RecommendedCrop,
    RecommenderError,
)

# 1.1.0: relations withheld by decision D6 (research evidence or unverified source) no longer score.
MODEL_VERSION = "1.1.0"  # bump when a filter, a weight or the ordering changes (9.3.1-3, section 5)

# Section 4.3. Parameters, not learned: recalibrate them in the UAT (9.3.2-5).
W_COMPANION = 1.0  # per planted crop with a favorable (+) or unfavorable (-) relation
W_REPELLENT = 0.5  # pest-repellent crop, only when something is already planted
SEASON_ENDING_MONTHS = 2  # "a época termina em ..." when this many months or fewer are left

TEXTS_PATH = Path(__file__).with_name("texts.yaml")


def load_texts(path: Path | None = None) -> dict:
    with (path or TEXTS_PATH).open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def months_left(months: list[int], month: int) -> int:
    """Consecutive months from `month` that are still in the window (12 = all year)."""
    n, m = 0, month
    while m in months and n < 12:
        n, m = n + 1, m % 12 + 1
    return n


def _sort_key(text: str) -> str:
    """Accent-insensitive key, so ties are broken in dictionary order."""
    return "".join(ch for ch in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(ch))


@dataclass
class _Candidate:
    crop: Crop
    variants: list[str | None]
    months_left: int
    window_end: int | None  # last month of the run in season; None when the crop can be planted all year
    windows: list[tuple[str | None, list[int], SourceRef]]
    good: list[tuple[str, Evidence, str | None]] = field(default_factory=list)  # (partner, evidence, source)
    bad: list[tuple[str, Evidence, str | None]] = field(default_factory=list)
    repellent: bool = False

    @property
    def score(self) -> float:
        return W_COMPANION * (len(self.good) - len(self.bad)) + (W_REPELLENT if self.repellent else 0.0)


class Recommender:
    """Recommends crops for a garden profile. Build once and reuse (the companion index is precomputed)."""

    def __init__(self, kb: KnowledgeBase, texts: dict | None = None):
        self.kb = kb
        self.t = texts or load_texts()
        # One relation per unordered pair; an unfavorable record would win over a favorable one
        # (section 4.3). The current base has no such conflict. Only usable relations count (decision
        # D6: research evidence and unverified sources stay in the base, out of the score and reasons).
        self._pairs: dict[frozenset[str], tuple[CompanionRelation, Evidence, str | None]] = {}
        by_pair = defaultdict(list)
        for rel in kb.usable_companions():
            by_pair[frozenset((rel.crop_a, rel.crop_b))].append(rel)
        for pair, rels in by_pair.items():
            rel = next((r for r in rels if r.relation == CompanionRelation.HARMS), rels[0])
            self._pairs[pair] = (
                rel.relation,
                rel.evidence,
                self._cite(SourceRef(source_id=rel.source_id, pages=rel.pages)),
            )

    # --- public API ------------------------------------------------------------------

    def recommend(self, profile: Profile) -> RecommendationResult:
        region = self._region(profile)
        warnings: list[str] = []
        planted = list(dict.fromkeys(profile.planted))  # dedupe, keep order
        for crop_id in planted:
            if crop_id not in self.kb.crops:
                warnings.append(self.t["warnings"]["unknown_planted"].format(crop=crop_id))
        planted = [c for c in planted if c in self.kb.crops]
        previous = profile.previous_crop
        if previous is not None and previous not in self.kb.crops:
            warnings.append(self.t["warnings"]["unknown_previous"].format(crop=previous))
            previous = None
        previous_family = self.kb.crops[previous].family if previous else None

        candidates, excluded = [], []
        for crop in self.kb.crops.values():
            reason = self._exclusion(crop, region, profile.month, profile.small_space, planted, previous_family)
            if reason is not None:
                excluded.append(Exclusion(crop_id=crop.id, reason=reason))
                continue
            candidates.append(self._candidate(crop, region, profile.month, planted))

        # Section 4.4: score, then the season that ends first, then the name.
        candidates.sort(key=lambda c: (-c.score, c.months_left, _sort_key(c.crop.name_pt)))
        return RecommendationResult(
            region=region,
            month=profile.month,
            small_space=profile.small_space,
            recommendations=[self._item(rank, c, region) for rank, c in enumerate(candidates, 1)],
            excluded=excluded,
            warnings=warnings,
            model_version=MODEL_VERSION,
        )

    # --- steps -----------------------------------------------------------------------

    @staticmethod
    def _region(profile: Profile) -> Region:
        if profile.ibge_code is not None:
            try:
                return region_from_ibge_code(profile.ibge_code)
            except ValueError as err:
                raise RecommenderError(f"código IBGE inválido: {err}") from err
        return Region(profile.region)

    def _exclusion(
        self,
        crop: Crop,
        region: Region,
        month: int,
        small_space: bool,
        planted: list[str],
        previous_family: str | None,
    ) -> ExclusionReason | None:
        """Filters F1 to F5 of section 4.2; the first one that applies is the reason."""
        by_variant = crop.planting_months(region)
        if by_variant is None:
            return ExclusionReason.NO_REGION_DATA
        if not any(month in months for months in by_variant.values()):
            return ExclusionReason.OUT_OF_SEASON
        if small_space and crop.small_space_recommended is not True:
            if crop.small_space_recommended is False:
                return ExclusionReason.NOT_FOR_SMALL_SPACE
            return ExclusionReason.NO_SMALL_SPACE_INFO
        if crop.id in planted:
            return ExclusionReason.ALREADY_PLANTED
        if previous_family is not None and crop.family == previous_family:
            return ExclusionReason.SAME_FAMILY_AS_PREVIOUS
        return None

    def _candidate(self, crop: Crop, region: Region, month: int, planted: list[str]) -> _Candidate:
        windows = [
            (w.variant, w.months_by_region[region], w.source)
            for w in crop.planting_windows
            if region in w.months_by_region and month in w.months_by_region[region]
        ]
        left = max(months_left(months, month) for _, months, _ in windows)
        candidate = _Candidate(
            crop=crop,
            variants=[variant for variant, _, _ in windows],
            months_left=left,
            window_end=None if left >= 12 else (month + left - 2) % 12 + 1,
            windows=windows,
        )
        for partner in planted:
            found = self._pairs.get(frozenset((crop.id, partner)))
            if found is None:
                continue
            relation, evidence, source = found
            target = candidate.good if relation == CompanionRelation.HELPS else candidate.bad
            target.append((partner, evidence, source))
        candidate.repellent = bool(planted) and any(
            r.role == CompanionRoleType.PEST_REPELLENT for r in crop.companion_roles
        )
        return candidate

    def _item(self, rank: int, c: _Candidate, region: Region) -> RecommendedCrop:
        r = self.t["reasons"]
        reasons = []
        for variant, months, source in c.windows:
            where = self.t["regions"][region.value]
            if variant is None:
                text = r["in_season"].format(region=where, months=self._format_months(months))
            else:
                text = r["in_season_variant"].format(
                    crop=c.crop.name_pt,
                    variant=self.t["variants"].get(variant, variant),
                    region_lower=where[0].lower() + where[1:],
                    months=self._format_months(months),
                )
            reasons.append(Reason(code=ReasonCode.IN_SEASON, text=text, source=self._cite(source)))
        if c.window_end is not None and c.months_left <= SEASON_ENDING_MONTHS:
            ending = r["season_ending"].format(month=self.t["months"][c.window_end - 1])
            reasons.append(Reason(code=ReasonCode.SEASON_ENDING, text=ending, source=reasons[0].source))
        for partner, evidence, source in c.good:
            text = r["companion_good"].format(partner=self._name(partner), evidence=self.t["evidence"][evidence])
            reasons.append(Reason(code=ReasonCode.COMPANION_GOOD, text=text, source=source))
        if c.repellent:
            refs = [role.source for role in c.crop.companion_roles if role.role == CompanionRoleType.PEST_REPELLENT]
            cited = "; ".join(dict.fromkeys(self._cite(ref) for ref in refs))
            reasons.append(Reason(code=ReasonCode.PEST_REPELLENT, text=r["pest_repellent"], source=cited))
        warnings = [
            Reason(
                code=ReasonCode.COMPANION_BAD,
                text=r["companion_bad"].format(partner=self._name(partner), evidence=self.t["evidence"][evidence]),
                source=source,
            )
            for partner, evidence, source in c.bad
        ]
        return RecommendedCrop(
            rank=rank,
            crop_id=c.crop.id,
            crop_name_pt=c.crop.name_pt,
            score=c.score,
            variants=[v for v in c.variants if v is not None],
            reasons=reasons,
            warnings=warnings,
        )

    # --- formatting ------------------------------------------------------------------

    def _name(self, crop_id: str) -> str:
        return self.kb.crops[crop_id].name_pt.lower()

    def _cite(self, ref: SourceRef) -> str:
        source = self.kb.sources.get(ref.source_id)
        label = source.title if source else ref.source_id
        return f"{label}, p. {ref.pages}" if ref.pages else label

    def _format_months(self, months: list[int]) -> str:
        return format_months(months, self.t["months"])


@lru_cache(maxsize=1)
def get_recommender() -> Recommender:
    """Cached instance for the FastAPI app (use as a dependency)."""
    return Recommender(get_knowledge_base())
