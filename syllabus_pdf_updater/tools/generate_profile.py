from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from document_analyzer import analyze_pdf


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Genera un perfil JSON de reemplazos sugeridos a partir de un PDF de syllabus.",
    )
    parser.add_argument("--pdf", required=True, help="Ruta al PDF de origen.")
    parser.add_argument(
        "--output",
        required=True,
        help="Ruta del archivo JSON de salida.",
    )
    parser.add_argument(
        "--include-empty",
        action="store_true",
        help="Incluye campos sin valor sugerido para completar manualmente.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        raise SystemExit(f"PDF no encontrado: {pdf_path}")

    analysis = analyze_pdf(pdf_path)
    replacements = []

    for field in analysis.suggested_fields:
        if not field.current_value:
            continue
        if not args.include_empty and not field.suggested_value:
            continue

        replacements.append(
            {
                "category": field.category,
                "label": field.label,
                "find": field.current_value,
                "replace": field.suggested_value,
            }
        )

    payload = {
        "app": "Syllabus PDF Updater Pro",
        "source_pdf": str(pdf_path),
        "page_count": analysis.page_count,
        "signed_source_detected": analysis.signed_source_detected,
        "replacements": replacements,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Perfil generado: {output_path}")
    print(f"Reemplazos incluidos: {len(replacements)}")


if __name__ == "__main__":
    main()
