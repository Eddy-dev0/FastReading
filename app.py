"""Tkinter application for importing text and PDF files into a reading buffer."""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from pypdf import PdfReader
from tkinterdnd2 import DND_FILES, TkinterDnD

SUPPORTED_EXTENSIONS = {".txt", ".pdf"}


class FastReadingApp:
    """Small desktop UI that accepts .txt and .pdf files via drag and drop."""

    def __init__(self, root: TkinterDnD.Tk) -> None:
        self.root = root
        self.root.title("FastReading")
        self.root.geometry("900x650")
        self.root.minsize(720, 480)

        self.status = tk.StringVar(value="Ziehe .txt- oder .pdf-Dateien in das Feld oder wähle Dateien aus.")
        self.is_editing = tk.BooleanVar(value=False)
        self.edit_button_text = tk.StringVar(value="EDIT")
        self._build_layout()
        self._register_drop_target()

    def _build_layout(self) -> None:
        main_frame = ttk.Frame(self.root, padding=16)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)

        title = ttk.Label(
            main_frame,
            text="FastReading Datei-Import",
            font=("Arial", 18, "bold"),
        )
        title.grid(row=0, column=0, sticky="w", pady=(0, 12))

        self.drop_frame = ttk.LabelFrame(main_frame, text="Drag & Drop")
        self.drop_frame.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.drop_frame.columnconfigure(0, weight=1)

        drop_label = ttk.Label(
            self.drop_frame,
            text="Dateien hier ablegen\nUnterstützt: .txt und .pdf",
            anchor="center",
            justify="center",
            padding=28,
            font=("Arial", 13),
        )
        drop_label.grid(row=0, column=0, sticky="ew")

        button_row = ttk.Frame(self.drop_frame)
        button_row.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        button_row.columnconfigure(0, weight=1)

        browse_button = ttk.Button(
            button_row,
            text="Dateien auswählen",
            command=self.open_file_dialog,
        )
        browse_button.grid(row=0, column=0)

        text_frame = ttk.LabelFrame(main_frame, text="Eingefügter Text")
        text_frame.grid(row=2, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(1, weight=1)

        text_toolbar = ttk.Frame(text_frame)
        text_toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4))
        text_toolbar.columnconfigure(0, weight=1)

        edit_button = ttk.Button(
            text_toolbar,
            textvariable=self.edit_button_text,
            command=self.toggle_edit_mode,
        )
        edit_button.grid(row=0, column=1, sticky="e")

        self.text_box = tk.Text(text_frame, wrap="word", undo=True, font=("Arial", 12))
        self.text_box.grid(row=1, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.text_box.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.text_box.configure(state="disabled", yscrollcommand=scrollbar.set)

        status_label = ttk.Label(main_frame, textvariable=self.status, anchor="w")
        status_label.grid(row=3, column=0, sticky="ew", pady=(8, 0))

    def _register_drop_target(self) -> None:
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind("<<Drop>>", self.handle_drop)

    def handle_drop(self, event: tk.Event) -> None:
        paths = [Path(path) for path in self.root.tk.splitlist(event.data)]
        self.import_files(paths)

    def open_file_dialog(self) -> None:
        selected_files = filedialog.askopenfilenames(
            title="Text- oder PDF-Dateien auswählen",
            filetypes=(
                ("Text- und PDF-Dateien", "*.txt *.pdf"),
                ("Textdateien", "*.txt"),
                ("PDF-Dateien", "*.pdf"),
            ),
        )
        if selected_files:
            self.import_files([Path(file_path) for file_path in selected_files])

    def import_files(self, paths: list[Path]) -> None:
        imported_count = 0
        errors: list[str] = []

        for path in paths:
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                errors.append(f"{path.name}: Dateityp wird nicht unterstützt.")
                continue

            try:
                content = self.extract_text(path)
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
                continue

            self.append_document(path, content)
            imported_count += 1

        if imported_count:
            self.status.set(f"{imported_count} Datei(en) erfolgreich eingefügt.")
        if errors:
            messagebox.showwarning("Import-Hinweise", "\n".join(errors))
            self.status.set("Einige Dateien konnten nicht importiert werden.")

    def extract_text(self, path: Path) -> str:
        if path.suffix.lower() == ".txt":
            return self.extract_txt(path)
        return self.extract_pdf(path)

    @staticmethod
    def extract_txt(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1")

    @staticmethod
    def extract_pdf(path: Path) -> str:
        reader = PdfReader(path)
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            pages.append(f"--- Seite {index} ---\n{page_text.strip()}")
        return "\n\n".join(pages).strip()

    def toggle_edit_mode(self) -> None:
        is_editing = not self.is_editing.get()
        self.is_editing.set(is_editing)
        self.edit_button_text.set("Bearbeitung beenden" if is_editing else "EDIT")
        self.text_box.configure(state="normal" if is_editing else "disabled")
        if is_editing:
            self.text_box.focus_set()
            self.status.set("Bearbeitungsmodus aktiv: Der Text kann jetzt geändert werden.")
        else:
            self.status.set("Anzeigemodus aktiv: Der Text ist vor Änderungen geschützt.")

    def append_document(self, path: Path, content: str) -> None:
        was_editing = self.is_editing.get()
        self.text_box.configure(state="normal")
        separator = "\n\n" if self.text_box.get("1.0", "end-1c") else ""
        document_text = f"{separator}===== {path.name} =====\n{content}\n"
        self.text_box.insert("end", document_text)
        self.text_box.see("end")
        if not was_editing:
            self.text_box.configure(state="disabled")


def main() -> None:
    root = TkinterDnD.Tk()
    app = FastReadingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
