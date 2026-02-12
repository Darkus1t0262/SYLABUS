from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

from document_analyzer import DocumentAnalysis, SuggestedField, analyze_pdf
from pdf_tools import ReplacementPair, preview_replacements, replace_text_in_pdf


class SyllabusUpdaterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Syllabus PDF Updater Pro")
        self.root.geometry("1320x840")
        self.root.minsize(1120, 700)

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()

        self.stats_pages_var = tk.StringVar(value="-")
        self.stats_text_var = tk.StringVar(value="-")
        self.stats_signature_var = tk.StringVar(value="-")
        self.stats_suggestions_var = tk.StringVar(value="-")
        self.suggested_caption_var = tk.StringVar(value="Carga un PDF para analizar campos.")

        self.analysis: Optional[DocumentAnalysis] = None
        self.suggested_rows: List[Dict[str, object]] = []
        self.replacement_rows: List[Dict[str, object]] = []

        self._configure_style()
        self._build_ui()
        self._add_replacement_row("Rector Antiguo", "Rector Nuevo")
        self._add_replacement_row("Tema Antiguo", "Tema Nuevo")

    def _configure_style(self) -> None:
        self.root.configure(bg="#f2f5f9")
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure("App.TFrame", background="#f2f5f9")
        style.configure("Panel.TFrame", background="#ffffff")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Header.TLabel", background="#f2f5f9", foreground="#162137", font=("Segoe UI", 20, "bold"))
        style.configure("SubHeader.TLabel", background="#f2f5f9", foreground="#4b5b77", font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background="#ffffff", foreground="#4b5b77", font=("Segoe UI", 9, "bold"))
        style.configure("CardValue.TLabel", background="#ffffff", foreground="#102341", font=("Segoe UI", 16, "bold"))
        style.configure("Accent.TButton", foreground="#ffffff", background="#0f62fe", padding=(10, 8))
        style.map("Accent.TButton", background=[("active", "#0353e9"), ("pressed", "#0349cf")])
        style.configure("Muted.TLabel", background="#ffffff", foreground="#6b7280", font=("Segoe UI", 9))
        style.configure("TNotebook", background="#f2f5f9", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12, 8), font=("Segoe UI", 10, "bold"))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, style="App.TFrame", padding=18)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)

        self._build_header(main)
        self._build_file_panel(main)
        self._build_stats_panel(main)
        self._build_work_tabs(main)

    def _build_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)

        ttk.Label(
            header,
            text="Syllabus PDF Updater Pro",
            style="Header.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Automatiza cambios de autoridades, periodos, temas y datos institucionales.",
            style="SubHeader.TLabel",
        ).grid(row=1, column=0, sticky="w")

    def _build_file_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Panel.TFrame", padding=12)
        panel.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        panel.columnconfigure(1, weight=1)

        ttk.Label(panel, text="PDF origen", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(panel, textvariable=self.input_var).grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(panel, text="Cargar PDF", command=self._pick_input_pdf).grid(row=0, column=2, sticky="ew")
        ttk.Button(panel, text="Analizar PDF", style="Accent.TButton", command=self._analyze_current_pdf).grid(
            row=0, column=3, sticky="ew", padx=(8, 0)
        )

        ttk.Label(panel, text="PDF salida", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(panel, textvariable=self.output_var).grid(
            row=1, column=1, sticky="ew", padx=(8, 8), pady=(8, 0)
        )
        ttk.Button(panel, text="Guardar como", command=self._pick_output_pdf).grid(
            row=1, column=2, sticky="ew", pady=(8, 0)
        )
        ttk.Button(panel, text="Generar PDF final", style="Accent.TButton", command=self._run_update).grid(
            row=1, column=3, sticky="ew", padx=(8, 0), pady=(8, 0)
        )

    def _build_stats_panel(self, parent: ttk.Frame) -> None:
        cards = ttk.Frame(parent, style="App.TFrame")
        cards.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)
        cards.columnconfigure(2, weight=1)
        cards.columnconfigure(3, weight=1)

        self._create_stat_card(cards, 0, "Paginas", self.stats_pages_var)
        self._create_stat_card(cards, 1, "Paginas con texto", self.stats_text_var)
        self._create_stat_card(cards, 2, "Firma detectada", self.stats_signature_var)
        self._create_stat_card(cards, 3, "Campos sugeridos", self.stats_suggestions_var)

    def _create_stat_card(self, parent: ttk.Frame, col: int, title: str, value_var: tk.StringVar) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=12)
        card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0))
        card.columnconfigure(0, weight=1)
        ttk.Label(card, text=title, style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(card, textvariable=value_var, style="CardValue.TLabel").grid(row=1, column=0, sticky="w")

    def _build_work_tabs(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.grid(row=3, column=0, sticky="nsew")

        tab_suggested = ttk.Frame(notebook, style="Panel.TFrame", padding=12)
        tab_replace = ttk.Frame(notebook, style="Panel.TFrame", padding=12)
        tab_preview = ttk.Frame(notebook, style="Panel.TFrame", padding=12)

        notebook.add(tab_suggested, text="Campos sugeridos")
        notebook.add(tab_replace, text="Reemplazos")
        notebook.add(tab_preview, text="Vista previa y salida")

        self._build_suggested_tab(tab_suggested)
        self._build_replace_tab(tab_replace)
        self._build_preview_tab(tab_preview)

    def _build_suggested_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

        actions = ttk.Frame(parent, style="Panel.TFrame")
        actions.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(actions, text="Analizar de nuevo", command=self._analyze_current_pdf).pack(side="left")
        ttk.Button(actions, text="Proponer periodo +1", command=self._suggest_next_cycle).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Marcar todo", command=lambda: self._set_all_suggested_enabled(True)).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(actions, text="Desmarcar todo", command=lambda: self._set_all_suggested_enabled(False)).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(actions, text="Enviar marcados a Reemplazos", style="Accent.TButton", command=self._push_suggested_to_replacements).pack(
            side="right"
        )

        ttk.Label(parent, textvariable=self.suggested_caption_var, style="Muted.TLabel").grid(
            row=1, column=0, sticky="w", pady=(0, 6)
        )

        table_wrap = ttk.Frame(parent, style="Panel.TFrame")
        table_wrap.grid(row=2, column=0, sticky="nsew")
        table_wrap.columnconfigure(0, weight=1)
        table_wrap.rowconfigure(1, weight=1)

        header = ttk.Frame(table_wrap, style="Panel.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        header.columnconfigure(3, weight=1)
        header.columnconfigure(4, weight=1)
        ttk.Label(header, text="Usar", style="Muted.TLabel", width=6).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Categoria", style="Muted.TLabel", width=20).grid(row=0, column=1, sticky="w")
        ttk.Label(header, text="Campo", style="Muted.TLabel", width=24).grid(row=0, column=2, sticky="w")
        ttk.Label(header, text="Buscar", style="Muted.TLabel").grid(row=0, column=3, sticky="w", padx=(8, 8))
        ttk.Label(header, text="Reemplazar", style="Muted.TLabel").grid(row=0, column=4, sticky="w", padx=(8, 8))

        canvas = tk.Canvas(table_wrap, borderwidth=0, highlightthickness=0, background="#ffffff")
        scroll = ttk.Scrollbar(table_wrap, orient="vertical", command=canvas.yview)
        self.suggested_rows_frame = ttk.Frame(canvas, style="Panel.TFrame")
        self.suggested_rows_frame.columnconfigure(3, weight=1)
        self.suggested_rows_frame.columnconfigure(4, weight=1)

        self.suggested_rows_frame.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        self.suggested_window_id = canvas.create_window((0, 0), window=self.suggested_rows_frame, anchor="nw")
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(self.suggested_window_id, width=event.width),
        )
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=1, column=0, sticky="nsew")
        scroll.grid(row=1, column=1, sticky="ns")

    def _build_replace_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        actions = ttk.Frame(parent, style="Panel.TFrame")
        actions.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(actions, text="+ Agregar fila", command=self._add_replacement_row).pack(side="left")
        ttk.Button(actions, text="Limpiar filas", command=self._clear_replacement_rows).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Cargar perfil", command=self._load_profile).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Guardar perfil", command=self._save_profile).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Vista previa de coincidencias", style="Accent.TButton", command=self._run_preview).pack(
            side="right"
        )

        table_wrap = ttk.Frame(parent, style="Panel.TFrame")
        table_wrap.grid(row=1, column=0, sticky="nsew")
        table_wrap.columnconfigure(0, weight=1)
        table_wrap.rowconfigure(1, weight=1)

        header = ttk.Frame(table_wrap, style="Panel.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        header.columnconfigure(1, weight=1)
        header.columnconfigure(2, weight=1)
        ttk.Label(header, text="#", style="Muted.TLabel", width=4).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Buscar", style="Muted.TLabel").grid(row=0, column=1, sticky="w", padx=(8, 8))
        ttk.Label(header, text="Reemplazar", style="Muted.TLabel").grid(row=0, column=2, sticky="w", padx=(8, 8))

        canvas = tk.Canvas(table_wrap, borderwidth=0, highlightthickness=0, background="#ffffff")
        scroll = ttk.Scrollbar(table_wrap, orient="vertical", command=canvas.yview)
        self.replacement_rows_frame = ttk.Frame(canvas, style="Panel.TFrame")
        self.replacement_rows_frame.columnconfigure(1, weight=1)
        self.replacement_rows_frame.columnconfigure(2, weight=1)

        self.replacement_rows_frame.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        self.replacement_window_id = canvas.create_window((0, 0), window=self.replacement_rows_frame, anchor="nw")
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(self.replacement_window_id, width=event.width),
        )
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=1, column=0, sticky="nsew")
        scroll.grid(row=1, column=1, sticky="ns")

    def _build_preview_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        parent.rowconfigure(2, weight=1)

        actions = ttk.Frame(parent, style="Panel.TFrame")
        actions.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(actions, text="Contar coincidencias", command=self._run_preview).pack(side="left")
        ttk.Button(actions, text="Generar PDF actualizado", style="Accent.TButton", command=self._run_update).pack(
            side="left", padx=(8, 0)
        )

        preview_wrap = ttk.Frame(parent, style="Panel.TFrame")
        preview_wrap.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        preview_wrap.columnconfigure(0, weight=1)
        preview_wrap.rowconfigure(0, weight=1)

        columns = ("buscar", "reemplazar", "hits", "estado")
        self.preview_tree = ttk.Treeview(
            preview_wrap,
            columns=columns,
            show="headings",
            height=12,
        )
        self.preview_tree.heading("buscar", text="Buscar")
        self.preview_tree.heading("reemplazar", text="Reemplazar")
        self.preview_tree.heading("hits", text="Coincidencias")
        self.preview_tree.heading("estado", text="Estado")
        self.preview_tree.column("buscar", width=360, anchor="w")
        self.preview_tree.column("reemplazar", width=360, anchor="w")
        self.preview_tree.column("hits", width=110, anchor="center")
        self.preview_tree.column("estado", width=130, anchor="center")
        self.preview_tree.grid(row=0, column=0, sticky="nsew")
        preview_scroll = ttk.Scrollbar(preview_wrap, orient="vertical", command=self.preview_tree.yview)
        preview_scroll.grid(row=0, column=1, sticky="ns")
        self.preview_tree.configure(yscrollcommand=preview_scroll.set)

        log_wrap = ttk.Frame(parent, style="Panel.TFrame")
        log_wrap.grid(row=2, column=0, sticky="nsew")
        log_wrap.columnconfigure(0, weight=1)
        log_wrap.rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_wrap, height=10, wrap="word", borderwidth=0, padx=10, pady=8)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_wrap, orient="vertical", command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scroll.set)

    def _pick_input_pdf(self) -> None:
        path = filedialog.askopenfilename(
            title="Seleccionar PDF de syllabus",
            filetypes=[("PDF", "*.pdf")],
        )
        if not path:
            return
        self.input_var.set(path)
        self._suggest_output_path()
        self._analyze_current_pdf()

    def _pick_output_pdf(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Guardar PDF actualizado",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        if path:
            self.output_var.set(path)

    def _suggest_output_path(self) -> None:
        current_input = self.input_var.get().strip()
        if not current_input:
            return
        p = Path(current_input)
        if not self.output_var.get().strip():
            self.output_var.set(str(p.with_name(f"{p.stem}_actualizado.pdf")))

    def _analyze_current_pdf(self) -> None:
        input_path = Path(self.input_var.get().strip())
        if not input_path.exists():
            messagebox.showerror("Error", "Selecciona un PDF origen valido.")
            return
        if input_path.suffix.lower() != ".pdf":
            messagebox.showerror("Error", "El archivo origen debe ser PDF.")
            return

        try:
            self.analysis = analyze_pdf(input_path)
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo analizar el PDF: {exc}")
            return

        assert self.analysis is not None
        self.stats_pages_var.set(str(self.analysis.page_count))
        self.stats_text_var.set(f"{self.analysis.searchable_pages}/{self.analysis.page_count}")
        self.stats_signature_var.set("Si" if self.analysis.signed_source_detected else "No")
        self.stats_suggestions_var.set(str(len(self.analysis.suggested_fields)))
        self.suggested_caption_var.set(
            f"Campos detectados: {len(self.analysis.suggested_fields)} | "
            f"Unidades: {len(self.analysis.unit_names)} | Temas: {len(self.analysis.weekly_topics)}"
        )
        self._render_suggested_fields(self.analysis.suggested_fields)

        self._log("PDF analizado correctamente.")
        self._log(
            f"Paginas: {self.analysis.page_count} | Texto extraible: {self.analysis.searchable_pages}/{self.analysis.page_count}"
        )
        if self.analysis.signed_source_detected:
            self._log("Aviso: el PDF parece firmado. Cualquier cambio invalida la firma previa.")
        for warning in self.analysis.warnings:
            self._log(f"Aviso: {warning}")

    def _clear_suggested_rows(self) -> None:
        for row in self.suggested_rows:
            row["frame"].destroy()
        self.suggested_rows = []

    def _render_suggested_fields(self, fields: List[SuggestedField]) -> None:
        self._clear_suggested_rows()
        for idx, field in enumerate(fields, start=1):
            frame = ttk.Frame(self.suggested_rows_frame, style="Panel.TFrame", padding=(4, 2))
            frame.grid(row=idx, column=0, sticky="ew")
            frame.columnconfigure(3, weight=1)
            frame.columnconfigure(4, weight=1)

            use_var = tk.BooleanVar(value=True)
            source_var = tk.StringVar(value=field.current_value)
            target_var = tk.StringVar(value=field.suggested_value)

            ttk.Checkbutton(frame, variable=use_var).grid(row=0, column=0, sticky="w")
            ttk.Label(frame, text=field.category, width=20).grid(row=0, column=1, sticky="w", padx=(4, 8))
            ttk.Label(frame, text=field.label, width=24).grid(row=0, column=2, sticky="w", padx=(0, 8))
            source_entry = ttk.Entry(frame, textvariable=source_var)
            source_entry.grid(row=0, column=3, sticky="ew", padx=(0, 8))
            source_entry.state(["readonly"])
            ttk.Entry(frame, textvariable=target_var).grid(row=0, column=4, sticky="ew", padx=(0, 8))

            self.suggested_rows.append(
                {
                    "frame": frame,
                    "use_var": use_var,
                    "source_var": source_var,
                    "target_var": target_var,
                    "category": field.category,
                    "label": field.label,
                }
            )

    def _set_all_suggested_enabled(self, enabled: bool) -> None:
        for row in self.suggested_rows:
            row["use_var"].set(enabled)

    def _suggest_next_cycle(self) -> None:
        for row in self.suggested_rows:
            category = str(row["category"])
            source = str(row["source_var"].get()).strip()
            target_var: tk.StringVar = row["target_var"]
            current_target = target_var.get().strip()
            if current_target:
                continue
            if category in {"Periodo", "Fechas globales"}:
                proposal = self._next_cycle_from_token(source)
                if proposal:
                    target_var.set(proposal)
        self._log("Se aplico propuesta automatica de periodo para filas vacias.")

    def _next_cycle_from_token(self, value: str) -> str:
        if "-" in value:
            parts = value.split("-")
            if len(parts) == 2 and parts[0].isdigit() and parts[0].startswith("20"):
                left = parts[0]
                right = parts[1]
                if len(right) == 4 and right.isdigit():
                    return f"{int(left) + 1}-{int(right) + 1}"
                if len(right) == 2 and right.isdigit():
                    return f"{int(left) + 1}-{right}"
        return ""

    def _push_suggested_to_replacements(self) -> None:
        added = 0
        skipped_empty = 0
        existing = {str(row["source_var"].get()).strip() for row in self.replacement_rows}

        for row in self.suggested_rows:
            if not row["use_var"].get():
                continue
            source = str(row["source_var"].get()).strip()
            target = str(row["target_var"].get()).strip()
            if not source:
                continue
            if not target:
                skipped_empty += 1
                continue
            if source in existing:
                continue
            self._add_replacement_row(source, target)
            existing.add(source)
            added += 1

        self._log(f"Se agregaron {added} cambios sugeridos a la lista de reemplazos.")
        if skipped_empty:
            self._log(f"Se omitieron {skipped_empty} sugerencias sin valor de reemplazo.")

    def _add_replacement_row(self, source: str = "", target: str = "") -> None:
        idx = len(self.replacement_rows) + 1
        frame = ttk.Frame(self.replacement_rows_frame, style="Panel.TFrame", padding=(4, 2))
        frame.grid(row=idx, column=0, sticky="ew")
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)

        number = ttk.Label(frame, text=f"{idx}.", width=4)
        number.grid(row=0, column=0, sticky="w")
        source_var = tk.StringVar(value=source)
        target_var = tk.StringVar(value=target)
        ttk.Entry(frame, textvariable=source_var).grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Entry(frame, textvariable=target_var).grid(row=0, column=2, sticky="ew", padx=(0, 8))
        ttk.Button(frame, text="Quitar", command=lambda: self._remove_replacement_row(frame)).grid(
            row=0, column=3, sticky="e"
        )

        self.replacement_rows.append(
            {
                "frame": frame,
                "number": number,
                "source_var": source_var,
                "target_var": target_var,
            }
        )
        self._renumber_replacement_rows()

    def _remove_replacement_row(self, frame: ttk.Frame) -> None:
        if len(self.replacement_rows) == 1:
            messagebox.showwarning("Atencion", "Debe existir al menos una fila.")
            return
        self.replacement_rows = [row for row in self.replacement_rows if row["frame"] != frame]
        frame.destroy()
        self._renumber_replacement_rows()

    def _clear_replacement_rows(self) -> None:
        for row in self.replacement_rows:
            row["frame"].destroy()
        self.replacement_rows = []
        self._add_replacement_row()

    def _renumber_replacement_rows(self) -> None:
        for idx, row in enumerate(self.replacement_rows, start=1):
            row["frame"].grid_configure(row=idx)
            row["number"].configure(text=f"{idx}.")

    def _collect_replacements(self) -> List[ReplacementPair]:
        pairs: List[ReplacementPair] = []
        seen = set()
        for row in self.replacement_rows:
            source = str(row["source_var"].get()).strip()
            target = str(row["target_var"].get()).strip()
            if not source and not target:
                continue
            if not source:
                raise ValueError("Hay una fila con Buscar vacio.")
            if source in seen:
                continue
            seen.add(source)
            pairs.append((source, target))

        if not pairs:
            raise ValueError("No hay reemplazos validos.")
        return pairs

    def _load_profile(self) -> None:
        path = filedialog.askopenfilename(
            title="Cargar perfil de cambios",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return

        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            replacements = payload.get("replacements", [])
            pairs: List[ReplacementPair] = []
            for item in replacements:
                source = str(item.get("find", "")).strip()
                target = str(item.get("replace", ""))
                if source:
                    pairs.append((source, target))
            if not pairs:
                raise ValueError("El perfil no contiene datos validos.")
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo cargar el perfil: {exc}")
            return

        for row in self.replacement_rows:
            row["frame"].destroy()
        self.replacement_rows = []
        for source, target in pairs:
            self._add_replacement_row(source, target)
        self._log(f"Perfil cargado con {len(pairs)} reemplazos.")

    def _save_profile(self) -> None:
        try:
            pairs = self._collect_replacements()
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
            return

        path = filedialog.asksaveasfilename(
            title="Guardar perfil de cambios",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return

        payload = {
            "app": "Syllabus PDF Updater Pro",
            "replacements": [{"find": source, "replace": target} for source, target in pairs],
        }
        Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self._log(f"Perfil guardado: {path}")

    def _run_preview(self) -> None:
        input_path = Path(self.input_var.get().strip())
        if not input_path.exists():
            messagebox.showerror("Error", "Selecciona un PDF origen valido.")
            return

        try:
            replacements = self._collect_replacements()
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
            return

        try:
            preview = preview_replacements(input_path, replacements)
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo generar vista previa: {exc}")
            return

        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)

        for source, target in replacements:
            hits = preview.per_term.get(source, 0)
            status = "OK" if hits > 0 else "Sin match"
            self.preview_tree.insert("", "end", values=(source, target, hits, status))

        self._log(f"Vista previa: {preview.total_matches} coincidencias totales.")
        if preview.signed_source_detected:
            self._log("Aviso: el PDF origen parece firmado digitalmente.")

    def _run_update(self) -> None:
        input_path = Path(self.input_var.get().strip())
        output_path = Path(self.output_var.get().strip())

        if not input_path.exists():
            messagebox.showerror("Error", "Selecciona un PDF origen valido.")
            return
        if output_path.suffix.lower() != ".pdf":
            messagebox.showerror("Error", "El archivo de salida debe ser .pdf.")
            return
        if input_path.resolve() == output_path.resolve():
            messagebox.showerror("Error", "El PDF de salida debe ser diferente al origen.")
            return

        try:
            replacements = self._collect_replacements()
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
            return

        try:
            result = replace_text_in_pdf(input_path, output_path, replacements)
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo generar el PDF actualizado: {exc}")
            return

        self._log(f"Salida: {result.output_path}")
        self._log(f"Reemplazos aplicados: {result.total_replacements}")
        for source, count in result.per_term.items():
            self._log(f"  - {source}: {count}")
        if result.signed_source_detected:
            self._log("Aviso: la firma del PDF original se invalida en el documento actualizado.")

        messagebox.showinfo(
            "Proceso completado",
            f"PDF actualizado generado.\nReemplazos aplicados: {result.total_replacements}",
        )

    def _log(self, message: str) -> None:
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")


def main() -> None:
    root = tk.Tk()
    app = SyllabusUpdaterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
