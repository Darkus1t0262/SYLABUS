# Syllabus PDF Updater Pro

Aplicacion de escritorio para actualizar syllabus en PDF de forma rapida:
- cambios de autoridades,
- cambios de periodo,
- cambios de modalidad,
- cambios de temas y textos frecuentes.

El codigo principal esta en `syllabus_pdf_updater/`.

## Como funciona

1. Cargas un PDF de syllabus.
2. La app detecta campos sugeridos (institucionales, periodo, autoridades, temas).
3. Confirmas o editas reemplazos.
4. Ejecutas vista previa de coincidencias.
5. Generas un PDF nuevo actualizado.

Nota: si el PDF original tiene firma digital, al editarlo esa firma se invalida en el nuevo archivo.

## Requisitos

- Windows
- Python 3.10+ (recomendado 3.11+)

## Probar el proyecto

```powershell
cd syllabus_pdf_updater
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## Generar .exe

```powershell
cd syllabus_pdf_updater
.venv\Scripts\Activate.ps1
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name SyllabusUpdaterPro app.py
```

El ejecutable se genera en `syllabus_pdf_updater/dist/`.

## Estructura

```text
syllabus_pdf_updater/
  app.py
  document_analyzer.py
  pdf_tools.py
  tools/generate_profile.py
  profiles/
  README.md
```

## Trabajo en equipo

- Lee `CONTRIBUTING.md` para flujo de ramas y PR.
- Usa perfiles JSON en `syllabus_pdf_updater/profiles/` para compartir cambios.

## Publicar en GitHub (repo publico)

Si usas GitHub CLI (`gh`) y ya estas autenticado:

```powershell
git init -b main
git add .
git commit -m "Initial public release: Syllabus PDF Updater Pro"
gh repo create syllabus-pdf-updater-pro --public --source . --remote origin --push
```

Si no usas `gh`:
1. Crea el repo publico en GitHub web.
2. Conecta remoto y sube:

```powershell
git remote add origin https://github.com/TU_USUARIO/syllabus-pdf-updater-pro.git
git branch -M main
git push -u origin main
```
