from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata
from typing import Dict, Iterable, List, Tuple

import fitz


ReplacementPair = Tuple[str, str]


@dataclass
class ReplacementResult:
    output_path: Path
    total_replacements: int
    per_term: Dict[str, int]
    signed_source_detected: bool


@dataclass
class PreviewResult:
    total_matches: int
    per_term: Dict[str, int]
    signed_source_detected: bool


def detect_pdf_signature(path: Path) -> bool:
    raw = path.read_bytes()
    return b"/Sig" in raw and b"/ByteRange" in raw


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value or "")
    without_marks = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return without_marks.casefold().strip()


def _is_single_token(value: str) -> bool:
    return bool(re.fullmatch(r"\S+", value.strip()))


def _find_word_rects(page: fitz.Page, source: str) -> List[fitz.Rect]:
    expected = _normalize_text(source)
    rects: List[fitz.Rect] = []
    for word in page.get_text("words"):
        text = str(word[4])
        if _normalize_text(text) == expected:
            rects.append(fitz.Rect(word[:4]))
    return rects


def _find_rects(page: fitz.Page, source: str) -> List[fitz.Rect]:
    if _is_single_token(source):
        # Single-token replacements should match full words only.
        return _find_word_rects(page, source)
    return [fitz.Rect(item) for item in page.search_for(source)]


def _normalize_pairs(replacements: Iterable[ReplacementPair]) -> List[ReplacementPair]:
    unique: Dict[str, str] = {}
    for source, target in replacements:
        src = source.strip()
        if not src:
            continue
        unique[src] = target
    # Replace longer terms first to reduce partial overlap side-effects.
    pairs = sorted(unique.items(), key=lambda item: len(item[0]), reverse=True)
    return [(source, target) for source, target in pairs]


def _insert_text_fitting(page: fitz.Page, rect: fitz.Rect, text: str) -> None:
    target = fitz.Rect(rect)
    max_size = min(max(target.height * 0.78, 7.0), 13.0)
    min_size = 5.5
    size = max_size

    while size >= min_size:
        overflow = page.insert_textbox(
            target,
            text,
            fontsize=size,
            fontname="helv",
            color=(0, 0, 0),
            align=fitz.TEXT_ALIGN_LEFT,
        )
        if overflow >= 0:
            return
        size -= 0.5

    page.insert_textbox(
        target,
        text,
        fontsize=min_size,
        fontname="helv",
        color=(0, 0, 0),
        align=fitz.TEXT_ALIGN_LEFT,
    )


def preview_replacements(
    input_path: Path,
    replacements: Iterable[ReplacementPair],
) -> PreviewResult:
    pairs = _normalize_pairs(replacements)
    per_term: Dict[str, int] = {source: 0 for source, _ in pairs}
    signed_source = detect_pdf_signature(input_path)
    doc = fitz.open(str(input_path))
    try:
        for page in doc:
            for source, _target in pairs:
                hits = _find_rects(page, source)
                if hits:
                    per_term[source] += len(hits)
    finally:
        doc.close()

    return PreviewResult(
        total_matches=sum(per_term.values()),
        per_term=per_term,
        signed_source_detected=signed_source,
    )


def replace_text_in_pdf(
    input_path: Path,
    output_path: Path,
    replacements: Iterable[ReplacementPair],
) -> ReplacementResult:
    pairs = _normalize_pairs(replacements)
    signed_source = detect_pdf_signature(input_path)
    per_term: Dict[str, int] = {source: 0 for source, _ in pairs}

    doc = fitz.open(str(input_path))
    try:
        for page in doc:
            for source, target in pairs:
                rects = _find_rects(page, source)
                if not rects:
                    continue

                for rect in rects:
                    page.add_redact_annot(rect, fill=(1, 1, 1))
                page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

                for rect in rects:
                    _insert_text_fitting(page, rect, target)

                per_term[source] += len(rects)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path), garbage=4, deflate=True)
    finally:
        doc.close()

    total = sum(per_term.values())
    return ReplacementResult(
        output_path=output_path,
        total_replacements=total,
        per_term=per_term,
        signed_source_detected=signed_source,
    )
