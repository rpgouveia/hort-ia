"""Batch image filtering and standardization for dataset preparation (WBS 9.1.2-1 & 9.1.2-3).

Processes an input directory of raw plant images:
1. Filters out low-quality, blurry, under/over-exposed or corrupt images (moves to quarantine).
2. Standardizes valid images to 224x224 px, RGB, optimized JPEG with stripped EXIF (LGPD).
3. Produces a detailed JSON report of the curation process.

Usage:
    python scripts/process_image_dataset.py <input_dir> <output_dir>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hort_ia.cv import ImagePipeline, PipelineConfig

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def process_dataset(
    input_dir: Path, output_dir: Path, config: PipelineConfig | None = None
) -> dict:
    pipeline = ImagePipeline(config)
    processed_dir = output_dir / "standardized"
    quarantine_dir = output_dir / "quarantine"
    processed_dir.mkdir(parents=True, exist_ok=True)
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    files = [p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() in VALID_EXTENSIONS]

    total = len(files)
    approved = 0
    quarantined = 0
    results = []

    for file_path in files:
        try:
            image_bytes = file_path.read_bytes()
            assessment, info, encoded_bytes, _ = pipeline.process(image_bytes, require_valid=False)

            if assessment.is_valid and info and encoded_bytes:
                out_name = f"{file_path.stem}.jpg"
                (processed_dir / out_name).write_bytes(encoded_bytes)
                approved += 1
                status = "approved"
            else:
                # Move original to quarantine with metadata log
                out_name = file_path.name
                (quarantine_dir / out_name).write_bytes(image_bytes)
                quarantined += 1
                status = "quarantined"

            results.append({
                "file": str(file_path.relative_to(input_dir)),
                "status": status,
                "assessment": assessment.model_dump(),
                "standardized_size_bytes": info.size_bytes if info else None,
            })
        except Exception as err:
            quarantined += 1
            results.append({
                "file": str(file_path.relative_to(input_dir)),
                "status": "error",
                "error": str(err),
            })

    summary = {
        "total_images": total,
        "approved": approved,
        "quarantined": quarantined,
        "approval_rate": round(approved / total, 4) if total > 0 else 0.0,
        "results": results,
    }

    report_path = output_dir / "processing_report.json"
    report_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Image dataset filtering and standardization.")
    parser.add_argument("input_dir", type=Path, help="Path to raw images folder")
    parser.add_argument("output_dir", type=Path, help="Path for processed dataset")
    args = parser.parse_args()

    if not args.input_dir.exists():
        print(f"Erro: diretório de entrada não existe: {args.input_dir}")
        sys.exit(1)

    print(f"Iniciando curadoria de {args.input_dir}...")
    summary = process_dataset(args.input_dir, args.output_dir)
    print(f"Concluído! Aprovadas: {summary['approved']}/{summary['total_images']} "
          f"({summary['approval_rate']:.1%}). Relatório salvo em {args.output_dir / 'processing_report.json'}")


if __name__ == "__main__":
    main()
