from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QTextEdit,
    QGroupBox, QScrollArea, QLabel, QPushButton, QHBoxLayout
)
from PySide6.QtCore import Signal
from typing import List, Dict
from ...core.models import EditableField, FieldCategory

class FormPanel(QWidget):
    field_changed = Signal(str, str) # field_id, new_value

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # Scroll area para los campos
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.scroll.setWidget(self.content_widget)
        
        self.layout.addWidget(self.scroll)
        
        # Botones de acción masiva
        self.actions_layout = QHBoxLayout()
        self.btn_apply_suggestions = QPushButton("Aplicar Sugerencias")
        self.btn_apply_suggestions.clicked.connect(self.apply_all_suggestions)
        self.actions_layout.addWidget(self.btn_apply_suggestions)
        self.layout.addLayout(self.actions_layout)

        self.inputs: Dict[str, QWidget] = {} # QLineEdit or QTextEdit
        self.fields_ref: List[EditableField] = []

    def load_fields(self, fields: List[EditableField]):
        self.fields_ref = fields
        # Limpiar
        for i in reversed(range(self.content_layout.count())):
            widget = self.content_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self.inputs.clear()

        # Agrupar por categoría
        groups = {}
        for f in fields:
            if f.category not in groups:
                groups[f.category] = []
            groups[f.category].append(f)

        # Crear grupos UI
        for category, group_fields in groups.items():
            group_box = QGroupBox(category.value)
            form_layout = QFormLayout()
            
            for field in group_fields:
                # Usar TextEdit (multilínea) para bibliografía y resultados
                is_multiline = field.category in [FieldCategory.BIBLIOGRAFIA, FieldCategory.RESULTADO]
                
                if is_multiline:
                    edit = QTextEdit()
                    edit.setPlainText(field.current_value)
                    edit.setMinimumHeight(60)
                    edit.setMaximumHeight(100)
                    edit.textChanged.connect(lambda f=field: self.on_text_change(f, self.inputs[f.id].toPlainText()))
                else:
                    edit = QLineEdit(field.current_value)
                    edit.textChanged.connect(lambda val, f=field: self.on_text_change(f, val))
                
                if field.suggested_value:
                    if isinstance(edit, QLineEdit):
                        edit.setPlaceholderText(f"Sugerido: {field.suggested_value}")
                    # Tooltip informativo
                    edit.setToolTip(f"Original: {field.original_value}\nSugerido: {field.suggested_value}")
                
                form_layout.addRow(field.label, edit)
                self.inputs[field.id] = edit
            
            group_box.setLayout(form_layout)
            self.content_layout.addWidget(group_box)
        
        self.content_layout.addStretch()

    def on_text_change(self, field: EditableField, new_value: str):
        field.current_value = new_value
        self.field_changed.emit(field.id, new_value)

    def apply_all_suggestions(self):
        for field in self.fields_ref:
            if field.suggested_value and field.current_value == field.original_value:
                if field.id in self.inputs:
                    widget = self.inputs[field.id]
                    if isinstance(widget, QLineEdit):
                        widget.setText(field.suggested_value)
                    elif isinstance(widget, QTextEdit):
                        widget.setPlainText(field.suggested_value)
