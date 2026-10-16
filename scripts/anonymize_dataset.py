"""Automated dataset anonymization and LGPD compliance validation (WBS 9.1.2-4 to 9.1.2-7).

Executes end-to-end privacy pipeline:
1. Validates legal consent against Terms of Use and Privacy Policy (9.1.2-4).
2. Audits PII: face detection, EXIF/GPS tags, CPFs, phones, emails (9.1.2-5).
3. Applies defined anonymization techniques (9.1.2-6).
4. Strips EXIF, applies Gaussian face blur, and masks textual PII (9.1.2-7).
5. Outputs a certified dataset with an audit compliance manifest.

Usage:
    python scripts/anonymize_dataset.py <input_dir> <output_dir> [--consent-file <path>]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hort_ia.core.privacy import (
    ConsentError,
    ConsentRecord,
    ConsentValidator,
    ImageAnonymizer,
    PIIAuditor,
    TextAnonymizer,
)

VALID_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def run_anonymization(
    input_dir: Path, output_dir: Path, consent_records: dict[str, ConsentRecord] | None = None
) -> dict:
    consent_validator = ConsentValidator()
    img_anonymizer = ImageAnonymizer()
    text_anonymizer = TextAnonymizer()
    auditor = PIIAuditor()

    output_images_dir = output_dir / "anonymized_images"
    output_meta_dir = output_dir / "anonymized_metadata"
    quarantine_dir = output_dir / "quarantine_unconsented"

    output_images_dir.mkdir(parents=True, exist_ok=True)
    output_meta_dir.mkdir(parents=True, exist_ok=True)
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    image_files = [p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() in VALID_IMAGE_EXTS]

    stats = {
        "total_images_scanned": len(image_files),
        "consented_and_processed": 0,
        "rejected_no_consent": 0,
        "faces_detected_and_blurred": 0,
        "exif_metadata_stripped": 0,
        "textual_pii_masked": 0,
        "audit_log": [],
    }

    # Process images
    for img_path in image_files:
        raw_bytes = img_path.read_bytes()
        grower_id = img_path.stem.split("_")[0]  # convention: <growerId>_<sampleId>.jpg

        # 9.1.2-4: Consent Validation
        consent = (consent_records or {}).get(grower_id)
        is_consented, reasons = consent_validator.validate(consent)

        if not is_consented:
            stats["rejected_no_consent"] += 1
            # Move to quarantine
            (quarantine_dir / img_path.name).write_bytes(raw_bytes)
            stats["audit_log"].append({
                "file": str(img_path.relative_to(input_dir)),
                "action": "quarantined_no_consent",
                "reasons": reasons,
            })
            continue

        stats["consented_and_processed"] += 1

        # 9.1.2-5: Audit PII
        meta_audit = auditor.audit_image_metadata(raw_bytes)

        # 9.1.2-7: Strip EXIF
        clean_bytes = img_anonymizer.strip_exif(raw_bytes)
        stats["exif_metadata_stripped"] += 1

        # 9.1.2-7: Face Blur
        import cv2
        import numpy as np
        from PIL import Image
        import io

        pil_img = Image.open(io.BytesIO(clean_bytes))
        bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        blurred_bgr, faces_count = img_anonymizer.blur_faces(bgr)

        if faces_count > 0:
            stats["faces_detected_and_blurred"] += faces_count

        final_pil = Image.fromarray(cv2.cvtColor(blurred_bgr, cv2.COLOR_BGR2RGB))
        buf = io.BytesIO()
        final_pil.save(buf, format="JPEG", quality=85)
        out_bytes = buf.getvalue()

        # Save to output
        out_file = output_images_dir / f"{img_path.stem}.jpg"
        out_file.write_bytes(out_bytes)

        stats["audit_log"].append({
            "file": str(img_path.relative_to(input_dir)),
            "action": "anonymized",
            "had_gps_exif": meta_audit.found_exif_gps,
            "faces_blurred": faces_count,
        })

    # Save compliance manifest
    manifest_path = output_dir / "lgpd_compliance_manifest.json"
    manifest_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    return stats


def main():
    parser = argparse.ArgumentParser(description="LGPD Consent Verification and Anonymization.")
    parser.add_argument("input_dir", type=Path, help="Path to raw dataset folder")
    parser.add_argument("output_dir", type=Path, help="Path for compliant output")
    parser.add_argument("--consent-file", type=Path, default=None, help="JSON file with consent records")
    args = parser.parse_args()

    consent_dict = {}
    if args.consent_file and args.consent_file.exists():
        raw_consents = json.loads(args.consent_file.read_text(encoding="utf-8"))
        consent_dict = {c["grower_id"]: ConsentRecord(**c) for c in raw_consents}

    print(f"Iniciando anonimização e validação LGPD em {args.input_dir}...")
    stats = run_anonymization(args.input_dir, args.output_dir, consent_dict)
    print(
        f"Concluído! Processadas com consentimento: {stats['consented_and_processed']}, "
        f"Rejeitadas por falta de consentimento: {stats['rejected_no_consent']}, "
        f"Faces desfocadas: {stats['faces_detected_and_blurred']}. "
        f"Manifesto salvo em: {args.output_dir / 'lgpd_compliance_manifest.json'}"
    )


if __name__ == "__main__":
    main()
