# Syllabus PDF Updater Pro 📄✨

**Syllabus PDF Updater Pro** es una herramienta de escritorio diseñada para facilitar la actualización de sílabos universitarios. 

Su objetivo es simple: **ahorrarte tiempo**. En lugar de copiar y pegar manualmente en documentos Word desordenados, esta aplicación lee tu PDF anterior, identifica los datos que cambian semestralmente (fechas, nombres, horas) y te permite actualizarlos en una interfaz moderna, generando un nuevo PDF listo para firmar.

---

## 🚀 ¿Qué hace esta aplicación?

1.  **Carga tu Sílabo Anterior**: Abre cualquier PDF de sílabo (generado digitalmente).
2.  **Detecta Datos Automáticamente**: Encuentra el periodo académico, nombre del docente, autoridades, y bibliografía.
3.  **Formulario de Edición Rápida**: Te presenta un formulario sencillo para cambiar esos datos.
4.  **Sugerencias Inteligentes**: Calcula automáticamente el nuevo periodo (ej. si lee "2025", sugiere "2026").
5.  **Vista Previa en Tiempo Real**: Ves el documento original a la izquierda y tus cambios a la derecha.
6.  **Guardado Seguro**: Genera un nuevo archivo PDF manteniendo el diseño exacto del original.

---

## 🛠️ Requisitos Previos

Antes de empezar, necesitas:
*   **Sistema Operativo**: Windows 10/11 (recomendado), macOS o Linux.
*   **Python 3.10 o superior**: [Descargar Python aquí](https://www.python.org/downloads/).
    *   *Nota: Al instalar Python en Windows, asegúrate de marcar la casilla "Add Python to PATH".*

---

## 📦 Guía de Instalación (Paso a Paso)

Sigue estos pasos en tu terminal (PowerShell o CMD):

### 1. Ubícate en la carpeta del proyecto
```bash
cd "d:\Documentos\Decimo\legislación\SYLABUS\syllabus_pro"
```

### 2. Crea un entorno virtual (Opcional pero recomendado)
Esto aísla las librerías del proyecto para no afectar tu sistema.
```bash
python -m venv .venv
```

### 3. Activa el entorno virtual
*   **En Windows:**
    ```bash
    .venv\Scripts\activate
    ```
    *(Verás que aparece `(.venv)` al inicio de tu línea de comandos).*

*   **En Mac/Linux:**
    ```bash
    source .venv/bin/activate
    ```

### 4. Instala las dependencias necesarias
```bash
pip install -r requirements.txt
```

---

## ▶️ Cómo Iniciar la App

Una vez instaladas las dependencias, inicia la aplicación con:

```bash
python main.py
```

---

## 📖 Cómo Usar la Aplicación

1.  **Abrir**: Haz clic en el botón **"Abrir PDF"** (esquina superior izquierda) y selecciona tu archivo.
2.  **Revisar**: La aplicación analizará el documento.
    *   A la **Izquierda**: Verás tu PDF.
    *   A la **Derecha**: Verás los campos editables detectados.
3.  **Editar**:
    *   Corrige nombres, fechas o textos.
    *   Si ves un botón **"Aplicar Sugerencias"** al final, úsalo para actualizar fechas automáticamente.
4.  **Guardar**:
    *   Haz clic en **"Guardar PDF Actualizado"**.
    *   Elige dónde guardar tu nuevo sílabo. ¡Listo!

---

## ❓ Solución de Problemas

*   **Error "Bad file descriptor" al guardar**:
    *   Solución: Intenta guardar el archivo con un nombre diferente (ej. `silabo_nuevo.pdf` en lugar de sobrescribir `silabo.pdf`).
    *   *Nota: Este error ha sido mitigado en la versión actual, pero si ocurre, usa "Guardar como".*

*   **No detecta texto (PDF escaneado)**:
    *   Actualmente, la aplicación funciona mejor con PDFs generados digitalmente (Word -> PDF).
    *   Soporte para documentos escaneados (OCR) está en desarrollo.

*   **La interfaz se ve pequeña/grande**:
    *   La aplicación intenta adaptarse a tu pantalla. Puedes maximizar la ventana para trabajar más cómodamente.

---

## 📂 Estructura de Carpetas (Para Desarrolladores)

*   `core/`: Modelos de datos y configuración.
*   `services/`: Lógica de procesamiento de PDF (lectura y escritura).
*   `ui/`: Interfaz gráfica (ventanas y botones).
*   `main.py`: Archivo de arranque.
