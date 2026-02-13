import sys
import os
from pathlib import Path

# Add project root to sys.path
current_dir = Path(__file__).parent
sys.path.append(str(current_dir.parent))

from PySide6.QtWidgets import QApplication
from syllabus_pro.ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # Estilo Fusion para look moderno cross-platform
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
