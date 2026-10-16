from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ImageQualityAssessment(BaseModel):
    """Result of quality filtering: sharpness, brightness, contrast and compatibility."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    is_valid: bool
    rejection_reasons: list[str] = Field(default_factory=list)
    user_feedback: str | None = None  # Friendly prompt in plain Portuguese for urban growers
    blur_score: float = Field(description="Laplacian variance (> 80 is considered sharp)")
    brightness_score: float = Field(description="Mean grayscale brightness (35 to 230 acceptable)")
    contrast_score: float = Field(description="Standard deviation of pixel intensity (> 18 acceptable)")
    original_resolution: tuple[int, int]  # (width, height)
    original_format: str | None = None
    original_size_bytes: int


class StandardizedImageInfo(BaseModel):
    """Metadata of the standardized image ready for entry-level mobile devices and ML models."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    width: int = 224
    height: int = 224
    channels: int = 3
    color_space: Literal["RGB"] = "RGB"
    format: Literal["JPEG", "WEBP"] = "JPEG"
    size_bytes: int
    exif_stripped: bool = True  # LGPD compliance: no GPS or device hardware metadata retained
    quality_assessment: ImageQualityAssessment
