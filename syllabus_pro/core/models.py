from enum import Enum
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

class FieldCategory(str, Enum):
    INSTITUCIONAL = "Datos Institucionales"
    PERIODO = "Periodo"
    AUTORIDAD = "Autoridades"
    TEMA = "Temas"
    UNIDAD = "Unidades"
    FECHA = "Fechas Globales"
    RESULTADO = "Resultados Aprendizaje"
    BIBLIOGRAFIA = "Bibliografía"
    HORAS = "Horas"
    OTRO = "Otro"

class EditableField(BaseModel):
    id: str
    category: FieldCategory
    label: str
    original_value: str
    current_value: str
    suggested_value: Optional[str] = None
    page_number: int = 1
    rect: Optional[List[float]] = None  # [x0, y0, x1, y1] para resaltar en UI

    @property
    def is_modified(self) -> bool:
        return self.current_value != self.original_value

class AnalysisResult(BaseModel):
    file_path: Path
    page_count: int
    is_signed: bool
    fields: List[EditableField] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

class AppState(BaseModel):
    current_file: Optional[Path] = None
    analysis: Optional[AnalysisResult] = None
    zoom_level: float = 1.0
