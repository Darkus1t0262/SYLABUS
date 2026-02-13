import fitz  # type: ignore
import pdfplumber
from pathlib import Path
from typing import List, Optional, Tuple, Any
import re
import os
import shutil
from statistics import median
from ..core.models import AnalysisResult, EditableField, FieldCategory

class PDFService:
    def __init__(self):
        self._doc: Optional[fitz.Document] = None
        self._path: Optional[Path] = None

    def load_pdf(self, path: Path) -> AnalysisResult:
        if self._doc:
            self._doc.close()
        
        self._path = path
        # Abrir documento en memoria para evitar bloqueo del archivo en disco
        # Esto permite que otros procesos (o nosotros mismos al guardar) sobrescriban el archivo original
        try:
            with open(path, "rb") as f:
                data = f.read()
            self._doc = fitz.open(stream=data, filetype="pdf")
        except Exception:
            # Fallback a apertura normal si falla carga en memoria (ej. archivo muy grande)
            self._doc = fitz.open(str(path))
        
        return self._analyze_document()

    def get_page_image(self, page_num: int, zoom: float = 1.0) -> bytes:
        if not self._doc or page_num < 0 or page_num >= len(self._doc):
            return b""
        
        page = self._doc[page_num]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        return pix.tobytes("png")

    def get_page_size(self, page_num: int) -> Tuple[float, float]:
        if not self._doc or page_num < 0 or page_num >= len(self._doc):
            return (1.0, 1.0)
        page = self._doc[page_num]
        rect = page.rect
        return (float(rect.width), float(rect.height))

    def save_pdf(self, output_path: Path, fields: List[EditableField]) -> None:
        if not self._doc:
            raise RuntimeError("No hay documento cargado para guardar.")

        # Crear nombre de archivo temporal único
        import time
        temp_filename = f"{output_path.stem}_tmp_{int(time.time())}.pdf"
        temp_path = output_path.parent / temp_filename
        
        # Copia de trabajo en memoria
        doc_copy = fitz.open()
        doc_copy.insert_pdf(self._doc)

        try:
            for page_num, page in enumerate(doc_copy):
                page_fields = [f for f in fields if f.page_number == page_num]
                
                for field in page_fields:
                    if not field.is_modified:
                        continue
                    target_rect, source_rects = self._resolve_target_rect(page, field)
                    if not target_rect:
                        continue

                    style = self._extract_text_style(page, target_rect)
                    measure_font = self._measurement_font_name(style["source_font"])
                    insert_font, insert_font_file = self._resolve_insert_font(page, style["source_font"])
                    base_size = self._fit_font_size(
                        field.original_value,
                        target_rect,
                        measure_font,
                        style["fontsize"]
                    )
                    max_font_size = min(style["fontsize"], base_size)
                    font_size = self._fit_font_size(
                        field.current_value,
                        target_rect,
                        measure_font,
                        max_font_size
                    )
                    align = self._choose_alignment()

                    line_rects = self._extract_text_line_rects(page, target_rect)
                    if line_rects:
                        slot_size, slot_lines = self._fit_text_to_line_slots(
                            field.current_value,
                            line_rects,
                            measure_font,
                            max_font_size
                        )
                        if slot_size and slot_lines is not None:
                            self._clear_rects_with_redaction(page, line_rects, preserve_borders=False)
                            for idx, line_text in enumerate(slot_lines):
                                line_text = line_text.strip()
                                if not line_text:
                                    continue
                                line_rect = line_rects[idx]
                                text_x = line_rect.x0 + 0.25
                                # Baseline estable para evitar fallos de textbox en líneas muy ajustadas.
                                text_y = line_rect.y1 - max(0.4, slot_size * 0.12)
                                page.insert_text(
                                    fitz.Point(text_x, text_y),
                                    line_text,
                                    fontsize=max(6.0, slot_size - 0.1),
                                    fontname=insert_font,
                                    fontfile=insert_font_file,
                                    color=style["color"],
                                    render_mode=0,
                                    overlay=True
                                )
                            continue

                    is_cell_rect = bool(field.rect and len(field.rect) == 4)
                    self._clear_rects_with_redaction(page, source_rects, preserve_borders=is_cell_rect)

                    write_rect = fitz.Rect(
                        target_rect.x0 + 1.2,
                        target_rect.y0 + 0.8,
                        target_rect.x1 - 1.2,
                        target_rect.y1 - 0.8
                    )
                    if write_rect.width <= 2 or write_rect.height <= 2:
                        write_rect = target_rect

                    page.insert_textbox(
                        write_rect,
                        field.current_value,
                        fontsize=font_size,
                        fontname=insert_font,
                        fontfile=insert_font_file,
                        color=style["color"],
                        align=align
                    )

            # 1. Guardar siempre a un archivo NUEVO temporal primero
            # Esto evita cualquier conflicto de bloqueo con el archivo de destino
            doc_copy.save(str(temp_path), garbage=4, deflate=True)
            
        except Exception as e:
            # Si falla el guardado, limpiar temporal
            if temp_path.exists():
                os.remove(str(temp_path))
            raise e
        finally:
            doc_copy.close()

        # 2. Reemplazar el archivo destino con el temporal
        # Usamos os.replace (atómico en POSIX, renombra en Windows)
        # Si el destino existe, intentamos eliminarlo primero si replace falla
        try:
            if output_path.exists():
                # Forzar liberación de atributos de solo lectura si existen
                try:
                    os.chmod(str(output_path), 0o777)
                except:
                    pass
                
                # Intentar reemplazo directo
                try:
                    os.replace(str(temp_path), str(output_path))
                except OSError:
                    # Si falla (ej. bloqueado por antivirus o indexador), esperar y reintentar
                    time.sleep(0.1)
                    os.remove(str(output_path))
                    shutil.move(str(temp_path), str(output_path))
            else:
                shutil.move(str(temp_path), str(output_path))
                
        except Exception as e:
            # Si todo falla, no dejar basura
            if temp_path.exists():
                # No borrarlo, dejarlo para recuperación manual si es crítico
                pass 
            raise RuntimeError(f"Error al sobrescribir archivo final: {str(e)}. \nIntente guardar con otro nombre.")

    def close(self):
        if self._doc:
            self._doc.close()
            self._doc = None

    def _analyze_document(self) -> AnalysisResult:
        if not self._doc or not self._path:
            raise RuntimeError("No document loaded")

        fields: List[EditableField] = []
        
        # Usar pdfplumber para extracción estructurada (tablas)
        with pdfplumber.open(self._path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                tables = page.extract_tables()
                
                # Extracciones por página
                if i == 0:
                    fields.extend(self._extract_header_fields(text, i))
                    fields.extend(self._extract_period_fields(text, i))
                
                # Buscar tablas específicas por contenido
                self._extract_learning_results(page, i, fields)
                self._extract_bibliography(page, i, fields)
                self._extract_hours_table(page, i, fields)
                self._extract_authorities_advanced(page, i, fields)

        # Detectar firma digital (simple)
        is_signed = self._detect_signature()

        self._ensure_unique_field_ids(fields)
        self._infer_missing_rects(fields)

        return AnalysisResult(
            file_path=self._path,
            page_count=len(self._doc),
            is_signed=is_signed,
            fields=fields,
            warnings=[]
        )

    def _ensure_unique_field_ids(self, fields: List[EditableField]) -> None:
        seen: dict[str, int] = {}
        for field in fields:
            base = field.id
            count = seen.get(base, 0) + 1
            seen[base] = count
            if count > 1:
                field.id = f"{base}__{count}"

    def _infer_missing_rects(self, fields: List[EditableField]) -> None:
        if not self._doc:
            return

        for field in fields:
            if field.rect:
                continue
            if field.page_number < 0 or field.page_number >= len(self._doc):
                continue
            original = (field.original_value or "").strip()
            if not original:
                continue

            try:
                page = self._doc[field.page_number]
                hits = self._search_hits(page, original)
                selected_hits = self._select_hits_for_text(hits, original)
                if selected_hits:
                    union_rect = self._union_rects(selected_hits)
                    field.rect = [union_rect.x0, union_rect.y0, union_rect.x1, union_rect.y1]
            except Exception:
                # Si no se puede inferir coordenada, mantenemos fallback por texto al guardar.
                continue

    def _resolve_target_rect(
        self, page: fitz.Page, field: EditableField
    ) -> Tuple[Optional[fitz.Rect], List[fitz.Rect]]:
        if field.rect and len(field.rect) == 4:
            rect = fitz.Rect(field.rect)
            return rect, [rect]

        hits = self._search_hits(page, field.original_value)
        selected_hits = self._select_hits_for_text(hits, field.original_value)
        if not selected_hits:
            return None, []

        return self._union_rects(selected_hits), selected_hits

    def _build_clear_rect(self, rect: fitz.Rect, preserve_borders: bool) -> fitz.Rect:
        if preserve_borders:
            # Mantener líneas de tabla: limpiar interior de celda sin tocar bordes.
            # Usar margen mínimo para cubrir texto previo y preservar la línea del cuadro.
            inset_x = min(0.35, max(0.12, rect.width * 0.003))
            inset_y = min(0.30, max(0.10, rect.height * 0.003))
            x0 = rect.x0 + inset_x
            y0 = rect.y0 + inset_y
            x1 = rect.x1 - inset_x
            y1 = rect.y1 - inset_y
        else:
            # Para hits de texto sueltos, ampliar ligeramente para cubrir tinta completa.
            x0 = rect.x0 - 0.4
            y0 = rect.y0 - 0.3
            x1 = rect.x1 + 0.4
            y1 = rect.y1 + 0.3

        if x1 <= x0 or y1 <= y0:
            return rect
        return fitz.Rect(x0, y0, x1, y1)

    def _clear_rects_with_redaction(
        self, page: fitz.Page, rects: List[fitz.Rect], preserve_borders: bool
    ) -> None:
        if not rects:
            return
        for rect in rects:
            clear_rect = self._build_clear_rect(rect, preserve_borders=preserve_borders)
            page.add_redact_annot(clear_rect, fill=(1, 1, 1))
        page.apply_redactions(
            images=fitz.PDF_REDACT_IMAGE_NONE,
            graphics=fitz.PDF_REDACT_LINE_ART_NONE,
            text=fitz.PDF_REDACT_TEXT_REMOVE
        )

    def _extract_text_line_rects(self, page: fitz.Page, rect: fitz.Rect) -> List[fitz.Rect]:
        try:
            data = page.get_text("dict", clip=rect)
        except Exception:
            return []

        raw_lines: List[fitz.Rect] = []
        for block in data.get("blocks", []):
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                has_text = any((span.get("text") or "").strip() for span in spans)
                if not has_text:
                    continue
                bbox = line.get("bbox")
                if not bbox:
                    continue
                line_rect = fitz.Rect(bbox)
                if line_rect.width <= 1 or line_rect.height <= 1:
                    continue
                raw_lines.append(line_rect)

        if not raw_lines:
            return []

        raw_lines.sort(key=lambda r: (r.y0, r.x0))
        merged_rows: List[List[fitz.Rect]] = []
        for line_rect in raw_lines:
            y_mid = (line_rect.y0 + line_rect.y1) / 2
            placed = False
            for row in merged_rows:
                ref = row[0]
                ref_mid = (ref.y0 + ref.y1) / 2
                if abs(y_mid - ref_mid) <= 1.4:
                    row.append(line_rect)
                    placed = True
                    break
            if not placed:
                merged_rows.append([line_rect])

        line_rects: List[fitz.Rect] = []
        for row in merged_rows:
            x0 = min(r.x0 for r in row)
            y0 = min(r.y0 for r in row)
            x1 = max(r.x1 for r in row)
            y1 = max(r.y1 for r in row)
            merged = fitz.Rect(x0, y0, x1, y1)
            # Usar el ancho de la celda para evitar que el wrap dependa de segmentos de texto parciales.
            merged = fitz.Rect(rect.x0 + 0.4, merged.y0, rect.x1 - 0.4, merged.y1)
            line_rects.append(merged)

        line_rects.sort(key=lambda r: (r.y0, r.x0))
        return line_rects

    def _search_hits(self, page: fitz.Page, text: str) -> List[fitz.Rect]:
        safe_text = (text or "").strip()
        if not safe_text:
            return []
        try:
            hits = page.search_for(safe_text)
        except Exception:
            return []
        return sorted(hits, key=lambda r: (r.y0, r.x0))

    def _select_hits_for_text(self, hits: List[fitz.Rect], text: str) -> List[fitz.Rect]:
        if not hits:
            return []
        if len(hits) == 1:
            return hits

        # Para textos largos tomamos el bloque contiguo más cercano al primer hit.
        if len((text or "").strip()) < 30:
            return [hits[0]]

        selected = [hits[0]]
        for rect in hits[1:]:
            prev = selected[-1]
            same_block = (rect.y0 - prev.y1) <= 18 and abs(rect.x0 - selected[0].x0) <= 180
            if not same_block:
                break
            selected.append(rect)
        return selected

    def _union_rects(self, rects: List[fitz.Rect]) -> fitz.Rect:
        x0 = min(r.x0 for r in rects)
        y0 = min(r.y0 for r in rects)
        x1 = max(r.x1 for r in rects)
        y1 = max(r.y1 for r in rects)
        return fitz.Rect(x0, y0, x1, y1)

    def _extract_text_style(self, page: fitz.Page, rect: fitz.Rect) -> dict:
        style = {
            "fontsize": 9.5,
            "color": (0.0, 0.0, 0.0),
            "source_font": "",
        }
        try:
            data = page.get_text("dict", clip=rect)
        except Exception:
            return style

        spans = []
        for block in data.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    txt = (span.get("text") or "").strip()
                    if txt:
                        spans.append(span)

        if not spans:
            return style

        # Usar mediana para evitar outliers (ej. títulos o spans sueltos grandes).
        span_sizes = [
            float(s.get("size") or style["fontsize"])
            for s in spans
            if float(s.get("size") or 0) > 0
        ]
        if span_sizes:
            raw_size = median(span_sizes)
            style["fontsize"] = max(6.0, min(11.0, float(raw_size)))

        main_span = max(spans, key=lambda s: len((s.get("text") or "").strip()))
        style["source_font"] = str(main_span.get("font") or "")

        color = main_span.get("color")
        if isinstance(color, int):
            style["color"] = self._int_to_rgb(color)

        return style

    def _measurement_font_name(self, source_font: str) -> str:
        name = (source_font or "").lower()
        if "times" in name:
            return "times-roman"
        if "courier" in name:
            return "cour"
        # Calibri y Arial miden parecido con Helvetica para ajuste aproximado.
        return "helv"

    def _resolve_insert_font(self, page: fitz.Page, source_font: str) -> Tuple[str, Optional[str]]:
        family = self._normalized_font_family(source_font)
        if not family:
            family = self._preferred_family_from_page(page)
        if not family:
            return "helv", None

        font_file = self._find_system_font_file(source_font, family)
        if not font_file:
            return "helv", None

        alias = f"APPFONT_{family.upper()}"
        return alias, font_file

    def _preferred_family_from_page(self, page: fitz.Page) -> str:
        try:
            fonts = page.get_fonts(full=True)
        except Exception:
            return ""

        found_calibri = False
        found_arial = False
        for font_info in fonts:
            base_name = str(font_info[3] or "").lower()
            if "calibri" in base_name:
                found_calibri = True
            if "arial" in base_name:
                found_arial = True

        if found_calibri:
            return "calibri"
        if found_arial:
            return "arial"
        return ""

    def _normalized_font_family(self, source_font: str) -> str:
        name = (source_font or "").lower()
        if "calibri" in name:
            return "calibri"
        if "arial" in name:
            return "arial"
        if "times" in name:
            return "times"
        if "courier" in name:
            return "courier"
        return ""

    def _find_system_font_file(self, source_font: str, family: str) -> Optional[str]:
        windir = os.environ.get("WINDIR", "C:\\Windows")
        fonts_dir = Path(windir) / "Fonts"
        if not fonts_dir.exists():
            return None

        src = (source_font or "").lower()
        is_bold = "bold" in src
        is_italic = "italic" in src or "oblique" in src

        if family == "calibri":
            candidates = []
            if is_bold and is_italic:
                candidates.append("calibriz.ttf")
            if is_bold:
                candidates.append("calibrib.ttf")
            if is_italic:
                candidates.append("calibrii.ttf")
            candidates.append("calibri.ttf")
        elif family == "arial":
            candidates = []
            if is_bold and is_italic:
                candidates.append("arialbi.ttf")
            if is_bold:
                candidates.append("arialbd.ttf")
            if is_italic:
                candidates.append("ariali.ttf")
            candidates.append("arial.ttf")
        elif family == "times":
            candidates = ["times.ttf", "timesbd.ttf"]
        elif family == "courier":
            candidates = ["cour.ttf", "courbd.ttf"]
        else:
            candidates = []

        for filename in candidates:
            path = fonts_dir / filename
            if path.exists():
                return str(path)
        return None

    def _int_to_rgb(self, color_int: int) -> Tuple[float, float, float]:
        r = (color_int >> 16) & 255
        g = (color_int >> 8) & 255
        b = color_int & 255
        return (r / 255.0, g / 255.0, b / 255.0)

    def _choose_alignment(self) -> int:
        # La justificación automática distorsiona la estética cuando cambia la longitud.
        # Mantener alineación a la izquierda produce resultados más estables.
        return getattr(fitz, "TEXT_ALIGN_LEFT", 0)

    def _fit_text_to_line_slots(
        self,
        text: str,
        line_rects: List[fitz.Rect],
        fontname: str,
        preferred_size: float
    ) -> Tuple[Optional[float], Optional[List[str]]]:
        if not line_rects:
            return None, None

        widths = [max(8.0, r.width - 0.6) for r in line_rects]
        size = max(6.0, min(13.0, preferred_size))
        while size >= 6.0:
            wrapped = self._wrap_text_to_widths(
                text=text,
                widths=widths,
                fontname=fontname,
                fontsize=size,
            )
            if wrapped is not None:
                return round(size, 1), wrapped
            size -= 0.25
        return None, None

    def _wrap_text_to_widths(
        self,
        text: str,
        widths: List[float],
        fontname: str,
        fontsize: float,
    ) -> Optional[List[str]]:
        max_lines = len(widths)
        if max_lines == 0:
            return None

        paragraphs = (text or "").replace("\r", "").split("\n")
        lines: List[str] = []

        for paragraph in paragraphs:
            words = paragraph.split()
            if not words:
                if len(lines) >= max_lines:
                    return None
                lines.append("")
            else:
                current = ""
                idx = 0
                while idx < len(words):
                    if len(lines) >= max_lines:
                        return None

                    word = words[idx]
                    width_limit = widths[len(lines)]
                    candidate = word if not current else f"{current} {word}"
                    if self._text_width(candidate, fontname, fontsize) <= width_limit:
                        current = candidate
                        idx += 1
                        continue

                    if current:
                        lines.append(current)
                        current = ""
                        continue

                    parts = self._split_word(word, width_limit, fontname, fontsize)
                    if not parts:
                        return None
                    lines.append(parts[0])
                    if len(parts) > 1:
                        words[idx] = "".join(parts[1:])
                    else:
                        idx += 1

                if current:
                    if len(lines) >= max_lines:
                        return None
                    lines.append(current)

        if len(lines) > max_lines:
            return None
        return lines

    def _text_width(self, text: str, fontname: str, fontsize: float) -> float:
        try:
            return fitz.get_text_length(text, fontname=fontname, fontsize=fontsize)
        except Exception:
            return fitz.get_text_length(text, fontname="helv", fontsize=fontsize)

    def _fit_font_size(
        self,
        text: str,
        rect: fitz.Rect,
        fontname: str,
        preferred_size: float
    ) -> float:
        start_size = max(6.0, min(13.0, preferred_size))
        size = start_size
        while size >= 6.0:
            if self._text_fits_rect(text, rect, fontname, size):
                return round(size, 1)
            size -= 0.5
        return 6.0

    def _text_fits_rect(
        self,
        text: str,
        rect: fitz.Rect,
        fontname: str,
        fontsize: float
    ) -> bool:
        max_width = max(8.0, rect.width - 4.0)
        max_height = max(8.0, rect.height - 2.0)
        line_height = fontsize * 1.2
        line_count = 0

        paragraphs = (text or "").splitlines()
        if not paragraphs:
            paragraphs = [text or ""]

        for paragraph in paragraphs:
            words = paragraph.split()
            if not words:
                line_count += 1
                continue

            line = ""
            for word in words:
                candidate = f"{line} {word}".strip()
                if fitz.get_text_length(candidate, fontname=fontname, fontsize=fontsize) <= max_width:
                    line = candidate
                    continue

                if line:
                    line_count += 1
                    line = word
                else:
                    parts = self._split_word(word, max_width, fontname, fontsize)
                    line_count += max(0, len(parts) - 1)
                    line = parts[-1] if parts else ""

                if fitz.get_text_length(line, fontname=fontname, fontsize=fontsize) > max_width:
                    parts = self._split_word(line, max_width, fontname, fontsize)
                    line_count += max(0, len(parts) - 1)
                    line = parts[-1] if parts else ""

            if line or not words:
                line_count += 1

        required_height = line_count * line_height
        return required_height <= max_height

    def _split_word(
        self,
        word: str,
        max_width: float,
        fontname: str,
        fontsize: float
    ) -> List[str]:
        if not word:
            return [""]

        pieces: List[str] = []
        current = ""
        for ch in word:
            candidate = f"{current}{ch}"
            if fitz.get_text_length(candidate, fontname=fontname, fontsize=fontsize) <= max_width:
                current = candidate
            else:
                if current:
                    pieces.append(current)
                current = ch
        if current:
            pieces.append(current)
        return pieces or [word]

    def _detect_signature(self) -> bool:
        if not self._path: return False
        raw = self._path.read_bytes()
        return b"/Sig" in raw and b"/ByteRange" in raw

    def _extract_header_fields(self, text: str, page_num: int) -> List[EditableField]:
        fields = []
        patterns = {
            "FACULTAD": r"FACULTAD:\s*(.+)",
            "CARRERA": r"CARRERA:\s*(.+)",
            "ASIGNATURA": r"ASIGNATURA.*?:\s*(.+)",
            "CODIGO": r"CÓDIGO:\s*([\w-]+)",
        }
        
        # Nota: Aquí usamos regex sobre texto plano, por lo que no tenemos rect exacto fácil.
        # Para mejorar esto en el futuro, buscaríamos la palabra clave con pdfplumber.extract_words()
        # y tomaríamos el texto a su derecha.
        
        for label, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                val = match.group(1).strip()
                fields.append(EditableField(
                    id=f"header_{label.lower()}",
                    category=FieldCategory.INSTITUCIONAL,
                    label=label,
                    original_value=val,
                    current_value=val,
                    page_number=page_num,
                    # Sin rect por ahora para estos básicos, usará fallback search_for
                ))
        return fields

    def _extract_period_fields(self, text: str, page_num: int) -> List[EditableField]:
        fields = []
        matches = re.finditer(r"\b(20\d{2})-(20\d{2})\b", text)
        seen = set()
        
        for m in matches:
            val = m.group(0)
            if val in seen: continue
            seen.add(val)
            
            y1 = int(m.group(1))
            y2 = int(m.group(2))
            suggested = f"{y1+1}-{y2+1}"
            
            fields.append(EditableField(
                id=f"period_{val}_{page_num}",
                category=FieldCategory.PERIODO,
                label="Periodo",
                original_value=val,
                current_value=val,
                suggested_value=suggested,
                page_number=page_num
            ))
        return fields

    def _extract_learning_results(self, page: Any, page_num: int, fields: List[EditableField]):
        # Buscar tabla de resultados de aprendizaje
        # Heurística: Buscar texto "Resultados de Aprendizaje" en la página
        text = page.extract_text() or ""
        if "RESULTADOS DE APRENDIZAJE" not in text.upper():
            return

        # Iterar tablas para encontrar la correcta
        tables = page.find_tables()
        for table_idx, table in enumerate(tables):
            # Verificar si la tabla tiene cabecera compatible
            rows = table.extract()
            if not rows: continue
            
            # Buscar celda que contenga "Resultados de Aprendizaje"
            header_found = False
            for row in rows[:3]: # Buscar en primeras filas
                if any("RESULTADOS DE APRENDIZAJE" in (cell or "").upper() for cell in row):
                    header_found = True
                    break
            
            if header_found:
                # Extraer celdas de contenido
                # Asumimos que la tabla tiene filas de contenido debajo
                # Extraemos celdas no vacías como campos editables
                for i, row in enumerate(rows):
                    if i < 1: continue # Skip header probable
                    for j, cell in enumerate(row):
                        if cell and len(cell.strip()) > 10: # Texto significativo
                             # Obtener coordenadas de la celda
                             # pdfplumber table.cells[i][j] da el rect
                             # table.rows[i].cells[j]
                             cell_obj = table.rows[i].cells[j]
                             if not cell_obj: continue
                             
                             # pdfplumber rect: (x0, top, x1, bottom)
                             # fitz rect: (x0, top, x1, bottom) - Son compatibles en sistema coords estándar PDF (salvo origen Y a veces)
                             # pdfplumber usa origen top-left. Fitz usa top-left. Compatible.
                            
                             fields.append(EditableField(
                                id=f"result_learn_{page_num}_{table_idx}_{i}_{j}",
                                category=FieldCategory.RESULTADO,
                                label=f"Resultado {i}-{j}",
                                original_value=cell.strip(),
                                current_value=cell.strip(),
                                page_number=page_num,
                                rect=list(cell_obj)
                            ))

    def _extract_bibliography(self, page: Any, page_num: int, fields: List[EditableField]):
        text = page.extract_text() or ""
        if "BIBLIOGRAFÍA" not in text.upper() and "BIBLIOGRAFIA" not in text.upper():
            return

        tables = page.find_tables()
        for table in tables:
            rows = table.extract()
            if not rows: continue
            
            # Buscar cabecera "TÍTULO/AUTOR/AÑO" o similar
            is_biblio = False
            for row in rows[:3]:
                txt_row = "".join([(c or "") for c in row]).upper()
                if "TÍTULO" in txt_row or "AUTOR" in txt_row or "EDITORIAL" in txt_row:
                    is_biblio = True
                    break
            
            if is_biblio:
                for i, row in enumerate(rows):
                    # Filtrar filas de cabecera
                    if "TÍTULO" in str(row).upper(): continue
                    
                    for j, cell in enumerate(row):
                        if cell and len(cell.strip()) > 5:
                            cell_obj = table.rows[i].cells[j]
                            fields.append(EditableField(
                                id=f"biblio_{page_num}_{i}_{j}",
                                category=FieldCategory.BIBLIOGRAFIA,
                                label=f"Ref. Bibliográfica",
                                original_value=cell.strip(),
                                current_value=cell.strip(),
                                page_number=page_num,
                                rect=list(cell_obj)
                            ))

    def _extract_hours_table(self, page: Any, page_num: int, fields: List[EditableField]):
        # Tabla de horas: "ORGANIZACIÓN DEL APRENDIZAJE"
        text = page.extract_text() or ""
        if "ORGANIZACIÓN DEL APRENDIZAJE" not in text.upper():
            return

        tables = page.find_tables()
        for table in tables:
            rows = table.extract()
            if not rows: continue
            
            # Buscar números de horas (suelen ser celdas pequeñas con números)
            # Y estar en la fila inferior de la tabla
            
            # Estrategia: Buscar celdas numéricas en la última fila
            last_row = rows[-1]
            last_row_objs = table.rows[-1].cells
            
            if not last_row: continue

            for j, cell in enumerate(last_row):
                if cell and cell.strip().isdigit():
                    # Es probable una hora
                    val = cell.strip()
                    cell_obj = last_row_objs[j]
                    
                    fields.append(EditableField(
                        id=f"hours_{page_num}_{j}",
                        category=FieldCategory.HORAS,
                        label=f"Horas (Col {j+1})",
                        original_value=val,
                        current_value=val,
                        page_number=page_num,
                        rect=list(cell_obj)
                    ))

    def _extract_authorities_advanced(self, page: Any, page_num: int, fields: List[EditableField]):
        # Buscar palabras clave y tomar el texto DEBAJO o AL LADO
        words = page.extract_words()
        roles = ["DOCENTE", "DIRECTOR", "COORDINADOR", "DECANO"]
        
        # Agrupar palabras en líneas
        # Simplificación: iterar palabras y buscar roles
        for i, w in enumerate(words):
            text = w['text'].upper()
            if any(r in text for r in roles):
                # Buscar texto candidato cerca (usualmente debajo)
                # Coordenadas palabra clave: w['x0'], w['top'], w['x1'], w['bottom']
                role_bottom = w['bottom']
                role_x0 = w['x0']
                
                # Buscar palabras que estén debajo (dentro de un rango Y) y alineadas X
                candidates = []
                for w2 in words:
                    if w2['top'] > role_bottom and w2['top'] < role_bottom + 50: # 50px abajo max
                        if abs(w2['x0'] - role_x0) < 100: # Alineado o cerca horizontalmente
                             candidates.append(w2)
                
                if candidates:
                    # Unir candidatos para formar nombre
                    # Ordenar por top y luego x0
                    candidates.sort(key=lambda x: (x['top'], x['x0']))
                    full_name = " ".join([c['text'] for c in candidates])
                    
                    # Calcular bounding box total
                    x0 = min(c['x0'] for c in candidates)
                    top = min(c['top'] for c in candidates)
                    x1 = max(c['x1'] for c in candidates)
                    bottom = max(c['bottom'] for c in candidates)
                    
                    # Filtrar falsos positivos (ej. etiquetas vacías)
                    if len(full_name) > 3:
                        fields.append(EditableField(
                            id=f"auth_adv_{page_num}_{i}",
                            category=FieldCategory.AUTORIDAD,
                            label=text.title(),
                            original_value=full_name,
                            current_value=full_name,
                            page_number=page_num,
                            rect=[x0, top, x1, bottom]
                        ))
