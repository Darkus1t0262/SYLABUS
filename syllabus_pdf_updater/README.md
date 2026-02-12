# Syllabus PDF Updater Pro

Aplicacion de escritorio para actualizar syllabus en PDF con un flujo rapido:

- analizar el PDF,
- detectar campos editables frecuentes,
- armar reemplazos masivos,
- validar coincidencias,
- generar PDF actualizado.

## Funciones principales

- Analisis automatico del PDF:
  - datos institucionales (`FACULTAD`, `CARRERA`, `MODALIDAD`, `ASIGNATURA`, `CODIGO`),
  - periodos (`PERIODO ACADEMICO`, `PERIODO DE EJECUCION`),
  - autoridades (`Docente`, `Coordinador`, `Director/a`),
  - unidades y temas semanales detectados.
- Deteccion de firma digital del PDF origen.
- Pestaña de `Campos sugeridos` para cargar cambios rapidos.
- Pestaña de `Reemplazos` para edicion manual y perfiles JSON.
- Pestaña de `Vista previa` para contar coincidencias antes de aplicar.
- Generacion de nuevo PDF actualizado (sin tocar el archivo original).

## Estructura del proyecto

```text
syllabus_pdf_updater/
  app.py
  document_analyzer.py
  pdf_tools.py
  requirements.txt
  profiles/
  tools/
    generate_profile.py
```

## Requisitos

- Windows con Python 3.10+ (probado en 3.14).
- Dependencia:
  - `pymupdf==1.26.5`

## Instalacion y ejecucion

```powershell
cd syllabus_pdf_updater
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## Flujo recomendado

1. `Cargar PDF`.
2. Revisar `Campos sugeridos`.
3. Completar los nuevos valores que quieras cambiar.
4. Click en `Enviar marcados a Reemplazos`.
5. Ir a `Vista previa y salida` y ejecutar `Contar coincidencias`.
6. Si el conteo es correcto, generar `PDF actualizado`.

## Perfiles JSON

Puedes guardar/cargar perfiles desde la pestaña `Reemplazos`.

Tambien tienes una plantilla base:

`profiles/plantilla_autoridades_periodo.json`

## Generar perfil automatico por script

El script `tools/generate_profile.py` crea un JSON desde un PDF analizado.

Ejemplo:

```powershell
cd syllabus_pdf_updater
.venv\Scripts\Activate.ps1
python tools\generate_profile.py `
  --pdf "C:\Users\Desmond\Downloads\TIP09BFT04  LEGISLACIÓN INFORMÁTICA P 25 26 Final-signed.pdf" `
  --output "profiles\perfil_autogenerado.json" `
  --include-empty
```

## Crear EXE para compartir

```powershell
cd syllabus_pdf_updater
.venv\Scripts\Activate.ps1
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name SyllabusUpdaterPro app.py
```

Salida:

`syllabus_pdf_updater\dist\SyllabusUpdaterPro.exe`

## Limitaciones importantes

- Si el PDF esta firmado digitalmente, al modificarlo la firma previa queda invalida.
- El motor funciona mejor con PDF con texto seleccionable.
- Si el texto original esta partido de forma extrema (por ejemplo por OCR de baja calidad), puede requerir ajustes manuales de reemplazo.
