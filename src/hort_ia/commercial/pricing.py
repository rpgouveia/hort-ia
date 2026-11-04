"""Price comparison service (WBS 9.5.1-4), implementing sections 5.1 to 5.4 of 9.5.1-3.

Given a product, a location and optionally the price the user has in hand, the service returns the
closest available Conab reference, the tolerance band around it and where the informed price sits.
Stateless: nothing is read from or written to a store, per the LGPD decision of 9.1.2-4/-7.

Nothing is learned here, and that is a consequence of the data, not a preference: the repository has
no offer, demand or negotiation history, so there is no label to train a model on (decision record,
section 2). Every parameter is either fixed in the approved approach or measured on the dataset.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import BaseModel

from ..core.geo import Region
from ..market import MarketDataset, get_market_dataset
from .bands import MAX_LAG_MONTHS, month_index, staleness_drift, tolerance_bands
from .reference import (
    ComparisonError,
    InvalidParameterError,
    Reference,
    ReferenceLevel,
    UnknownIdError,
    ptbr,
    resolve_location,
    resolve_reference,
)

MODEL_VERSION = "1.0.0"  # bump when the ladder, the band, the weights or the lag rule change

# Section 5.2: at the national level the band is the mean deviation observed between an entrepost and
# the weighted national mean (29.3%, section 3a). The only band that is not measured per product,
# because it answers a different question: how wrong the national mean tends to be, not how much the
# product oscillates. It always travels with `degraded = true`.
NATIONAL_BAND_PCT = 0.30


class PricePosition(StrEnum):
    BELOW = "abaixo_da_faixa"
    WITHIN = "na_faixa"
    ABOVE = "acima_da_faixa"


class Location(BaseModel):
    uf: str
    region: Region


class PriceComparison(BaseModel):
    """The output contract of section 5.4, consumed by 9.5.1-5 and 9.5.1-6."""

    product_id: str
    location: Location
    reference_level: ReferenceLevel
    entrepost_ids: list[str]  # empty at the national level
    reference_month: str  # effective month of the price used, not always the bulletin's
    reference_price_brl_kg: float
    band_low_brl_kg: float
    band_high_brl_kg: float
    band_pct: float
    informed_price_brl_kg: float | None
    deviation_pct: float | None  # informed / reference - 1
    position: PricePosition | None
    change_prev_month: float | None
    confidence: float
    source: str  # id(s) of the dataset source(s) in data/market/sources.json
    model_version: str
    degraded: bool = False
    warning: str | None = None


class PriceComparator:
    """Compares a price against the Conab reference of the user's location.

    Build once and reuse: the tolerance bands and the staleness drift are measured over the whole
    price history on construction.
    """

    def __init__(self, dataset: MarketDataset, max_lag_months: int = MAX_LAG_MONTHS):
        self.dataset = dataset
        self.max_lag_months = max_lag_months
        self.bands = tolerance_bands(dataset)
        self.drift = staleness_drift(dataset, max_lag_months)
        self.latest_month = max((p.month for p in dataset.prices), key=month_index)
        self.source = ",".join(sorted(dataset.sources))

    def band_pct(self, product_id: str, reference: Reference) -> float:
        """Tolerance band of section 5.2, widened when the reference is 2 or 3 months behind."""
        if reference.level is ReferenceLevel.NATIONAL:
            return NATIONAL_BAND_PCT
        band = self.bands[product_id]
        if reference.lag_months >= 2:  # a lag of 0 or 1 month is normal and widens nothing
            band += self.drift[reference.lag_months]
        return round(band, 4)

    def compare(
        self,
        product_id: str,
        *,
        ibge_code: int | str | None = None,
        uf: str | None = None,
        price_brl_kg: float | None = None,
    ) -> PriceComparison:
        """Compare `price_brl_kg` (optional) against the reference for `product_id` at the location.

        Without an informed price the output carries only the reference and the band, which is what
        the chatbot needs to answer "quanto está valendo?".
        """
        if price_brl_kg is not None and price_brl_kg <= 0:
            raise InvalidParameterError(f"preço deve ser positivo: {price_brl_kg!r}")
        user_uf, region = resolve_location(ibge_code, uf)
        reference = resolve_reference(
            self.dataset, product_id, user_uf, region, self.latest_month, self.max_lag_months
        )

        band = self.band_pct(product_id, reference)
        # A median of two-decimal prices lands on a half cent (case C2: 3.295), so the reference keeps
        # three decimals; the band bounds are prices the user compares against and keep two.
        value = round(reference.price_brl_kg, 3)
        low = round(reference.low_brl_kg * (1 - band), 2)
        high = round(reference.high_brl_kg * (1 + band), 2)

        deviation: float | None = None
        position: PricePosition | None = None
        if price_brl_kg is not None:
            deviation = round(price_brl_kg / value - 1, 4)
            position = (
                PricePosition.WITHIN
                if low <= price_brl_kg <= high
                else PricePosition.BELOW
                if price_brl_kg < low
                else PricePosition.ABOVE
            )

        warnings = list(reference.warnings)
        if reference.lag_months >= 2:
            warnings.insert(
                0,
                f"série defasada: último preço observado é de {reference.month} "
                f"({reference.lag_months} meses, base até {self.latest_month}); "
                f"banda ampliada em {ptbr(100 * self.drift[reference.lag_months], 1)}%",
            )

        return PriceComparison(
            product_id=product_id,
            location=Location(uf=user_uf, region=region),
            reference_level=reference.level,
            entrepost_ids=reference.entrepost_ids,
            reference_month=reference.month,
            reference_price_brl_kg=value,
            band_low_brl_kg=low,
            band_high_brl_kg=high,
            band_pct=band,
            informed_price_brl_kg=price_brl_kg,
            deviation_pct=deviation,
            position=position,
            change_prev_month=(
                None
                if reference.change_prev_month is None
                else round(reference.change_prev_month, 4)
            ),
            confidence=reference.confidence,
            source=self.source,
            model_version=MODEL_VERSION,
            degraded=reference.degraded,
            warning="; ".join(warnings) if warnings else None,
        )


@lru_cache(maxsize=1)
def get_price_comparator() -> PriceComparator:
    """Cached instance for the FastAPI app (use as a dependency)."""
    return PriceComparator(get_market_dataset())


__all__ = [
    "MODEL_VERSION",
    "NATIONAL_BAND_PCT",
    "ComparisonError",
    "InvalidParameterError",
    "Location",
    "PriceComparator",
    "PriceComparison",
    "PricePosition",
    "ReferenceLevel",
    "UnknownIdError",
    "get_price_comparator",
]
