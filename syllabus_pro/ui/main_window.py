import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QFileDialog, QSplitter, QToolBar, QMessageBox, QStatusBar
)
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import Qt

from ..services.pdf_service import PDFService
from .widgets.pdf_viewer import PDFViewer
from .widgets.form_panel import FormPanel

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Syllabus PDF Updater Pro")
        self.resize(1200, 800)
        
        self.pdf_service = PDFService()
        self.current_analysis = None
        
        self._init_ui()
        self._create_actions()
        self._create_toolbar()
        self._create_statusbar()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Splitter principal
        splitter = QSplitter(Qt.Horizontal)
        
        # Panel izquierdo (Visor PDF)
        self.viewer = PDFViewer()
        splitter.addWidget(self.viewer)
        
        # Panel derecho (Formulario)
        self.form_panel = FormPanel()
        self.form_panel.field_changed.connect(self.on_field_changed)
        splitter.addWidget(self.form_panel)
        
        splitter.setStretchFactor(0, 2) # Visor más ancho
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter)

    def _create_actions(self):
        self.act_open = QAction("Abrir PDF", self)
        self.act_open.triggered.connect(self.open_pdf)
        
        self.act_save = QAction("Guardar PDF Actualizado", self)
        self.act_save.triggered.connect(self.save_pdf)
        self.act_save.setEnabled(False)

        self.act_exit = QAction("Salir", self)
        self.act_exit.triggered.connect(self.close)

    def _create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        toolbar.addAction(self.act_open)
        toolbar.addAction(self.act_save)

    def _create_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Listo. Abre un sílabo para comenzar.")

    def open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir Sílabo PDF", "", "PDF Files (*.pdf)"
        )
        if not path:
            return
            
        try:
            self.status.showMessage(f"Analizando {path}...")
            self.current_analysis = self.pdf_service.load_pdf(Path(path))
            
            # Cargar UI
            self.viewer.clear()
            for i in range(self.current_analysis.page_count):
                img_bytes = self.pdf_service.get_page_image(i)
                self.viewer.add_page(img_bytes, i)
            
            self.form_panel.load_fields(self.current_analysis.fields)
            
            # Actualizar estado
            msg = f"Cargado: {self.current_analysis.page_count} páginas. "
            if self.current_analysis.is_signed:
                msg += "[Firma Digital Detectada - Se perderá al guardar]"
            self.status.showMessage(msg)
            self.act_save.setEnabled(True)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar el PDF:\n{str(e)}")
            self.status.showMessage("Error al cargar.")

    def save_pdf(self):
        if not self.current_analysis:
            return
            
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar PDF", "", "PDF Files (*.pdf)"
        )
        if not path:
            return
            
        try:
            self.pdf_service.save_pdf(Path(path), self.current_analysis.fields)
            QMessageBox.information(self, "Éxito", "PDF generado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar:\n{str(e)}")

    def on_field_changed(self, field_id: str, new_val: str):
        # Aquí podríamos actualizar el overlay del visor en tiempo real
        if self.current_analysis:
            self.viewer.update_overlays(self.current_analysis.fields)

    def closeEvent(self, event):
        self.pdf_service.close()
        event.accept()
