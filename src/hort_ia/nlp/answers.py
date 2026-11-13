"""Answer generation (NLG) for the conversational assistant (WBS 9.4, section 5.2).

Every answer is a template from data/nlu/responses.yaml filled with data from the
knowledge base or the market dataset. Nothing agronomic is generated: when the data is
missing, the answer says so and sets `handoff=True` (route to Technical Assistance).

The functions take already-extracted, structured input (crop id, region, month...), so
they do not depend on how the NLU is implemented. The current month is a parameter to
keep answers deterministic and testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel

from ..core.calendar import format_months
from ..core.geo import Region
from ..core.sources import SourceRef
from ..knowledge.models import Crop, Evidence, KnowledgeBase, ManagementType, ValidationStatus
from ..recommender import Profile, Recommender
from .dataset import EntityType, nlu_dir


class Answer(BaseModel):
    """What the dialogue manager receives; the API decides how to display it."""

    intent: str
    text: str
    sources: list[str] = []  # human-readable citations of the data used
    handoff: bool = False  # suggest Technical Assistance (no data, or out of scope)
    missing_entity: EntityType | None = None  # the dialogue manager must ask for it


def load_templates(path: Path | None = None) -> dict:
    with (path or nlu_dir() / "responses.yaml").open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class Responder:
    kb: KnowledgeBase
    templates: dict
    market: object | None = None  # hort_ia.market MarketDataset, optional
    recommender: Recommender | None = None  # built from `kb` on first use when not given

    @property
    def _t(self) -> dict:
        return self.templates

    # --- formatting helpers ------------------------------------------------------

    def month_name(self, month: int) -> str:
        return self._t["months"][month - 1]

    def format_months(self, months: list[int]) -> str:
        """[2..10] -> 'de fevereiro a outubro'; wraps the year; 12 months -> 'o ano todo'."""
        return format_months(months, self._t["months"])

    @staticmethod
    def join(items: list[str]) -> str:
        return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " e " + items[-1]

    def crop_name(self, crop: Crop, capitalize: bool = False) -> str:
        return crop.name_pt if capitalize else crop.name_pt.lower()

    def cite(self, refs: list[SourceRef]) -> list[str]:
        out = []
        for ref in refs:
            source = self.kb.sources.get(ref.source_id)
            label = source.title if source else ref.source_id
            out.append(f"{label}, p. {ref.pages}" if ref.pages else label)
        return list(dict.fromkeys(out))  # dedupe, keep order

    def region_label(self, region: Region | str) -> str:
        return self._t["regions"][Region(region).value]

    def _answer(self, intent: str, lines: list[str], sep: str = " ", **kwargs) -> Answer:
        """Join the non-empty lines; `sep="\\n"` puts one part per line (pest and disease answers)."""
        return Answer(intent=intent, text=sep.join(line for line in lines if line), **kwargs)

    def _crop_or_ask(self, intent: str, crop_id: str | None) -> Crop | Answer:
        c = self._t["common"]
        if crop_id is None:
            return self._answer(intent, [c["ask_crop"]], missing_entity=EntityType.CROP)
        crop = self.kb.crops.get(crop_id)
        if crop is None:
            known = self.join(sorted(cr.name_pt.lower() for cr in self.kb.crops.values()))
            return self._answer(intent, [c["unknown_crop"].format(crops=known)], handoff=True)
        return crop

    # --- intents -------------------------------------------------------------------

    def planting_time(self, crop_id: str | None, region: Region | str | None, month: int) -> Answer:
        t, intent = self._t["planting_time"], "planting_time"
        crop = self._crop_or_ask(intent, crop_id)
        if isinstance(crop, Answer):
            return crop
        if region is None:
            return self._answer(intent, [self._t["common"]["ask_location"]], missing_entity=EntityType.LOCATION)
        name, where = self.crop_name(crop, capitalize=True), self.region_label(region)
        by_variant = crop.planting_months(region)
        if by_variant is None:
            return self._answer(
                intent,
                [t["no_data"].format(crop=name.lower(), region=where), self._t["common"]["handoff"]],
                handoff=True,
            )
        lines, in_season, refs = [], False, []
        for window in crop.planting_windows:
            if Region(region) not in window.months_by_region:
                continue
            months = window.months_by_region[Region(region)]
            variant = " " + self._t["variants"].get(window.variant, window.variant) if window.variant else ""
            refs.append(window.source)
            if not months:
                lines.append(t["not_recommended"].format(crop=name, variant=variant, region=where))
                continue
            lines.append(
                t["window"].format(crop=name, variant=variant, region=where, months=self.format_months(months))
            )
            in_season = in_season or month in months
        if any(by_variant.values()):
            key = "now_yes" if in_season else "now_no"
            lines.append(t[key].format(month=self.month_name(month)))
            days = [w.harvest_start_days for w in crop.planting_windows if Region(region) in w.months_by_region]
            lines.append(t["harvest"].format(min=min(d.min for d in days), max=max(d.max for d in days)))
        return self._answer(intent, [" ".join(line.split()) for line in lines], sources=self.cite(refs))

    def what_to_plant(self, region: Region | str | None, month: int, small_space: bool = False) -> Answer:
        t, intent = self._t["what_to_plant"], "what_to_plant"
        if region is None:
            return self._answer(intent, [self._t["common"]["ask_location"]], missing_entity=EntityType.LOCATION)
        # Same list and order as the recommendation engine (9.3.1-3, decision D6).
        if self.recommender is None:
            self.recommender = Recommender(self.kb)
        result = self.recommender.recommend(Profile(region=region, month=month, small_space=small_space))
        crops = [item.crop_name_pt.lower() for item in result.recommendations]
        where, month_name = self.region_label(region), self.month_name(month)
        if not crops:
            return self._answer(intent, [t["none"].format(month=month_name, region=where)], handoff=True)
        key = "list_small_space" if small_space else "list"
        # Cite the planting windows behind the list (found by 9.4.2-2, case U9: the list had no source).
        sources = list(dict.fromkeys(
            reason.source for item in result.recommendations for reason in item.reasons
            if reason.code == "in_season" and reason.source
        ))  # fmt: skip
        return self._answer(
            intent, [t[key].format(month=month_name, region=where, crops=self.join(crops))], sources=sources
        )

    def crop_care(self, crop_id: str | None, aspect: str | None = None) -> Answer:
        """aspect: spacing | harvest | watering | container | None (summary of spacing and harvest)."""
        t, intent = self._t["crop_care"], "crop_care"
        crop = self._crop_or_ask(intent, crop_id)
        if isinstance(crop, Answer):
            return crop
        name, lines, refs = self.crop_name(crop), [], []
        if aspect in (None, "spacing", "container") and crop.spacing:
            if aspect != "container":
                conv = crop.spacing.conventional
                lines.append(
                    t["spacing"].format(crop=crop.name_pt, plants=conv.between_plants_cm, rows=conv.between_rows_cm)
                )
            show_small = aspect == "container" or crop.small_space_recommended
            if crop.spacing.small_spaces and crop.small_space_recommended is not False and show_small:
                small = crop.spacing.small_spaces
                lines.append(
                    t["spacing_small_space"].format(plants=small.between_plants_cm, rows=small.between_rows_cm)
                )
            refs.append(crop.spacing.source)
        if aspect == "container":
            key = {True: "container_yes", False: "container_no", None: "container_unknown"}[
                crop.small_space_recommended
            ]
            lines.insert(0, t[key].format(crop=name))
            if crop.small_space_recommended is False:
                lines += [g.statement_pt for g in self._guidelines_for(crop, topic="small_spaces")]
        if aspect in (None, "harvest") and crop.planting_windows:
            days = [w.harvest_start_days for w in crop.planting_windows]
            template = t["harvest"] if aspect == "harvest" else self._t["planting_time"]["harvest"]
            lines.append(template.format(crop=crop.name_pt, min=min(d.min for d in days), max=max(d.max for d in days)))
            refs += [w.source for w in crop.planting_windows]
        if aspect == "watering":
            guidelines = self._guidelines_for(crop, topic="irrigation")
            lines += [g.statement_pt for g in guidelines]
            refs += [g.source for g in guidelines]
        if not lines:
            return self._answer(intent, [t["no_info"].format(crop=name), self._t["common"]["handoff"]], handoff=True)
        if not refs:  # only "no information" lines (e.g. container for a crop without spacing): hand off
            return self._answer(intent, [*lines, self._t["common"]["handoff"]], handoff=True)
        return self._answer(intent, lines, sources=self.cite(refs))

    def _guidelines_for(self, crop: Crop, topic: str) -> list:
        """Most specific guidelines for a crop: crop-specific first, else by crop group."""
        candidates = [g for g in self.kb.guidelines.values() if g.topic == topic]
        specific = [g for g in candidates if crop.id in g.applies_to_crops]
        if specific:
            return specific
        return [g for g in candidates if set(crop.crop_groups) & set(g.applies_to_groups)]

    def companion_planting(self, crop_id: str | None, rotation: bool = False) -> Answer:
        t, intent = self._t["companion_planting"], "companion_planting"
        if crop_id is None:
            # The rotation rule by id: the other "rotation" guideline (rotacao_familia_por_cultura, ATD v3)
            # only points to the `rotation` field of crops.json, which means nothing to the user.
            general = [g for g in self.kb.guidelines.values() if g.topic == "companion"]
            general += [g for g in [self.kb.guidelines.get("rotacao_por_familia")] if g]
            return self._answer(
                intent, [g.statement_pt for g in general], sources=self.cite([g.source for g in general])
            )
        crop = self._crop_or_ask(intent, crop_id)
        if isinstance(crop, Answer):
            return crop
        name = self.crop_name(crop)
        if rotation:
            same = sorted(c.name_pt.lower() for c in self.kb.crops.values() if c.family == crop.family)
            rule = self.kb.guidelines.get("rotacao_por_familia")
            return self._answer(
                intent,
                [t["rotation"].format(crop=name, same_family=self.join(same))],
                sources=self.cite([rule.source] if rule else []),
            )
        good, bad, evidence, refs, relation_refs = set(), set(), set(), [], []
        for rel in self.kb.usable_companions_of(crop.id):  # decision D6: withheld relations never show
            other = rel.crop_b if rel.crop_a == crop.id else rel.crop_a
            (good if rel.relation == "helps" else bad).add(self.kb.crops[other].name_pt.lower())
            evidence.add(rel.evidence)
            relation_refs.append(SourceRef(source_id=rel.source_id, pages=rel.pages))
        lines = []
        if any(r.role == "pest_repellent" for r in crop.companion_roles):
            lines.append(t["repellent"].format(crop=crop.name_pt))
            refs += [r.source for r in crop.companion_roles]
        if good:
            lines.append(t["good"].format(crop=name, partners=self.join(sorted(good))))
        if bad:
            lines.append(t["bad"].format(crop=name, partners=self.join(sorted(bad))))
        if note := self._evidence_note(evidence):
            lines.append(note)
        if not lines:
            return self._answer(intent, [t["none"].format(crop=name)], handoff=True)
        return self._answer(intent, lines, sources=self.cite(refs + relation_refs))

    def _evidence_note(self, evidence: set[Evidence]) -> str | None:
        """Where the combinations shown come from (decision D9): all from tradition, mixed, or all technical.

        Research relations never get here (decision D6), so `evidence` holds technical and traditional only."""
        t = self._t["companion_planting"]
        if not evidence:
            return None
        if evidence == {Evidence.TRADITIONAL}:
            return t["traditional_note"]
        if Evidence.TRADITIONAL in evidence:
            return t["mixed_note"]
        return t["technical_note"]

    def pest_disease(self, cv_label: str | None = None, entry_id: str | None = None) -> Answer:
        """From the CV model output (cv_label) or a pest named in the text (entry_id)."""
        t, intent = self._t["pest_disease"], "pest_disease"
        entry = self.kb.by_cv_label(cv_label) if cv_label else self.kb.pests_diseases.get(entry_id or "")
        if entry is None:
            return self._answer(intent, [t["ask_photo"]])
        if entry.type == "healthy":
            return self._answer(intent, [t["healthy"]])
        if entry.is_beneficial:  # `type: beneficial` (ATD v3) or a pest with `beneficial: true`
            return self._answer(intent, [t["beneficial"].format(name=entry.name_pt)], sources=self.cite(entry.sources))
        # One part per line and each action as a list item, easier to read than a single paragraph
        # for the pilot's audience. The other intents keep a single paragraph.
        name, sep = entry.name_pt or entry.causal_agent or entry.cv_label, "\n"
        lines = [t["identified"].format(name=name)]
        # The expected symptom lets the user check the CV identification against the plant. It is
        # descriptive, so it is shown with any validation status, and its sources come first.
        refs = list(entry.symptoms_sources)
        if entry.symptoms:
            lines.append(t["symptoms"].format(symptoms=entry.symptoms[:1].lower() + entry.symptoms[1:]))
        # Until agronomists review an entry, show only what is safe to do on one's own (prevention,
        # cultural and biological actions) and route treatment to Technical Assistance. Homemade
        # preparations (`alternative`) only appear once the entry is reviewed. `validated_by_atd` is
        # treated like `draft`: the ATD checks source and page, which is not an agronomic endorsement.
        reviewed = entry.validation_status == ValidationStatus.REVIEWED
        shown = [m for m in entry.management if reviewed or m.type != ManagementType.ALTERNATIVE]
        if not shown:
            lines += [t["no_management"], self._t["common"]["handoff"]]
            return self._answer(intent, lines, sep, sources=self.cite(refs), handoff=True)
        sources = self.cite(refs + [m.source for m in shown])
        lines += [t["prevention"], *(t["action_item"].format(action=m.description) for m in shown)]
        if reviewed:  # the closing line offers Technical Assistance without requiring it
            return self._answer(intent, lines + [t["reviewed_closing"]], sep, sources=sources)
        return self._answer(intent, lines + [t["treatment_handoff"]], sep, sources=sources, handoff=True)

    def market_price(self, product: str | None, uf: str | None = None) -> Answer:
        """product: crop id, market product id or name; uf: user's state, to pick the local Ceasa."""
        t, intent = self._t["market_price"], "market_price"
        if self.market is None:
            return self._answer(intent, [self._t["fallback"]["text"], self._t["common"]["handoff"]], handoff=True)
        if product is None:
            return self._answer(intent, [self._t["common"]["ask_crop"]], missing_entity=EntityType.CROP)
        m = self.market
        found = m.products.get(product) or m.product_by_crop_id(product) or m.product_by_alias(product)
        if found is None:
            names = self.join(sorted(p.name_pt.lower() for p in m.products.values()))
            asked = self.kb.crops[product].name_pt.lower() if product in self.kb.crops else product
            return self._answer(intent, [t["not_tracked"].format(product=asked, products=names)])
        local = next((e for e in m.entrepostos.values() if uf and e.uf == uf.upper()), None)
        ref = m.reference_price(found.id, local.id) if local else None
        where = t["where_entrepost"].format(entrepost=local.name_pt) if ref else t["where_national"]
        ref = ref or m.reference_price(found.id)
        if ref is None:
            return self._answer(
                intent, [t["not_tracked"].format(product=found.name_pt.lower(), products="")], handoff=True
            )
        year, month = ref.reference_month.split("-")
        lines = [
            t["price"].format(
                month=f"{self.month_name(int(month))} de {year}",
                product=found.name_pt.lower(),
                price=f"{ref.price_brl_kg:.2f}".replace(".", ","),
                where=where,
            )
        ]
        if ref.change_prev_month is not None:
            pct = round(abs(ref.change_prev_month) * 100)
            key = "change_stable" if pct == 0 else "change_up" if ref.change_prev_month > 0 else "change_down"
            lines.append(t[key].format(pct=pct))
        lines.append(t["wholesale_note"])
        source = m.sources.get("conab_boletim_hortigranjeiro")
        return self._answer(intent, lines, sources=[source.title] if source else [])

    def unknown_crop(self, intent: str) -> Answer:
        """The user named a plant the base does not have (the dialogue could not recognize it)."""
        known = self.join(sorted(cr.name_pt.lower() for cr in self.kb.crops.values()))
        return self._answer(intent, [self._t["common"]["unknown_crop"].format(crops=known)], handoff=True)

    def help(self) -> Answer:
        return self._answer("help", [self._t["help"]["text"]])

    def fallback(self) -> Answer:
        return self._answer("fallback", [self._t["fallback"]["text"], self._t["common"]["handoff"]], handoff=True)
