# Contributing Guide

Gracias por colaborar en este proyecto.

## Flujo recomendado

1. Crea una rama desde `main`:
   - `feat/<descripcion-corta>` para nuevas funciones
   - `fix/<descripcion-corta>` para correcciones
2. Haz cambios pequenos y claros.
3. Prueba la app localmente.
4. Abre un Pull Request con:
   - objetivo del cambio,
   - pasos para probar,
   - capturas si hubo cambios de interfaz.

## Convenciones basicas

- Mantener el codigo legible y simple.
- Evitar dependencias nuevas sin justificar.
- No subir binarios generados (`dist/`, `build/`).
- No subir entornos virtuales (`.venv/`).

## Prueba rapida antes de PR

```powershell
cd syllabus_pdf_updater
python -m py_compile app.py document_analyzer.py pdf_tools.py tools\generate_profile.py
```
