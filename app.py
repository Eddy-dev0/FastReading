"""Tkinter application for importing text and PDF files into a reading buffer."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk
from pypdf import PdfReader
from tkinterdnd2 import DND_FILES, TkinterDnD

SUPPORTED_EXTENSIONS = {".txt", ".pdf"}
MAX_PDF_IMAGE_WIDTH = 760


@dataclass
class DocumentPart:
    """A text or image fragment extracted from an imported document."""

    kind: str
    content: str | bytes


class FastReadingApp:
    """Small desktop UI that accepts .txt and .pdf files via drag and drop."""

    def __init__(self, root: TkinterDnD.Tk) -> None:
        self.root = root
        self.root.title("FastReading")
        self.root.geometry("900x650")
        self.root.minsize(720, 480)

        self.status = tk.StringVar(value="Drop .txt or .pdf files into the field, or choose files manually.")
        self.is_editing = tk.BooleanVar(value=False)
        self.edit_button_text = tk.StringVar(value="EDIT")
        self.pdf_images: list[ImageTk.PhotoImage] = []
        self._build_layout()
        self._register_drop_target()

    def _build_layout(self) -> None:
        main_frame = ttk.Frame(self.root, padding=16)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)

        title = ttk.Label(
            main_frame,
            text="FastReading File Import",
            font=("Arial", 18, "bold"),
        )
        title.grid(row=0, column=0, sticky="w", pady=(0, 12))

        self.drop_frame = ttk.LabelFrame(main_frame, text="Drag & Drop")
        self.drop_frame.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.drop_frame.columnconfigure(0, weight=1)

        drop_label = ttk.Label(
            self.drop_frame,
            text="Drop files here\nSupported: .txt and .pdf",
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
            text="Choose files",
            command=self.open_file_dialog,
        )
        browse_button.grid(row=0, column=0)

        text_frame = ttk.LabelFrame(main_frame, text="Inserted Text")
        text_frame.grid(row=2, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(1, weight=1)

        text_toolbar = ttk.Frame(text_frame)
        text_toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4))
        text_toolbar.columnconfigure(0, weight=1)

        self.mark_button = ttk.Button(
            text_toolbar,
            text="Mark",
            command=self.toggle_selection_mark,
        )
        self.mark_button.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self.mark_button.grid_remove()

        edit_button = ttk.Button(
            text_toolbar,
            textvariable=self.edit_button_text,
            command=self.toggle_edit_mode,
        )
        edit_button.grid(row=0, column=2, sticky="e")

        self.text_box = tk.Text(text_frame, wrap="word", undo=True, font=("Arial", 12))
        self.text_box.grid(row=1, column=0, sticky="nsew")
        self.text_box.tag_configure("highlight", background="#fff59d")

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
            title="Choose text or PDF files",
            filetypes=(
                ("Text and PDF files", "*.txt *.pdf"),
                ("Text files", "*.txt"),
                ("PDF files", "*.pdf"),
            ),
        )
        if selected_files:
            self.import_files([Path(file_path) for file_path in selected_files])

    def import_files(self, paths: list[Path]) -> None:
        imported_count = 0
        errors: list[str] = []

        for path in paths:
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                errors.append(f"{path.name}: File type is not supported.")
                continue

            try:
                content = self.extract_content(path)
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
                continue

            self.append_document(path, content)
            imported_count += 1

        if imported_count:
            self.status.set(f"Successfully inserted {imported_count} file(s).")
        if errors:
            messagebox.showwarning("Import notes", "\n".join(errors))
            self.status.set("Some files could not be imported.")

    def extract_content(self, path: Path) -> list[DocumentPart]:
        if path.suffix.lower() == ".txt":
            return [DocumentPart("text", self.extract_txt(path))]
        return self.extract_pdf(path)

    @staticmethod
    def extract_txt(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1")

    @staticmethod
    def extract_pdf(path: Path) -> list[DocumentPart]:
        reader = PdfReader(path)
        parts: list[DocumentPart] = []
        for index, page in enumerate(reader.pages, start=1):
            page_text = (page.extract_text() or "").strip()
            parts.append(DocumentPart("text", f"--- Page {index} ---\n{page_text}"))
            for image in page.images:
                parts.append(DocumentPart("image", image.data))
        return parts

    def toggle_edit_mode(self) -> None:
        is_editing = not self.is_editing.get()
        self.is_editing.set(is_editing)
        self.edit_button_text.set("DONE" if is_editing else "EDIT")
        self.text_box.configure(state="normal" if is_editing else "disabled")
        if is_editing:
            self.mark_button.grid()
            self.text_box.focus_set()
            self.status.set("Edit mode is active: you can edit text or select text and click Mark.")
        else:
            self.mark_button.grid_remove()
            self.status.set("View mode is active: the text is protected from changes.")

    def toggle_selection_mark(self) -> None:
        try:
            start = self.text_box.index("sel.first")
            end = self.text_box.index("sel.last")
        except tk.TclError:
            self.status.set("Select text first, then click Mark.")
            return

        tag_ranges = self.text_box.tag_ranges("highlight")
        is_marked = any(
            self.text_box.compare(start, ">=", tag_start) and self.text_box.compare(end, "<=", tag_end)
            for tag_start, tag_end in zip(tag_ranges[0::2], tag_ranges[1::2])
        )
        if is_marked:
            self.text_box.tag_remove("highlight", start, end)
            self.status.set("Mark removed from the selected text.")
        else:
            self.text_box.tag_add("highlight", start, end)
            self.status.set("Selected text was marked.")

    def append_document(self, path: Path, content: list[DocumentPart]) -> None:
        was_editing = self.is_editing.get()
        self.text_box.configure(state="normal")
        separator = "\n\n" if self.text_box.get("1.0", "end-1c") else ""
        self.text_box.insert("end", f"{separator}===== {path.name} =====\n")
        for part in content:
            if part.kind == "text":
                self.text_box.insert("end", f"{part.content}\n\n")
            elif part.kind == "image":
                self.insert_pdf_image(part.content)
        self.text_box.see("end")
        if not was_editing:
            self.text_box.configure(state="disabled")

    def insert_pdf_image(self, image_data: str | bytes) -> None:
        if not isinstance(image_data, bytes):
            return
        try:
            image = Image.open(BytesIO(image_data))
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA")
            if image.width > MAX_PDF_IMAGE_WIDTH:
                ratio = MAX_PDF_IMAGE_WIDTH / image.width
                image = image.resize((MAX_PDF_IMAGE_WIDTH, max(1, int(image.height * ratio))))
            photo = ImageTk.PhotoImage(image)
        except Exception:
            self.text_box.insert("end", "[PDF image could not be displayed]\n\n")
            return

        self.pdf_images.append(photo)
        self.text_box.image_create("end", image=photo)
        self.text_box.insert("end", "\n\n")


def main() -> None:
    root = TkinterDnD.Tk()
    FastReadingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
