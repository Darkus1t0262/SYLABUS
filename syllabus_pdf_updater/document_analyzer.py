from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import unicodedata
from typing import Dict, Iterable, List, Tuple

import fitz


@dataclass
class SuggestedField:
    category: str
    label: str
    current_value: str
    suggested_value: str = ""


@dataclass
class DocumentAnalysis:
    pdf_path: Path
    page_count: int
    searchable_pages: int
    signed_source_detected: bool
    suggested_fields: List[SuggestedField] = field(default_factory=list)
    unit_names: List[str] = field(default_factory=list)
    weekly_topics: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


_STOP_MARKERS = (
    "REVISIÓN DE LA UNIDAD",
    "REVISION DE LA UNIDAD",
    "LEER LA BIBLIOGRAFIA",
    "FOROS DE DISCUSION",
    "CASO DE ESTUDIO",
    "EJEMPLOS",
    "INVESTIGACION BIBLIOGRAFICA",
    "RESPONDER PREGUNTAS",
    "TRABAJO AUTONOMO",
)


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _normalized_upper(value: str) -> str:
    return _strip_accents(value).upper()


def _clean_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _detect_pdf_signature(path: Path) -> bool:
    raw = path.read_bytes()
    return b"/Sig" in raw and b"/ByteRange" in raw


def _next_period_value(lines: List[str], start_index: int) -> str:
    stop_words = (
        "PERIODO DE EJECUCION",
        "PROYECTO INTEGRADOR",
        "ORGANIZACION DEL APRENDIZAJE",
    )
    for idx in range(start_index, min(start_index + 8, len(lines))):
        candidate = lines[idx]
        upper = _normalized_upper(candidate)
        if not candidate:
            continue
        if "_" in candidate:
            continue
        if candidate.startswith("(") and candidate.endswith(")"):
            continue
        if any(stop in upper for stop in stop_words):
            break
        return candidate
    return ""


def _extract_basic_fields(lines: List[str]) -> Dict[str, str]:
    labels = [
        "FACULTAD",
        "CARRERA",
        "MODALIDAD",
        "ASIGNATURA O EQUIVALENTE",
        "CODIGO",
        "CÓDIGO",
    ]
    label_pattern = "|".join(re.escape(item) for item in labels)
    pair_rx = re.compile(
        rf"(?P<label>{label_pattern}):\s*(?P<value>.*?)(?=(?:\s+(?:{label_pattern}):)|$)",
        flags=re.IGNORECASE,
    )

    extracted: Dict[str, str] = {}
    for line in lines:
        for match in pair_rx.finditer(line):
            raw_label = _normalized_upper(match.group("label"))
            value = _clean_line(match.group("value"))
            if not value:
                continue
            if raw_label == "CODIGO":
                raw_label = "CÓDIGO"
            extracted[raw_label] = value
    return extracted


def _extract_period_fields(lines: List[str]) -> Dict[str, str]:
    found: Dict[str, str] = {}
    for idx, line in enumerate(lines):
        upper = _normalized_upper(line)
        if "PERIODO ACADEMICO" in upper and "PERÍODO ACADÉMICO" not in found:
            value = _next_period_value(lines, idx + 1)
            if value:
                found["PERÍODO ACADÉMICO"] = value
        if "PERIODO DE EJECUCION" in upper and "PERÍODO DE EJECUCIÓN" not in found:
            value = _next_period_value(lines, idx + 1)
            if value:
                found["PERÍODO DE EJECUCIÓN"] = value
    return found


def _is_role_stop_line(value: str) -> bool:
    upper = _normalized_upper(value)
    if not value.strip():
        return True
    if "_" in value:
        return True
    if upper.startswith("FECHA"):
        return True
    if upper in {
        "DOCENTE",
        "COORDINADOR AREA",
        "DIRECTOR/A DE CARRERA",
        "CONSEJO DE CARRERA",
        "EJERCICIO PROFESIONAL",
    }:
        return True
    return False


def _extract_name_after_role(lines: List[str], role_keyword: str) -> str:
    role_key = _normalized_upper(role_keyword)
    title_rx = re.compile(r"^(Dr\.|Ing\.|Lic\.|Mgs\.|Mgtr\.|MSc\.|PhD\.?|Abg\.|Arq\.)\s+", re.I)
    plain_name_rx = re.compile(r"^[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ.'-]+(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ.'-]+){0,3}$")
    suffix_rx = re.compile(r"^(PhD|MSc|MBA|Mgtr\.?|Mgs\.?)$", re.I)

    for idx, line in enumerate(lines):
        if role_key not in _normalized_upper(line):
            continue

        for probe_idx in range(idx, min(idx + 6, len(lines))):
            candidate = lines[probe_idx]
            if _is_role_stop_line(candidate):
                continue

            if title_rx.match(candidate):
                parts = [candidate]
                for extra_idx in range(probe_idx + 1, min(probe_idx + 4, len(lines))):
                    extra = lines[extra_idx]
                    if _is_role_stop_line(extra):
                        break
                    if plain_name_rx.match(extra) or suffix_rx.match(extra):
                        parts.append(extra)
                    else:
                        break
                return _clean_line(" ".join(parts))

            if plain_name_rx.match(candidate):
                return candidate

    return ""


