"""Image filtering and standardization engine

Optimized for entry-level mobile devices (smartphones de entrada), low-bandwidth
connectivity environments and strict LGPD compliance (metadata stripping).
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np
from PIL import Image

from .models import ImageQualityAssessment, StandardizedImageInfo


class ImageProcessingError(Exception):
    """Raised when an image cannot be decoded or processed."""


@dataclass(frozen=True)
class PipelineConfig:
    """Thresholds and target specifications for entry-level mobile devices."""

    target_size: tuple[int, int] = (224, 224)
    min_resolution: tuple[int, int] = (128, 128)
    min_blur_score: float = 75.0  # Laplacian variance threshold
    min_brightness: float = 35.0  # Under-exposure limit (0-255)
    max_brightness: float = 230.0  # Over-exposure limit (0-255)
    min_contrast: float = 18.0  # Minimum standard deviation
    jpeg_quality: int = 85  # Balance between bandwidth (<100KB) and visual fidelity
    output_format: Literal["JPEG", "WEBP"] = "JPEG"
    strip_metadata: bool = True  # LGPD compliance


class ImagePipeline:
    def __init__(self, config: PipelineConfig | None = None):
        self.config = config or PipelineConfig()

    def _decode_image(self, image_bytes: bytes) -> tuple[np.ndarray, str | None, tuple[int, int]]:
        """Decode byte stream into an RGB numpy array and extract format/dimensions."""
        try:
            pil_img = Image.open(io.BytesIO(image_bytes))
            detected_format = pil_img.format
            width, height = pil_img.size

            # Convert to RGB (handles RGBA, Grayscale, CMYK, etc.)
            if pil_img.mode != "RGB":
                pil_img = pil_img.convert("RGB")

            # Convert PIL RGB to OpenCV BGR representation
            rgb_arr = np.array(pil_img)
            bgr_arr = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)
            return bgr_arr, detected_format, (width, height)
        except Exception as error:
            raise ImageProcessingError(f"Arquivo corrompido ou formato de imagem inválido: {error}") from error

    def assess_quality(self, image_bytes: bytes) -> tuple[ImageQualityAssessment, np.ndarray]:
        """Assess quality (blur, illumination, contrast, resolution) without modifying the image."""
        size_bytes = len(image_bytes)
        bgr, detected_format, (w, h) = self._decode_image(image_bytes)

        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

        # 1. Blur detection via Laplacian variance
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # 2. Illumination / Brightness
        brightness_score = float(np.mean(gray))

        # 3. Contrast / Dispersion
        contrast_score = float(np.std(gray))

        # Rejection checks
        reasons: list[str] = []
        feedback_parts: list[str] = []

        min_w, min_h = self.config.min_resolution
        if w < min_w or h < min_h:
            reasons.append(f"Resolução muito baixa ({w}x{h}). Mínimo exigido: {min_w}x{min_h}.")
            feedback_parts.append("Aproxime mais a câmera da folha com boa iluminação.")

        if blur_score < self.config.min_blur_score:
            reasons.append(
                f"Imagem borrada ou fora de foco (nitidez: {blur_score:.1f}, mínimo: {self.config.min_blur_score:.1f})."
            )
            feedback_parts.append("Segure o celular com firmeza e toque na tela para focar antes de tirar a foto.")

        if brightness_score < self.config.min_brightness:
            reasons.append(
                f"Imagem muito escura (brilho: {brightness_score:.1f}, mínimo: {self.config.min_brightness:.1f})."
            )
            feedback_parts.append("O ambiente está escuro. Tire a foto em local com mais luz natural ou use o flash.")
        elif brightness_score > self.config.max_brightness:
            reasons.append(
                f"Imagem com excesso de claridade / reflexo (brilho: {brightness_score:.1f}, máximo: {self.config.max_brightness:.1f})."
            )
            feedback_parts.append("A foto ficou muito clara pelo reflexo do sol. Mude o ângulo para evitar o reflexo direto.")

        if contrast_score < self.config.min_contrast:
            reasons.append(
                f"Imagem com baixíssimo contraste (contraste: {contrast_score:.1f}, mínimo: {self.config.min_contrast:.1f})."
            )
            feedback_parts.append("A imagem não apresenta detalhes visíveis da planta.")

        is_valid = len(reasons) == 0
        user_feedback = "Foto com ótima qualidade para diagnóstico." if is_valid else " ".join(feedback_parts)

        assessment = ImageQualityAssessment(
            is_valid=is_valid,
            rejection_reasons=reasons,
            user_feedback=user_feedback,
            blur_score=round(blur_score, 2),
            brightness_score=round(brightness_score, 2),
            contrast_score=round(contrast_score, 2),
            original_resolution=(w, h),
            original_format=detected_format,
            original_size_bytes=size_bytes,
        )
        return assessment, bgr

    def standardize(
        self, bgr_image: np.ndarray, assessment: ImageQualityAssessment
    ) -> tuple[StandardizedImageInfo, bytes, np.ndarray]:
        """Resize to target dimensions (with aspect-ratio padding) and compress cleanly (no EXIF)."""
        target_w, target_h = self.config.target_size
        h, w = bgr_image.shape[:2]

        # Calculate scale to fit inside target size while preserving aspect ratio
        scale = min(target_w / w, target_h / h)
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))

        # Downscaling interpolation
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
        resized = cv2.resize(bgr_image, (new_w, new_h), interpolation=interp)

        # Symmetric padding to reach exact target_size (224x224)
        pad_top = (target_h - new_h) // 2
        pad_bottom = target_h - new_h - pad_top
        pad_left = (target_w - new_w) // 2
        pad_right = target_w - new_w - pad_left

        padded_bgr = cv2.copyMakeBorder(
            resized, pad_top, pad_bottom, pad_left, pad_right, cv2.BORDER_CONSTANT, value=(0, 0, 0)
        )

        # Convert to RGB for model input and storage
        padded_rgb = cv2.cvtColor(padded_bgr, cv2.COLOR_BGR2RGB)

        # Encode with PIL to guarantee stripping of all EXIF metadata (LGPD compliance)
        pil_out = Image.fromarray(padded_rgb)
        buf = io.BytesIO()
        pil_out.save(buf, format=self.config.output_format, quality=self.config.jpeg_quality, optimize=True)
        encoded_bytes = buf.getvalue()

        info = StandardizedImageInfo(
            width=target_w,
            height=target_h,
            channels=3,
            color_space="RGB",
            format=self.config.output_format,
            size_bytes=len(encoded_bytes),
            exif_stripped=self.config.strip_metadata,
            quality_assessment=assessment,
        )
        return info, encoded_bytes, padded_rgb

    def process(
        self, image_bytes: bytes, require_valid: bool = True
    ) -> tuple[ImageQualityAssessment, StandardizedImageInfo | None, bytes | None, np.ndarray | None]:
        """End-to-end execution: assess quality and, if valid, standardize."""
        assessment, bgr = self.assess_quality(image_bytes)
        if require_valid and not assessment.is_valid:
            return assessment, None, None, None

        info, encoded_bytes, rgb_arr = self.standardize(bgr, assessment)
        return assessment, info, encoded_bytes, rgb_arr
