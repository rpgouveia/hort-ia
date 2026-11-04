"""The reference-price ladder of 9.5.1-3, section 5.1: UF -> macro-region -> national.

Why a ladder instead of the single national mean the bulletin already publishes: an entrepost
deviates from that mean by 19.7% at the median, 68% at p90 and 146% at worst (section 3a of the
decision record), so comparing a grower in Curitiba against it would be wrong by an order of
magnitude in some cases. Decision D1.

Only the *local* level rescues an entrepost that stopped publishing (section 5.3): levels 2 and 3
read the reference month of the bulletin, which is why Brasilia falls all the way to the national
mean (case C6) even though Goiania, in the same region, still has a 2-month-old series.

The errors of the module live here because this is the layer where resolution fails: an unknown
product, an unknown location, or a malformed parameter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from statistics import median

from ..core.geo import UF_BY_CODE, Region, region_from_ibge_code, region_from_uf
from ..market import MarketDataset
from .bands import MAX_LAG_MONTHS, month_index


class ComparisonError(Exception):
    """The price comparison cannot be produced."""


class UnknownIdError(ComparisonError):
    """Unknown product (no Conab quote) or unknown location. Maps to 404."""


class InvalidParameterError(ComparisonError):
    """Malformed or out-of-range parameter. Maps to 422."""


class ReferenceLevel(StrEnum):
    LOCAL = "local"
    REGIONAL = "regional"
    NATIONAL = "nacional"


# Section 5.1: the further the reference is from the user, the less it says about their price.
CONFIDENCE: dict[ReferenceLevel, float] = {
    ReferenceLevel.LOCAL: 1.00,
    ReferenceLevel.REGIONAL: 0.70,
    ReferenceLevel.NATIONAL: 0.40,
}


def region_label(region: Region) -> str:
    """'centro_oeste' -> 'Centro-Oeste', for the warnings. No table: the enum value carries it."""
    return region.value.replace("_", "-").title()


def ptbr(value: float, decimals: int = 2) -> str:
    """Format a number for the `warning` field, which is the one output the user reads."""
    return f"{value:.{decimals}f}".replace(".", ",")


def resolve_location(
    ibge_code: int | str | None = None, uf: str | None = None
) -> tuple[str, Region]:
    """Resolve the user's location to (UF, region) with `hort_ia.core.geo`.

    Malformed input is a 422 and a well-formed but unknown location a 404, per section 8.
    """
    if ibge_code is not None and uf is not None:
        raise InvalidParameterError("informe ibge_code ou uf, não os dois")
    if ibge_code is not None:
        digits = str(ibge_code).strip()
        if not digits.isdigit() or len(digits) not in (2, 7):
            raise InvalidParameterError(
                f"código IBGE deve ter 2 (UF) ou 7 (município) dígitos: {ibge_code!r}"
            )
        if digits[:2] not in UF_BY_CODE:
            raise UnknownIdError(f"código de UF desconhecido no código IBGE: {ibge_code!r}")
        return UF_BY_CODE[digits[:2]], region_from_ibge_code(digits)
    if uf is not None:
        text = uf.strip().upper()
        if len(text) != 2 or not text.isalpha():
            raise InvalidParameterError(f"UF deve ter 2 letras: {uf!r}")
        try:
            return text, region_from_uf(text)
        except ValueError as error:
            raise UnknownIdError(f"UF desconhecida: {uf!r}") from error
    raise InvalidParameterError("informe a localização: ibge_code ou uf")


@dataclass(frozen=True)
class Quote:
    """One entrepost's price for the comparison, with how old it is."""

    entrepost_id: str
    price_brl_kg: float
    month: str
    lag_months: int
    change_prev_month: float | None


@dataclass(frozen=True)
class Reference:
    """The reference the ladder settled on. `low`/`high` are the bounds the band is applied to."""

    level: ReferenceLevel
    entrepost_ids: list[str]
    month: str
    price_brl_kg: float  # unrounded, so the deviation is not computed on a rounded value
    low_brl_kg: float
    high_brl_kg: float
    lag_months: int
    change_prev_month: float | None
    degraded: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def confidence(self) -> float:
        return CONFIDENCE[self.level]


def _median_change(quotes: list[Quote]) -> float | None:
    changes = [q.change_prev_month for q in quotes if q.change_prev_month is not None]
    return median(changes) if changes else None


