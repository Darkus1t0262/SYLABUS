from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QLabel
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QPen, QFont
from PySide6.QtCore import Qt, QRectF
from typing import List, Optional, Tuple
from ...core.models import EditableField

class PDFPageLabel(QLabel):
    def __init__(self, page_num: int, page_size: Tuple[float, float], parent=None):
        super().__init__(parent)
        self.page_num = page_num
        self.page_width = page_size[0] if page_size[0] > 0 else 1.0
        self.page_height = page_size[1] if page_size[1] > 0 else 1.0
        self.original_pixmap: Optional[QPixmap] = None
        self.fields: List[EditableField] = []

    def set_image(self, image_bytes: bytes):
        image = QImage.fromData(image_bytes)
        self.original_pixmap = QPixmap.fromImage(image)
        self.refresh_view()

    def update_fields(self, fields: List[EditableField]):
        self.fields = [f for f in fields if f.page_number == self.page_num]
        self.refresh_view()

    def _map_pdf_rect_to_image(self, rect: List[float], pixmap: QPixmap) -> QRectF:
        x0, y0, x1, y1 = rect
        scale_x = pixmap.width() / self.page_width
        scale_y = pixmap.height() / self.page_height
        left = x0 * scale_x
        top = y0 * scale_y
        width = max(1.0, (x1 - x0) * scale_x)
        height = max(1.0, (y1 - y0) * scale_y)
        return QRectF(left, top, width, height)

    def refresh_view(self):
        if not self.original_pixmap:
            return

        display_pixmap = self.original_pixmap.copy()
        painter = QPainter(display_pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)

        modified_without_rect = 0

        for field in self.fields:
            if not field.is_modified:
                continue
            if not field.rect or len(field.rect) != 4:
                modified_without_rect += 1
                continue

            mapped_rect = self._map_pdf_rect_to_image(field.rect, display_pixmap)
            painter.fillRect(mapped_rect, QColor(255, 255, 255, 225))
            painter.setPen(QPen(QColor(44, 102, 178, 220), 1))
            painter.drawRect(mapped_rect)

            font_size = max(7, min(11, int(mapped_rect.height() * 0.35)))
            painter.setFont(QFont("Arial", font_size))
            painter.setPen(QColor(20, 20, 20))
            text_rect = mapped_rect.adjusted(2, 1, -2, -1)
            painter.drawText(
                text_rect,
                Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignVCenter,
                field.current_value
            )

        if modified_without_rect > 0:
            badge_rect = QRectF(8, 8, max(180.0, display_pixmap.width() * 0.45), 24)
            painter.fillRect(badge_rect, QColor(30, 30, 30, 170))
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Arial", 9, QFont.Bold))
            painter.drawText(
                badge_rect.adjusted(8, 0, -8, 0),
                Qt.AlignLeft | Qt.AlignVCenter,
                f"Cambios sin coordenadas: {modified_without_rect}"
            )

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

    def add_page(self, image_bytes: bytes, page_num: int, page_size: Tuple[float, float]):
        page_label = PDFPageLabel(page_num, page_size)
        page_label.set_image(image_bytes)
        self.layout.addWidget(page_label)
        self.pages.append(page_label)

    def update_overlays(self, fields: List[EditableField]):
        for page in self.pages:
            page.update_fields(fields)
