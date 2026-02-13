import fitz  # type: ignore
import pdfplumber
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
import re
import os
import shutil
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

    def save_pdf(self, output_path: Path, fields: List[EditableField]) -> None:
        if not self._doc:
            return

        # Trabajar sobre una copia en memoria para no dañar el documento actual si falla
        # O simplemente aplicar cambios. Como fitz modifica en memoria, 
        # si queremos seguir editando, debemos tener cuidado.
        # Para simplificar: aplicamos cambios al doc actual.
        
        for page_num, page in enumerate(self._doc):
            page_fields = [f for f in fields if f.page_number == page_num]
            
            for field in page_fields:
                if not field.is_modified:
                    continue

                # Estrategia 1: Usar coordenadas exactas si existen
                if field.rect:
                    # fitz rect es [x0, y0, x1, y1]
                    rect = fitz.Rect(field.rect)
                    
                    # 1. Redactar (borrar) área
                    page.add_redact_annot(rect, fill=(1, 1, 1))
                    page.apply_redactions()
                    
                    # 2. Insertar nuevo texto
                    page.insert_textbox(
                        rect, 
                        field.current_value,
                        fontsize=9, 
                        fontname="helv",
                        color=(0, 0, 0)
                    )
                else:
                    # Estrategia 2 (Fallback): Buscar texto
                    hits = page.search_for(field.original_value)
                    if hits:
                        for rect in hits:
                            page.add_redact_annot(rect, fill=(1, 1, 1))
                        page.apply_redactions()
                        page.insert_textbox(
                            hits[0], 
                            field.current_value, 
                            fontsize=10, 
                            fontname="helv",
                            color=(0, 0, 0)
                        )

        # Manejar guardado sobre el mismo archivo (Windows file lock)
        is_overwrite = False
        if self._path:
            try:
                is_overwrite = output_path.resolve() == self._path.resolve()
            except OSError:
                pass # Puede fallar si paths son extraños

        if is_overwrite:
            # Guardar en temporal
            temp_path = output_path.with_suffix(".tmp.pdf")
            try:
                self._doc.save(str(temp_path), garbage=4, deflate=True)
                
                # Cerrar documento para liberar lock
                self._doc.close()
                self._doc = None
                
                # Reemplazar archivo original
                if output_path.exists():
                    os.remove(str(output_path))
                shutil.move(str(temp_path), str(output_path))
                
                # Reabrir documento
                self.load_pdf(output_path)
            except Exception as e:
                # Intentar limpiar
                if temp_path.exists():
                    os.remove(str(temp_path))
                raise e
        else:
            # Guardar normal
            self._doc.save(str(output_path), garbage=4, deflate=True)

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

        return AnalysisResult(
            file_path=self._path,
            page_count=len(self._doc),
            is_signed=is_signed,
            fields=fields,
            warnings=[]
        )

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
        for table in tables:
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
                                id=f"result_learn_{page_num}_{i}_{j}",
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