def _local_quotes(
    dataset: MarketDataset,
    product_id: str,
    uf: str,
    latest_month: str,
    max_lag: int,
) -> tuple[list[Quote], list[str]]:
    """Usable quotes from the entrepostos of the UF, plus a warning per discarded entrepost.

    An entrepost that published in the reference month is used as is; one that stopped publishing is
    rescued from the last observed month of its series while the lag is within `max_lag` (CEASA/GO,
    2 months) and dropped above it (CEASA/DF, 22 months). Series edges are never extrapolated and a
    missing price is never zero, as in 9.6.
    """
    quotes: list[Quote] = []
    warnings: list[str] = []
    for entrepost in sorted(dataset.entrepostos.values(), key=lambda e: e.id):
        if entrepost.uf != uf:
            continue
        published = dataset.reference_price(product_id, entrepost.id)
        if published is not None:
            quotes.append(
                Quote(
                    entrepost_id=entrepost.id,
                    price_brl_kg=published.price_brl_kg,
                    month=published.reference_month,
                    lag_months=month_index(latest_month)
                    - month_index(published.reference_month),
                    change_prev_month=published.change_prev_month,
                )
            )
            continue
        observed = dataset.latest_price(product_id, entrepost.id)
        if observed is None:
            continue
        lag = month_index(latest_month) - month_index(observed.month)
        if lag > max_lag:
            warnings.append(
                f"{entrepost.name_pt} descartada: {lag} meses de defasagem "
                f"(último preço em {observed.month})"
            )
            continue
        quotes.append(
            Quote(
                entrepost_id=entrepost.id,
                price_brl_kg=observed.price_brl_kg,
                month=observed.month,
                lag_months=lag,
                change_prev_month=None,  # the bulletin published no monthly change for this month
            )
        )
    if not quotes:
        return [], warnings
    # Never mix a fresh price with a stale one: the freshest quotes of the UF win.
    freshest = min(q.lag_months for q in quotes)
    return [q for q in quotes if q.lag_months == freshest], warnings


def _regional_quotes(dataset: MarketDataset, product_id: str, region: Region) -> list[Quote]:
    """Entrepostos of the region that published in the reference month (section 5.1, level 2)."""
    quotes = []
    for entrepost in sorted(dataset.entrepostos.values(), key=lambda e: e.id):
        if entrepost.region != region:
            continue
        published = dataset.reference_price(product_id, entrepost.id)
        if published is not None:
            quotes.append(
                Quote(
                    entrepost_id=entrepost.id,
                    price_brl_kg=published.price_brl_kg,
                    month=published.reference_month,
                    lag_months=0,
                    change_prev_month=published.change_prev_month,
                )
            )
    return quotes


def resolve_reference(
    dataset: MarketDataset,
    product_id: str,
    uf: str,
    region: Region,
    latest_month: str,
    max_lag: int = MAX_LAG_MONTHS,
) -> Reference:
    """Walk the ladder of section 5.1 and return the first level that has a price.

    Raises `UnknownIdError` when the product has no Conab quote at all (case C7): the comparison is
    not produced, and in the matching engine the price criterion is switched off (decision D6).
    """
    if product_id not in dataset.products:
        raise UnknownIdError(f"produto sem cotação Conab: {product_id!r}")

    quotes, warnings = _local_quotes(dataset, product_id, uf, latest_month, max_lag)
    if quotes:
        # More than one entrepost in the UF (São Paulo): the median, around a single point. Case C2.
        value = median([q.price_brl_kg for q in quotes])
        return Reference(
            level=ReferenceLevel.LOCAL,
            entrepost_ids=[q.entrepost_id for q in quotes],
            month=min(q.month for q in quotes),
            price_brl_kg=value,
            low_brl_kg=value,
            high_brl_kg=value,
            lag_months=max(q.lag_months for q in quotes),
            change_prev_month=_median_change(quotes),
            warnings=warnings,
        )

    quotes = _regional_quotes(dataset, product_id, region)
    if quotes:
        prices = [q.price_brl_kg for q in quotes]
        # The region is a weak proxy (CV of 52% for alface in the Sudeste), so the output carries the
        # observed min-max instead of a point value, and confidence drops to 0.70. Decision D2.
        warnings.append(f"sem entreposto de referência em {uf}")
        warnings.append(
            f"referência regional ({region_label(region)}) a partir de {len(quotes)} entreposto(s): "
            f"R$ {ptbr(min(prices))} a {ptbr(max(prices))}/kg"
        )
        return Reference(
            level=ReferenceLevel.REGIONAL,
            entrepost_ids=[q.entrepost_id for q in quotes],
            month=quotes[0].month,
            price_brl_kg=median(prices),
            low_brl_kg=min(prices),
            high_brl_kg=max(prices),
            lag_months=0,
            change_prev_month=_median_change(quotes),
            warnings=warnings,
        )

    national = dataset.reference_price(product_id, None)
    if national is None:  # the dataset guarantees one weighted average per product
        raise UnknownIdError(f"produto sem média ponderada nacional: {product_id!r}")
    warnings.append(
        f"sem entreposto de referência na região {region_label(region)}; "
        "comparação contra a média ponderada nacional da Conab"
    )
    return Reference(
        level=ReferenceLevel.NATIONAL,
        entrepost_ids=[],
        month=national.reference_month,
        price_brl_kg=national.price_brl_kg,
        low_brl_kg=national.price_brl_kg,
        high_brl_kg=national.price_brl_kg,
        lag_months=0,
        change_prev_month=national.change_prev_month,
        degraded=True,  # section 5.2: the national level is always a degraded comparison
        warnings=warnings,
    )
