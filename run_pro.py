import sys
from pathlib import Path

# Añadir el directorio actual al path para que Python encuentre el paquete 'syllabus_pro'
sys.path.append(str(Path(__file__).parent))

from syllabus_pro.main import main

if __name__ == "__main__":
    main()
