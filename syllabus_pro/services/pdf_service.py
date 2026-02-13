import fitz  # type: ignore
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import re
import unicodedata
from ..core.models import AnalysisResult, EditableField, FieldCategory

class PDFService:
    def __init__(self):
        self._doc: Optional[fitz.Document] = None
        self._path: Optional[Path] = None

    def load_pdf(self, path: Path) -> AnalysisResult:
        if self._doc:
            self._doc.close()
        
        self._path = path
        self._doc = fitz.open(str(path))
        
        return self._analyze_document()

    def get_page_image(self, page_num: int, zoom: float = 1.0) -> bytes:
        """Renderiza una página como bytes de imagen PNG para la UI."""
        if not self._doc or page_num < 0 or page_num >= len(self._doc):
            return b""
        
        page = self._doc[page_num]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        return pix.tobytes("png")

    def save_pdf(self, output_path: Path, fields: List[EditableField]) -> None:
        """Genera el PDF actualizado aplicando los cambios."""
        if not self._doc:
            return

        # Trabajar sobre una copia en memoria o recargar para no dañar el estado actual
        # Aquí usaremos el documento abierto y guardaremos en nueva ruta
        
        # Estrategia simple: Reemplazo de texto usando redact_annot
        # Nota: Esto invalida firmas digitales, como ya se sabe.
        
        for page in self._doc:
            # Buscar coincidencias de los valores originales
            for field in fields:
                if not field.is_modified:
                    continue
                
                # Buscar el texto original en la página
                # Nota: fitz.Page.search_for es exacto. Si el texto original tiene saltos de línea extraños, puede fallar.
                # Una implementación robusta requeriría más lógica de coincidencia difusa.
                hits = page.search_for(field.original_value)
                
                for rect in hits:
                    # Añadir redacción (borrar texto original)
                    page.add_redact_annot(rect, fill=(1, 1, 1)) # Fondo blanco
                
                if hits:
                    page.apply_redactions()
                    # Insertar nuevo texto en la primera posición encontrada (o en todas)
                    # Usamos insert_text o insert_textbox
                    # Para simplificar, usamos el primer rect
                    target_rect = hits[0]
                    
                    # Intentar mantener fuente y tamaño es complejo sin OCR previo de estilos.
                    # Usaremos una fuente estándar por defecto por ahora.
                    page.insert_textbox(
                        target_rect, 
                        field.current_value, 
                        fontsize=11, # Estimado
                        fontname="helv",
                        color=(0, 0, 1) # Azul para resaltar cambios (opcional) o Negro (0,0,0)
                    )

        self._doc.save(str(output_path))

    def close(self):
        if self._doc:
            self._doc.close()
            self._doc = None

    def _analyze_document(self) -> AnalysisResult:
        if not self._doc:
            raise RuntimeError("No document loaded")

        fields: List[EditableField] = []
        full_text = ""
        
        # Extracción básica de texto
        for i, page in enumerate(self._doc):
            text = page.get_text()
            full_text += text + "\n"
            
            # Detectar campos en la primera página (Metadata común)
            if i == 0:
                fields.extend(self._extract_header_fields(text))
                fields.extend(self._extract_period_fields(text))

        # Detectar autoridades y firmas (usualmente al final)
        last_page_text = self._doc[-1].get_text()
        fields.extend(self._extract_authorities(last_page_text, len(self._doc) - 1))

        # Detectar firma digital
        is_signed = self._detect_signature()

        return AnalysisResult(
            file_path=self._path,
            page_count=len(self._doc),
            is_signed=is_signed,
            fields=fields,
            warnings=[] if is_signed else ["No se detectó firma digital en el original."]
        )

    def _detect_signature(self) -> bool:
        # Lógica simplificada de detección
        raw = self._path.read_bytes()
        return b"/Sig" in raw and b"/ByteRange" in raw

    def _extract_header_fields(self, text: str) -> List[EditableField]:
        fields = []
        # Patrones comunes
        patterns = {
            "FACULTAD": r"FACULTAD:\s*(.+)",
            "CARRERA": r"CARRERA:\s*(.+)",
            "ASIGNATURA": r"ASIGNATURA.*?:\s*(.+)",
            "CODIGO": r"CÓDIGO:\s*([\w-]+)",
        }
        
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
                    page_number=0
                ))
        return fields

    def _extract_period_fields(self, text: str) -> List[EditableField]:
        fields = []
        # Buscar patrones de periodo tipo "2025-2026"
        matches = re.finditer(r"\b(20\d{2})-(20\d{2})\b", text)
        seen = set()
        
        for m in matches:
            val = m.group(0)
            if val in seen:
                continue
            seen.add(val)
            
            # Sugerir siguiente periodo
            y1 = int(m.group(1))
            y2 = int(m.group(2))
            suggested = f"{y1+1}-{y2+1}"
            
            fields.append(EditableField(
                id=f"period_{val}",
                category=FieldCategory.PERIODO,
                label="Periodo Académico/Ejecución",
                original_value=val,
                current_value=val,
                suggested_value=suggested,
                page_number=0
            ))
        return fields

    def _extract_authorities(self, text: str, page_idx: int) -> List[EditableField]:
        fields = []
        # Busqueda simplificada de docentes/firmas
        # En una app real, esto sería más robusto con NLP o posición
        lines = text.split('\n')
        roles = ["Docente", "Director", "Coordinador", "Decano"]
        
        for i, line in enumerate(lines):
            for role in roles:
                if role.upper() in line.upper():
                    # Buscar nombre en líneas cercanas
                    if i + 1 < len(lines):
                        name_candidate = lines[i+1].strip()
                        if len(name_candidate) > 5 and not any(r.upper() in name_candidate.upper() for r in roles):
                            fields.append(EditableField(
                                id=f"auth_{role}_{i}",
                                category=FieldCategory.AUTORIDAD,
                                label=role,
                                original_value=name_candidate,
                                current_value=name_candidate,
                                page_number=page_idx
                            ))
        return fields
