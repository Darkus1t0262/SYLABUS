from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QLabel, QSizePolicy
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QPen, QFont
from PySide6.QtCore import Qt, Signal
from typing import List, Optional
from ...core.models import EditableField

class PDFPageLabel(QLabel):
    def __init__(self, page_num: int, parent=None):
        super().__init__(parent)
        self.page_num = page_num
        self.original_pixmap: Optional[QPixmap] = None
        self.fields: List[EditableField] = []
        self.zoom = 1.0

    def set_image(self, image_bytes: bytes):
        image = QImage.fromData(image_bytes)
        self.original_pixmap = QPixmap.fromImage(image)
        self.refresh_view()

    def update_fields(self, fields: List[EditableField]):
        self.fields = [f for f in fields if f.page_number == self.page_num]
        self.refresh_view()

    def refresh_view(self):
        if not self.original_pixmap:
            return

        # Dibujar overlays sobre la copia del pixmap
        display_pixmap = self.original_pixmap.copy()
        painter = QPainter(display_pixmap)
        
        # Configurar fuente para overlays (simple estimación)
        font = QFont("Arial", 10)
        painter.setFont(font)

        for field in self.fields:
            if field.is_modified and field.rect: # Solo si tenemos coordenadas
                # TODO: Mapear coordenadas PDF a coordenadas Imagen
                # Por ahora, simulamos un resaltado simple si no hay rects reales
                pass
            
            # Nota: Sin coordenadas precisas del PDF (que fitz da), no podemos dibujar encima exacto.
            # En una implementación completa, PDFService debe devolver 'rect' para cada campo.
            # Aquí solo mostramos la imagen base.
        
        painter.end()
        self.setPixmap(display_pixmap)
        self.adjustSize()

class PDFViewer(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.setWidget(self.container)
        self.pages: List[PDFPageLabel] = []

    def clear(self):
        for i in reversed(range(self.layout.count())): 
            self.layout.itemAt(i).widget().setParent(None)
        self.pages = []

    def add_page(self, image_bytes: bytes, page_num: int):
        page_label = PDFPageLabel(page_num)
        page_label.set_image(image_bytes)
        self.layout.addWidget(page_label)
        self.pages.append(page_label)

    def update_overlays(self, fields: List[EditableField]):
        for page in self.pages:
            page.update_fields(fields)
