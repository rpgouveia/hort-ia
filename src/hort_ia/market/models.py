"""Pydantic models for the Hort.IA market dataset (Conab Boletim Hortigranjeiro).

Every record carries `sources` for traceability, where `SourceRef.pages` holds the
name of the workbook sheet the value came from. Unlike the agronomic knowledge base,
market records have no `validation_status`: Conab is an official published bulletin,
not a team transcription awaiting agronomist review.

Source models come from `hort_ia.core`; only `Region` is imported from the knowledge
base. The `crop_id` link is deliberately *not* enforced here, so the
market dataset loads without the agronomic base; `check_crop_links` checks it on demand.
"""

from __future__ import annotations

from collections import Counter
from enum import StrEnum
from typing import TYPE_CHECKING, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.sources import ID_PATTERN, Source, SourceRef
from ..knowledge.models import Region

if TYPE_CHECKING:
    from ..knowledge.models import KnowledgeBase

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
UF_PATTERN = r"^([A-Z]{2}|NI)$"  # NI = "não informado" (used in the UF supply tables)


class ProductCategory(StrEnum):
    """Workbook family a product comes from ("hortaliças" / "frutas")."""

    VEGETABLE = "vegetable"
    FRUIT = "fruit"


class MarketModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- Registries --------------------------------------------------------------


class MarketProduct(MarketModel):
    """A product quoted in the bulletin, optionally linked to a Crop."""

    id: str = Field(pattern=ID_PATTERN)
    name_pt: str
    category: ProductCategory
    unit: Literal["kg"] = "kg"
    crop_id: str | None = None  # None = not among the 15 MVP crops in crops.json
    aliases: list[str] = []  # every label found in the workbook
    sources: list[SourceRef] = []
    notes: str | None = None


class Entrepost(MarketModel):
    """A wholesale market (Ceasa) that reports prices and volumes to Conab.

    `aliases` holds every raw spelling found in the workbook, so the committed
    registry *is* the build script's lookup table and the normalisation of the
    source's inconsistent casing stays auditable.
    """

    id: str = Field(pattern=ID_PATTERN)
    name_pt: str
    city: str
    uf: str = Field(pattern=r"^[A-Z]{2}$")
    region: Region
    aliases: list[str] = Field(min_length=1)
    sources: list[SourceRef] = []
    notes: str | None = None

    @model_validator(mode="after")
    def _unique_aliases(self) -> Self:
        duplicates = [a for a, n in Counter(self.aliases).items() if n > 1]
        if duplicates:
            raise ValueError(f"entrepost '{self.id}': duplicate aliases {duplicates}")
        return self


# --- Facts -------------------------------------------------------------------
#
# A source cell that was blank, 0 or #DIV/0! produces no record at all, which is
# why every measure below is strictly positive instead of nullable. Gaps are
# recovered by comparing against the registries (see `coverage_report`).


class PriceObservation(MarketModel):
    """One month of the price series of a product at an entrepost."""

    product_id: str
    entrepost_id: str
    month: str = Field(pattern=MONTH_PATTERN)
    price_brl_kg: float = Field(gt=0)


class PriceReference(MarketModel):
    """The bulletin's headline price for the reference month.

    `entrepost_id is None` marks the "Média Ponderada" row: the volume-weighted
    national mean, which cannot be recomputed from the other rows because Conab
    does not publish the weights.
    """

    product_id: str
    entrepost_id: str | None = None
    reference_month: str = Field(pattern=MONTH_PATTERN)
    price_brl_kg: float = Field(gt=0)
    change_prev_month: float | None = Field(default=None, ge=-1)

    @property
    def is_weighted_average(self) -> bool:
        return self.entrepost_id is None


class QuantityObservation(MarketModel):
    """Volume of a product traded at an entrepost in one month."""

    product_id: str
    entrepost_id: str
    month: str = Field(pattern=MONTH_PATTERN)
    quantity_kg: int = Field(gt=0)


class MarketVolume(MarketModel):
    """Total volume traded across the analysed entrepostos, by product category."""

    category: ProductCategory
    month: str = Field(pattern=MONTH_PATTERN)
    quantity_kg: int = Field(gt=0)


class MicroregionSupply(MarketModel):
    """A microregion in the bulletin's supply ranking (truncated: top 20 only)."""

    product_id: str
    microregion: str
    uf: str = Field(pattern=UF_PATTERN)
    quantity_kg: int = Field(gt=0)
    rank: int = Field(ge=1)
    reference_month: str = Field(pattern=MONTH_PATTERN)


class UfSupply(MarketModel):
    """Supply of a product by state. Unlike the microregions, a complete partition."""

    product_id: str
    uf: str = Field(pattern=UF_PATTERN)
    quantity_kg: int = Field(gt=0)
    reference_month: str = Field(pattern=MONTH_PATTERN)


# --- Aggregate ---------------------------------------------------------------


