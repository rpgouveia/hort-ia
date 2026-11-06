"""Hort.IA agronomic recommendation engine (WBS 9.3).

The engine is 9.3.1-4; the profile integration and the routes are 9.3.1-5.
Approach and decision record: `docs/recommender/9.3.1-3_Abordagem_Motor_Recomendacao.md`.
"""

from .engine import (
    MODEL_VERSION,
    SEASON_ENDING_MONTHS,
    W_COMPANION,
    W_REPELLENT,
    Recommender,
    get_recommender,
    load_texts,
    months_left,
)
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

__all__ = [
    "MODEL_VERSION",
    "SEASON_ENDING_MONTHS",
    "W_COMPANION",
    "W_REPELLENT",
    "Exclusion",
    "ExclusionReason",
    "Profile",
    "Reason",
    "ReasonCode",
    "RecommendationResult",
    "RecommendedCrop",
    "Recommender",
    "RecommenderError",
    "get_recommender",
    "load_texts",
    "months_left",
]
