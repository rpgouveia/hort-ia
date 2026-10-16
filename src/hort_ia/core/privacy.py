"""Data privacy, consent validation and anonymization engine (LGPD compliant).
"""

from __future__ import annotations

import hashlib
import io
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

CASCADE_PATH = Path(__file__).resolve().parents[1] / "cv" / "resources" / "haarcascade_frontalface_default.xml"


# =============================================================================
# 9.1.2-4: Consent Validation Models & Engine (Art. 7, I and Art. 8 of LGPD)
# =============================================================================


class ConsentError(Exception):
    """Raised when data cannot be processed due to missing or invalid legal consent."""


class ConsentRecord(BaseModel):
    """Explicit consent register ensuring auditability and traceability under LGPD."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    grower_id: str
    consent_given: bool
    purpose: str = Field(description="Must cover AI model training and inference")
    terms_version: str = "v1.0"
    privacy_policy_version: str = "v1.0"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    revoked: bool = False


class ConsentValidator:
    """Validates user consent before allowing data ingestion or model training."""

    def __init__(self, min_terms_version: str = "v1.0", min_policy_version: str = "v1.0"):
        self.min_terms_version = min_terms_version
        self.min_policy_version = min_policy_version

    def validate(self, consent: ConsentRecord | None) -> tuple[bool, list[str]]:
        reasons = []
        if consent is None:
            return False, ["Consentimento não informado (ausente)."]

        if not consent.consent_given:
            reasons.append("Consentimento não concedido pelo titular.")

        if consent.revoked:
            reasons.append("Consentimento revogado pelo titular dos dados.")

        valid_purposes = {"ai_training", "ai_training_and_inference", "hort_ia_platform", "pesquisa_e_manejo"}
        if not any(p in consent.purpose.lower() for p in valid_purposes):
            reasons.append(
                f"Finalidade declarada ({consent.purpose!r}) não autoriza uso para inteligência artificial."
            )

        if consent.terms_version < self.min_terms_version:
            reasons.append(
                f"Versão dos Termos de Uso ({consent.terms_version}) inferior à mínima ({self.min_terms_version})."
            )

        if consent.privacy_policy_version < self.min_policy_version:
            reasons.append(
                f"Versão da Política de Privacidade ({consent.privacy_policy_version}) inferior à mínima ({self.min_policy_version})."
            )

        return len(reasons) == 0, reasons

    def assert_valid(self, consent: ConsentRecord | None) -> None:
        is_valid, reasons = self.validate(consent)
        if not is_valid:
            raise ConsentError("Conformidade LGPD violada: " + "; ".join(reasons))


# =============================================================================
# 9.1.2-5: PII Identification & Audit (Texts and Images)
# =============================================================================


@dataclass
class PIIAuditReport:
    """Findings from exploratory scan for Personally Identifiable Information."""

    found_faces: int = 0
    found_exif_gps: bool = False
    found_exif_device_info: bool = False
    found_cpfs: list[str] = field(default_factory=list)
    found_emails: list[str] = field(default_factory=list)
    found_phones: list[str] = field(default_factory=list)
    found_grower_names: list[str] = field(default_factory=list)

    @property
    def has_sensitive_data(self) -> bool:
        return (
            self.found_faces > 0
            or self.found_exif_gps
            or self.found_exif_device_info
            or bool(self.found_cpfs)
            or bool(self.found_emails)
            or bool(self.found_phones)
            or bool(self.found_grower_names)
        )


class PIIAuditor:
    """Scans texts and images to locate PII before applying anonymization."""

    CPF_REGEX = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
    EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    PHONE_REGEX = re.compile(r"(?:\(?\d{2}\)?\s?)?(?:9\s?)?\d{4}[-\s]?\d{4}\b")

    def audit_text(self, text: str, known_names: list[str] | None = None) -> PIIAuditReport:
        report = PIIAuditReport()
        report.found_cpfs = self.CPF_REGEX.findall(text)
        report.found_emails = self.EMAIL_REGEX.findall(text)
        report.found_phones = self.PHONE_REGEX.findall(text)

        if known_names:
            for name in known_names:
                if re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE):
                    report.found_grower_names.append(name)
        return report

    def audit_image_metadata(self, image_bytes: bytes) -> PIIAuditReport:
        report = PIIAuditReport()
        try:
            pil_img = Image.open(io.BytesIO(image_bytes))
            exif = pil_img.getexif()
            if exif:
                # 0x8825 is GPSInfo tag in EXIF
                if 0x8825 in exif:
                    report.found_exif_gps = True
                # Camera Model (0x0110), Make (0x010F), Software (0x0131), Serial (0xA431)
                device_tags = {0x010F, 0x0110, 0x0131, 0xA431}
                if any(tag in exif for tag in device_tags):
                    report.found_exif_device_info = True
        except Exception:
            pass
        return report


# =============================================================================
# 9.1.2-6 & 9.1.2-7: Anonymization Techniques & Implementation
# =============================================================================


class ImageAnonymizer:
    """Anonymizes images by blurring detected human faces and stripping EXIF tags."""

    def __init__(self, cascade_path: Path | str | None = None):
        self.cascade_path = str(cascade_path or CASCADE_PATH)
        self.face_cascade = None
        if hasattr(cv2, "CascadeClassifier") and os.path.exists(self.cascade_path):
            try:
                cascade = cv2.CascadeClassifier(self.cascade_path)
                if not cascade.empty():
                    self.face_cascade = cascade
            except Exception:
                self.face_cascade = None

    def detect_face_regions(self, bgr_image: np.ndarray) -> list[tuple[int, int, int, int]]:
        """Detect candidate face or skin regions in background."""
        # Method A: Haar cascade if available
        if self.face_cascade is not None and not self.face_cascade.empty():
            gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(24, 24),
            )
            if len(faces) > 0:
                return [tuple(f) for f in faces]

        # Method B: Robust skin-color segmentation in YCrCb color space
        # Standard range for human skin tone: Y in [0, 255], Cr in [133, 173], Cb in [77, 127]
        ycrcb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2YCrCb)
        lower_skin = np.array([0, 133, 77], dtype=np.uint8)
        upper_skin = np.array([255, 173, 127], dtype=np.uint8)
        mask = cv2.inRange(ycrcb, lower_skin, upper_skin)

        # Morphological opening and closing to remove noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        h_img, w_img = bgr_image.shape[:2]
        min_area = (w_img * h_img) * 0.005  # At least 0.5% of the image

        boxes = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area >= min_area:
                x, y, w, h = cv2.boundingRect(cnt)
                aspect_ratio = float(w) / h
                # Face/body parts usually have aspect ratio between 0.4 and 2.2
                if 0.4 <= aspect_ratio <= 2.2:
                    boxes.append((x, y, w, h))

        return boxes

    def blur_faces(
        self, bgr_image: np.ndarray, manual_boxes: list[tuple[int, int, int, int]] | None = None
    ) -> tuple[np.ndarray, int]:
        """Apply heavy non-reversible Gaussian blur to detected or specified face regions."""
        boxes = manual_boxes if manual_boxes is not None else self.detect_face_regions(bgr_image)
        if not boxes:
            return bgr_image, 0

        anonymized = bgr_image.copy()
        for x, y, w, h in boxes:
            roi = anonymized[y : y + h, x : x + w]
            if roi.size == 0:
                continue
            ksize = max(51, (min(w, h) // 2) * 2 + 1)
            blurred = cv2.GaussianBlur(roi, (ksize, ksize), 30)
            anonymized[y : y + h, x : x + w] = blurred

        return anonymized, len(boxes)

    def strip_exif(self, image_bytes: bytes, output_format: str = "JPEG", quality: int = 85) -> bytes:
        """Completely decode and re-encode to drop 100% of EXIF/GPS metadata."""
        pil_img = Image.open(io.BytesIO(image_bytes))
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")

        # Create pure pixel array dropping any PIL image metadata dictionary
        clean_img = Image.fromarray(np.array(pil_img))
        buf = io.BytesIO()
        clean_img.save(buf, format=output_format, quality=quality, optimize=True)
        return buf.getvalue()


class TextAnonymizer:
    """Sanitizes agronomic texts, replacing PII with pseudonyms or generic tokens."""

    def __init__(self, salt: str = "hortia_salt_2026"):
        self.salt = salt

    def generate_pseudonym(self, real_name: str, prefix: str = "Produtor") -> str:
        """Create deterministic, opaque pseudonym using SHA-256."""
        h = hashlib.sha256(f"{self.salt}:{real_name.strip().lower()}".encode()).hexdigest()[:6]
        return f"{prefix}_{h}"

    def anonymize_text(
        self,
        text: str,
        name_map: dict[str, str] | None = None,
    ) -> str:
        """Sanitizes CPFs, phones, emails and substitutes registered names."""
        clean = text
        # Mask CPF
        clean = re.sub(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", "[CPF_REMOVIDO]", clean)
        # Mask Email
        clean = re.sub(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[EMAIL_REMOVIDO]", clean
        )
        # Mask Phone
        clean = re.sub(r"(?:\(?\d{2}\)?\s?)?(?:9\s?)?\d{4}[-\s]?\d{4}\b", "[TELEFONE_REMOVIDO]", clean)

        # Substitute registered names with pseudonyms
        if name_map:
            for real_name, pseudo in name_map.items():
                pattern = re.compile(rf"\b{re.escape(real_name)}\b", re.IGNORECASE)
                clean = pattern.sub(pseudo, clean)

        return clean

    def anonymize_grower_record(
        self, record: dict[str, Any], known_names: list[str] | None = None
    ) -> dict[str, Any]:
        """Anonymizes a dictionary representing a farm/grower record."""
        sanitized = dict(record)

        # Grower real name -> pseudonym
        if "grower_name" in sanitized:
            real = str(sanitized.pop("grower_name"))
            sanitized["grower_pseudo_id"] = self.generate_pseudonym(real)

        # Phone / Document / Email
        for sensitive in ("cpf", "email", "phone", "telefone", "documento"):
            if sensitive in sanitized:
                sanitized.pop(sensitive, None)

        # Anonymize notes or remarks
        if "notes" in sanitized and isinstance(sanitized["notes"], str):
            sanitized["notes"] = self.anonymize_text(sanitized["notes"])

        return sanitized


# =============================================================================
# End-to-End Privacy Pipeline
# =============================================================================


class PrivacyPipeline:
    """Orchestrates legal consent validation, metadata stripping and face blur."""

    def __init__(
        self,
        validator: ConsentValidator | None = None,
        image_anonymizer: ImageAnonymizer | None = None,
        text_anonymizer: TextAnonymizer | None = None,
    ):
        self.validator = validator or ConsentValidator()
        self.img_anonymizer = image_anonymizer or ImageAnonymizer()
        self.text_anonymizer = text_anonymizer or TextAnonymizer()
        self.auditor = PIIAuditor()

    def process_submission(
        self,
        image_bytes: bytes,
        consent: ConsentRecord,
        text_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate consent and anonymize image and metadata. Aborts if consent fails."""
        # 1. Validate Legal Consent
        self.validator.assert_valid(consent)

        # 2. Audit initial state
        meta_audit = self.auditor.audit_image_metadata(image_bytes)

        # 3. Strip EXIF
        clean_bytes = self.img_anonymizer.strip_exif(image_bytes)

        # 4. Blur faces if any present
        pil_img = Image.open(io.BytesIO(clean_bytes))
        bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        blurred_bgr, faces_blurred = self.img_anonymizer.blur_faces(bgr)

        # Re-encode clean image
        final_pil = Image.fromarray(cv2.cvtColor(blurred_bgr, cv2.COLOR_BGR2RGB))
        out_buf = io.BytesIO()
        final_pil.save(out_buf, format="JPEG", quality=85)
        final_bytes = out_buf.getvalue()

        # 5. Anonymize metadata text
        clean_metadata = None
        if text_metadata:
            clean_metadata = self.text_anonymizer.anonymize_grower_record(text_metadata)

        return {
            "status": "anonymized_and_compliant",
            "consent_validated": True,
            "grower_id": consent.grower_id,
            "faces_blurred": faces_blurred,
            "exif_stripped": True,
            "initial_had_gps": meta_audit.found_exif_gps,
            "anonymized_image_bytes": final_bytes,
            "anonymized_metadata": clean_metadata,
        }
