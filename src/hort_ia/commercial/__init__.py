"""Hort.IA commercial engine (WBS 9.5): reference prices and price comparison.

Price comparison is 9.5.1-4; the matching engine and its score are 9.5.1-5.
Approach and decision record: `docs/commercial/9.5.1-3_Abordagem_Comparacao_e_Matching.md`.
"""

from .bands import MAX_LAG_MONTHS, staleness_drift, tolerance_bands
from .pricing import (
    MODEL_VERSION,
    NATIONAL_BAND_PCT,
    ComparisonError,
    InvalidParameterError,
    Location,
    PriceComparator,
    PriceComparison,
    PricePosition,
    UnknownIdError,
    get_price_comparator,
)
from .reference import CONFIDENCE, ReferenceLevel, resolve_location, resolve_reference

__all__ = [
    "CONFIDENCE",
    "MAX_LAG_MONTHS",
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
    "resolve_location",
    "resolve_reference",
    "staleness_drift",
    "tolerance_bands",
]