def _extract_signature_name(lines: List[str]) -> str:
    marker = "FIRMADO ELECTRONICAMENTE POR"
    for idx, line in enumerate(lines):
        if marker not in _normalized_upper(line):
            continue
        pieces: List[str] = []
        for probe_idx in range(idx + 1, min(idx + 6, len(lines))):
            candidate = lines[probe_idx]
            upper = _normalized_upper(candidate)
            if _is_role_stop_line(candidate):
                continue
            if "VALIDAR UNICAMENTE" in upper:
                break
            if re.fullmatch(r"[A-ZÁÉÍÓÚÑ ]{4,}", candidate):
                pieces.append(candidate.title())
            elif re.fullmatch(r"[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ.'-]+(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ.'-]+){0,4}", candidate):
                pieces.append(candidate)
            else:
                break
        if pieces:
            return _clean_line(" ".join(pieces))
    return ""


def _extract_units(lines: Iterable[str]) -> List[str]:
    units: List[str] = []
    seen = set()
    for line in lines:
        if not line:
            continue
        upper = _normalized_upper(line)
        if not upper.startswith("NOMBRE:"):
            continue
        value = _clean_line(line.split(":", 1)[1])
        if not value or "_" in value:
            continue
        if value in seen:
            continue
        seen.add(value)
        units.append(value)
    return units


def _trim_topic(text: str) -> str:
    out = _clean_line(text)
    upper = _normalized_upper(out)
    for marker in _STOP_MARKERS:
        idx = upper.find(marker)
        if idx > 0:
            out = _clean_line(out[:idx])
            break
    return out


def _normalize_topic_text(value: str) -> str:
    value = _clean_line(value)
    value = re.sub(r"\s+([,.;:])", r"\1", value)
    return value


def _extract_weekly_topics(page_lines: List[List[str]]) -> List[str]:
    week_only_rx = re.compile(r"^(?:\d{1,2}|\d{1,2}\s+y\s+\d{1,2})$", re.I)
    week_inline_range_rx = re.compile(r"^\d{1,2}\s+y\s+\d{1,2}\s+(.+)$", re.I)
    week_inline_single_rx = re.compile(r"^\d{1,2}\s+(?!y\s+\d{1,2}$)(.+)$", re.I)
    content_page_markers = ("SEMANA", "CONTENIDO", "COMPONENTE")
    stop_markers = (
        "REVISION DE LA",
        "LEER LA",
        "FOROS",
        "CASO DE ESTUDIO",
        "INVESTIGACION",
        "RESPONDER",
        "PRÁCTICAS DE",
        "PRACTICAS DE",
        "TRABAJO AUTONOMO",
        "EVALUACION",
        "DESCRIPCION MICROCURRICULAR",
    )

    topics: List[str] = []
    seen = set()

    def _register_topic(value: str) -> None:
        candidate = _trim_topic(_normalize_topic_text(value))
        if len(candidate) < 10:
            return
        if len(candidate) > 260:
            return
        upper = _normalized_upper(candidate)
        if upper.startswith("REVISION DE LA UNIDAD"):
            return
        if upper.startswith("NOMBRE:"):
            return
        if "ESCENARIOS DE APRENDIZAJE" in upper:
            return
        if "DESCRIPCION MICROCURRICULAR" in upper:
            return
        if upper in {"DOCENTE", "TRABAJO AUTONOMO", "EVALUACION"}:
            return
        if candidate in seen:
            return
        seen.add(candidate)
        topics.append(candidate)

    for lines in page_lines:
        normalized_lines = [_normalized_upper(item) for item in lines]
        normalized_set = set(normalized_lines)
        week_markers_count = sum(1 for item in lines if week_only_rx.match(item))
        looks_like_content_page = all(marker in normalized_set for marker in content_page_markers) or (
            week_markers_count >= 2 and any("DOCENTE" in item for item in normalized_lines)
        )
        if not looks_like_content_page:
            continue

        start_index = 0
        for pos, value in enumerate(lines):
            if _normalized_upper(value) == "SEMANA":
                start_index = pos + 1
                break

        idx = start_index
        while idx < len(lines):
            line = lines[idx]
            if week_only_rx.match(line):
                parts: List[str] = []
                for probe_idx in range(idx + 1, min(idx + 25, len(lines))):
                    probe = lines[probe_idx]
                    probe_upper = _normalized_upper(probe)
                    if (
                        week_only_rx.match(probe)
                        or week_inline_range_rx.match(probe)
                        or week_inline_single_rx.match(probe)
                    ):
                        break
                    if any(marker in probe_upper for marker in stop_markers):
                        break
                    if probe_upper in {"SEMANA", "CONTENIDO", "DOCENTE", "EVALUACION"}:
                        continue
                    if _is_role_stop_line(probe):
                        continue
                    parts.append(probe)
                if parts:
                    _register_topic(" ".join(parts))
                idx += 1
                continue

            inline_match = week_inline_range_rx.match(line) or week_inline_single_rx.match(line)
            if inline_match:
                topic_value = inline_match.group(1)
                if idx + 1 < len(lines):
                    nxt = lines[idx + 1]
                    nxt_upper = _normalized_upper(nxt)
                    if (
                        not week_only_rx.match(nxt)
                        and not week_inline_range_rx.match(nxt)
                        and not week_inline_single_rx.match(nxt)
                        and not any(marker in nxt_upper for marker in stop_markers)
                        and len(topic_value.split()) <= 4
                    ):
                        topic_value = f"{topic_value} {nxt}"
                _register_topic(topic_value)

            idx += 1

    return topics