class MarketDataset(MarketModel):
    products: dict[str, MarketProduct]
    entrepostos: dict[str, Entrepost]
    sources: dict[str, Source]
    prices: list[PriceObservation]
    price_reference: list[PriceReference]
    quantities: list[QuantityObservation]
    volumes: list[MarketVolume]
    microregion_supply: list[MicroregionSupply]
    uf_supply: list[UfSupply]

    @model_validator(mode="after")
    def _referential_integrity(self) -> Self:
        errors: list[str] = []

        def check_product(product_id: str, owner: str) -> None:
            if product_id not in self.products:
                errors.append(f"{owner}: produto desconhecido '{product_id}'")

        def check_entrepost(entrepost_id: str | None, owner: str) -> None:
            if entrepost_id is not None and entrepost_id not in self.entrepostos:
                errors.append(f"{owner}: entreposto desconhecido '{entrepost_id}'")

        def check_source(source_id: str, owner: str) -> None:
            if source_id not in self.sources:
                errors.append(f"{owner}: fonte desconhecida '{source_id}'")

        def check_duplicates(keys: list[tuple], filename: str) -> None:
            for key, n in Counter(keys).items():
                if n > 1:
                    errors.append(f"{filename}: chave duplicada {key}")

        for registry, filename in ((self.products, "products.json"), (self.entrepostos, "entrepostos.json")):
            for record in registry.values():
                for ref in record.sources:
                    check_source(ref.source_id, f"{filename} '{record.id}'")

        for name, rows in (("prices_monthly.csv", self.prices), ("quantities.csv", self.quantities)):
            for i, row in enumerate(rows, start=2):  # CSV line number
                owner = f"{name} line {i}"
                check_product(row.product_id, owner)
                check_entrepost(row.entrepost_id, owner)
            check_duplicates([(r.product_id, r.entrepost_id, r.month) for r in rows], name)

        for i, ref in enumerate(self.price_reference, start=2):
            owner = f"prices_reference.csv line {i}"
            check_product(ref.product_id, owner)
            check_entrepost(ref.entrepost_id, owner)
        check_duplicates(
            [(r.product_id, r.entrepost_id) for r in self.price_reference], "prices_reference.csv"
        )

        check_duplicates([(v.category, v.month) for v in self.volumes], "volume_totals.csv")

        for i, row in enumerate(self.microregion_supply, start=2):
            check_product(row.product_id, f"supply_microregions.csv line {i}")
        check_duplicates(
            [(r.product_id, r.rank) for r in self.microregion_supply], "supply_microregions.csv"
        )
        check_duplicates(
            [(r.product_id, r.microregion, r.uf) for r in self.microregion_supply],
            "supply_microregions.csv",
        )

        for i, row in enumerate(self.uf_supply, start=2):
            check_product(row.product_id, f"supply_uf.csv line {i}")
        check_duplicates([(r.product_id, r.uf) for r in self.uf_supply], "supply_uf.csv")

        for product_id in self.products:
            if not any(p.product_id == product_id for p in self.prices):
                errors.append(f"produto '{product_id}' sem nenhuma observação de preço")
            averages = [
                r for r in self.price_reference if r.product_id == product_id and r.is_weighted_average
            ]
            if len(averages) != 1:
                errors.append(
                    f"produto '{product_id}': esperada 1 média ponderada, encontradas {len(averages)}"
                )
            ranked = sorted(
                (r for r in self.microregion_supply if r.product_id == product_id),
                key=lambda r: r.rank,
            )
            if [r.rank for r in ranked] != list(range(1, len(ranked) + 1)):
                errors.append(f"produto '{product_id}': ranks de microrregião não são contíguos a partir de 1")
            if any(a.quantity_kg < b.quantity_kg for a, b in zip(ranked, ranked[1:])):
                errors.append(f"produto '{product_id}': microrregiões não estão em ordem decrescente")

        # An ambiguous alias would make the build script non-deterministic on the next edition.
        for registry, filename in ((self.products, "products.json"), (self.entrepostos, "entrepostos.json")):
            seen: dict[str, str] = {}
            for record in registry.values():
                for alias in record.aliases:
                    normalised = alias.strip().casefold()
                    if seen.setdefault(normalised, record.id) != record.id:
                        errors.append(
                            f"{filename}: alias '{alias}' usado por '{seen[normalised]}' e '{record.id}'"
                        )

        if errors:
            raise ValueError("referential integrity errors:\n- " + "\n- ".join(errors))
        return self

    # --- Queries (used by the commercial matching engine, WBS 9.5) ------------

    def price_series(self, product_id: str, entrepost_id: str) -> list[PriceObservation]:
        """The price history of a product at one entrepost, oldest month first."""
        series = [
            p for p in self.prices if p.product_id == product_id and p.entrepost_id == entrepost_id
        ]
        return sorted(series, key=lambda p: p.month)

    def latest_price(self, product_id: str, entrepost_id: str) -> PriceObservation | None:
        series = self.price_series(product_id, entrepost_id)
        return series[-1] if series else None

    def reference_price(self, product_id: str, entrepost_id: str | None = None) -> PriceReference | None:
        """The headline price for the reference month; `entrepost_id=None` = national mean."""
        return next(
            (
                r
                for r in self.price_reference
                if r.product_id == product_id and r.entrepost_id == entrepost_id
            ),
            None,
        )

    def top_origins(self, product_id: str, limit: int = 5) -> list[MicroregionSupply]:
        ranked = sorted(
            (r for r in self.microregion_supply if r.product_id == product_id),
            key=lambda r: r.rank,
        )
        return ranked[:limit]

    def product_by_crop_id(self, crop_id: str) -> MarketProduct | None:
        """Resolve an agronomic crop to the product quoted in the bulletin."""
        return next((p for p in self.products.values() if p.crop_id == crop_id), None)

    def product_by_alias(self, text: str) -> MarketProduct | None:
        normalised = text.strip().casefold()
        return next(
            (
                p
                for p in self.products.values()
                if normalised == p.name_pt.casefold()
                or normalised in {a.casefold() for a in p.aliases}
            ),
            None,
        )


def check_crop_links(dataset: MarketDataset, kb: KnowledgeBase) -> list[str]:
    """Cross-check `crop_id` against the agronomic base. The only coupling between them."""
    return [
        f"products.json: produto '{product.id}' aponta para cultura inexistente '{product.crop_id}'"
        for product in dataset.products.values()
        if product.crop_id is not None and product.crop_id not in kb.crops
    ]