def _extract_year_tokens(text: str) -> List[str]:
    found = re.findall(r"\b20\d{2}(?:-20?\d{2})?\b", text)
    unique = []
    seen = set()
    for token in found:
        if token not in seen:
            seen.add(token)
            unique.append(token)
    return unique


def _suggest_next_value(value: str) -> str:
    span_rx = re.fullmatch(r"(20\d{2})-(20\d{2})", value)
    if span_rx:
        start = int(span_rx.group(1)) + 1
        end = int(span_rx.group(2)) + 1
        return f"{start}-{end}"

    year_month_rx = re.fullmatch(r"(20\d{2})-(\d{2})", value)
    if year_month_rx:
        year = int(year_month_rx.group(1)) + 1
        month = year_month_rx.group(2)
        return f"{year}-{month}"

    return ""


def _append_field(
    container: List[SuggestedField],
    seen: set,
    category: str,
    label: str,
    value: str,
    suggested: str = "",
) -> None:
    clean_value = _clean_line(value)
    if not clean_value:
        return
    key = (category, label, clean_value)
    if key in seen:
        return
    seen.add(key)
    container.append(
        SuggestedField(
            category=category,
            label=label,
            current_value=clean_value,
            suggested_value=suggested,
        )
    )


def analyze_pdf(path: Path) -> DocumentAnalysis:
    doc = fitz.open(str(path))
    try:
        all_lines: List[str] = []
        page_lines: List[List[str]] = []
        searchable_pages = 0

        for page in doc:
            raw_text = page.get_text("text")
            lines = [_clean_line(line) for line in raw_text.splitlines()]
            lines = [line for line in lines if line]
            page_lines.append(lines)
            all_lines.extend(lines)
            if len(_clean_line(raw_text)) > 20:
                searchable_pages += 1

        first_lines = page_lines[0] if page_lines else []
        last_lines = page_lines[-1] if page_lines else []
        full_text = "\n".join(all_lines)

        suggestions: List[SuggestedField] = []
        seen = set()

        for label, value in _extract_basic_fields(first_lines).items():
            _append_field(
                suggestions,
                seen,
                category="Datos institucionales",
                label=label,
                value=value,
            )

        for label, value in _extract_period_fields(first_lines).items():
            _append_field(
                suggestions,
                seen,
                category="Periodo",
                label=label,
                value=value,
                suggested=_suggest_next_value(value),
            )

        docente = _extract_name_after_role(last_lines, "Docente")
        coordinador = _extract_name_after_role(last_lines, "Coordinador")
        director = _extract_name_after_role(last_lines, "Director/a de Carrera")
        firma = _extract_signature_name(last_lines)

        if docente:
            _append_field(suggestions, seen, "Autoridades", "Docente", docente)
        if coordinador:
            _append_field(suggestions, seen, "Autoridades", "Coordinador", coordinador)
        if director:
            _append_field(suggestions, seen, "Autoridades", "Director/a de Carrera", director)
        if firma:
            _append_field(suggestions, seen, "Firma", "Firmado electronicamente por", firma)

        units = _extract_units(all_lines)
        for idx, unit in enumerate(units, start=1):
            _append_field(suggestions, seen, "Unidades", f"Unidad {idx}", unit)

        weekly_topics = _extract_weekly_topics(page_lines)
        for idx, topic in enumerate(weekly_topics[:18], start=1):
            _append_field(suggestions, seen, "Temas", f"Tema {idx}", topic)

        for token in _extract_year_tokens(full_text):
            _append_field(
                suggestions,
                seen,
                "Fechas globales",
                "Token de fecha",
                token,
                _suggest_next_value(token),
            )

        warnings: List[str] = []
        if searchable_pages == 0:
            warnings.append(
                "El PDF parece imagen/escaneado. Los reemplazos exactos pueden no funcionar."
            )
        if searchable_pages < len(doc):
            warnings.append(
                "Algunas paginas tienen poco texto extraible. Revisa el resultado final manualmente."
            )

        return DocumentAnalysis(
            pdf_path=path,
            page_count=len(doc),
            searchable_pages=searchable_pages,
            signed_source_detected=_detect_pdf_signature(path),
            suggested_fields=suggestions,
            unit_names=units,
            weekly_topics=weekly_topics,
            warnings=warnings,
        )
    finally:
        doc.close()
