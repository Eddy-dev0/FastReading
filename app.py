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
RSVP_TEXT = """Rapid Serial Visual Presentation, kurz RSVP, ist eine coole Technik, um Informationen schnell – Element für Element – an derselben Stelle auf dem Bildschirm anzuzeigen. Anstatt einen ganzen Absatz in Ihrem eigenen Tempo zu lesen, huschen Wörter (oder Bilder) schnell vorbei, meist im Zentrum Ihres Blickfelds. Es ähnelt Schnelllesen: Der Inhalt bewegt sich, nicht Ihre Augen. Das erleichtert die Informationsverarbeitung, ohne dass Sie scrollen oder Ihren Blick bewegen müssen.

RSVP wird in psychologischen Experimenten zur Untersuchung von Aufmerksamkeit und Wahrnehmung eingesetzt, hat aber auch Eingang in Apps gefunden, die Ihnen helfen, schneller zu lesen oder Ihre Konzentration zu verbessern. Interessant an RSVP ist, dass es Forschern hilft zu verstehen, wie unser Gehirn mit sich schnell ändernden Informationen umgeht – zum Beispiel, wie lange es braucht, um etwas Wichtiges zu bemerken, oder wann wir Dinge „übersehen“, obwohl wir sie gesehen haben.

Vielleicht haben Sie auch schon vom „Aufmerksamkeitsblinzeln“ bei RSVP gehört, einem kurzen Moment, in dem Ihr Gehirn sozusagen abschaltet und etwas übersieht, kurz nachdem es etwas anderes bemerkt hat. Es ist ein seltsamer, aber faszinierender Einblick in unsere Aufmerksamkeit. Insgesamt ist RSVP eine schnelle und unterhaltsame Möglichkeit, mehr über die Funktionsweise unseres Gehirns zu erfahren! Ich hoffe, euch gefällt das Video!"""
RSVP_WPM_PRESETS = [100, 150, 200, 250, 300, 350, 400, 600]
DEFAULT_RSVP_WPM = 300
RSVP_PIVOT_OFFSET_PX = -4


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
        self.selected_highlight_color = tk.StringVar(value="Yellow")
        self.highlight_tags = {
            "Yellow": ("highlight_yellow", "#fff59d"),
            "Green": ("highlight_green", "#c8e6c9"),
            "Blue": ("highlight_blue", "#bbdefb"),
            "Pink": ("highlight_pink", "#f8bbd0"),
            "Orange": ("highlight_orange", "#ffe0b2"),
        }
        self.pdf_images: list[ImageTk.PhotoImage] = []
        self._build_layout()
        self._register_drop_target()

    def _build_layout(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        main_frame = ttk.Frame(notebook, padding=0)
        rsvp_tab = tk.Frame(notebook, bg="black")
        notebook.add(main_frame, text="FastReading Import")
        notebook.add(rsvp_tab, text="RSVP")

        self.rsvp_words = RSVP_TEXT.split()
        self.rsvp_word_index = 0
        self.rsvp_after_id: str | None = None
        self.rsvp_wpm = tk.IntVar(value=DEFAULT_RSVP_WPM)
        self.rsvp_wpm_picker: tk.Toplevel | None = None
        self.build_rsvp_tab(rsvp_tab)

        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        self.drop_frame = ttk.LabelFrame(main_frame, text="Drag & Drop")
        self.drop_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
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
        text_frame.grid(row=1, column=0, sticky="nsew")
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

        self.color_picker = ttk.Combobox(
            text_toolbar,
            textvariable=self.selected_highlight_color,
            values=list(self.highlight_tags),
            state="readonly",
            width=10,
        )
        self.color_picker.grid(row=0, column=2, sticky="e", padx=(0, 8))
        self.color_picker.grid_remove()

        edit_button = ttk.Button(
            text_toolbar,
            textvariable=self.edit_button_text,
            command=self.toggle_edit_mode,
        )
        edit_button.grid(row=0, column=3, sticky="e")

        self.text_box = tk.Text(text_frame, wrap="word", undo=True, font=("Arial", 12))
        self.text_box.grid(row=1, column=0, sticky="nsew")
        for tag_name, color in self.highlight_tags.values():
            self.text_box.tag_configure(tag_name, background=color)

        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.text_box.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.text_box.configure(state="disabled", yscrollcommand=scrollbar.set)

        status_label = ttk.Label(main_frame, textvariable=self.status, anchor="w")
        status_label.grid(row=2, column=0, sticky="ew", pady=(8, 0))

    def build_rsvp_tab(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        self.rsvp_canvas = tk.Canvas(parent, bg="black", highlightthickness=0, bd=0)
        self.rsvp_canvas.grid(row=0, column=0, sticky="nsew")
        self.rsvp_canvas.bind("<Configure>", self.draw_rsvp_view)

        control_bar = tk.Frame(parent, bg="black")
        control_bar.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 16))
        control_bar.columnconfigure(0, weight=1)

        self.root.bind("<space>", self.handle_rsvp_space)
        self.root.bind("<Left>", lambda event: self.change_rsvp_wpm(-50))
        self.root.bind("<Right>", lambda event: self.change_rsvp_wpm(50))
        self.root.bind("<Down>", lambda event: self.change_rsvp_wpm(-50))
        self.root.bind("<Up>", lambda event: self.change_rsvp_wpm(50))

        self.rsvp_wpm_label = tk.Label(
            control_bar,
            text=f"{self.rsvp_wpm.get()} wpm",
            bg="black",
            fg="#3a3a3a",
            font=("Arial", 24, "italic"),
        )
        self.rsvp_wpm_label.grid(row=0, column=1, sticky="e", padx=(0, 32))
        self.rsvp_wpm_label.bind("<Button-1>", self.open_rsvp_wpm_picker)
        self.rsvp_wpm_label.configure(cursor="hand2")

        self.start_rsvp_playback()

    def draw_rsvp_view(self, event: tk.Event | None = None) -> None:
        canvas = self.rsvp_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 1)
        height = max(canvas.winfo_height(), 1)
        center_x = (width / 2) + RSVP_PIVOT_OFFSET_PX
        center_y = height / 2

        line_color = "#161616"
        canvas.create_line(0, center_y - 92, width, center_y - 92, fill=line_color, width=5)
        canvas.create_line(0, center_y + 92, width, center_y + 92, fill=line_color, width=5)
        canvas.create_line(center_x, center_y - 92, center_x, center_y - 30, fill=line_color, width=5)
        canvas.create_line(center_x, center_y + 30, center_x, center_y + 92, fill=line_color, width=5)

        if not self.rsvp_words:
            return
        word = self.rsvp_words[self.rsvp_word_index % len(self.rsvp_words)]
        pivot = self.get_rsvp_pivot_index(word)
        before = word[:pivot]
        pivot_char = word[pivot : pivot + 1]
        after = word[pivot + 1 :]

        font = ("Times New Roman", 58)
        canvas.create_text(center_x, center_y, text=before, fill="white", font=font, anchor="e")
        pivot_item = canvas.create_text(center_x, center_y, text=pivot_char, fill="#ff3045", font=font, anchor="w")
        pivot_bbox = canvas.bbox(pivot_item)
        after_x = pivot_bbox[2] if pivot_bbox else center_x
        canvas.create_text(after_x, center_y, text=after, fill="white", font=font, anchor="w")

    @staticmethod
    def get_rsvp_pivot_index(word: str) -> int:
        letters = [index for index, character in enumerate(word) if character.isalpha()]
        if not letters:
            return 0
        return letters[min(len(letters) // 3, len(letters) - 1)]

    def start_rsvp_playback(self) -> None:
        if self.rsvp_after_id is None:
            self.rsvp_after_id = self.root.after(self.get_rsvp_interval_ms(), self.advance_rsvp_word)

    def stop_rsvp_playback(self) -> None:
        if self.rsvp_after_id is not None:
            self.root.after_cancel(self.rsvp_after_id)
            self.rsvp_after_id = None

    def handle_rsvp_space(self, event: tk.Event) -> str:
        self.toggle_rsvp_playback()
        return "break"

    def get_rsvp_interval_ms(self) -> int:
        return int(60_000 / max(self.rsvp_wpm.get(), 1))

    def change_rsvp_wpm(self, amount: int) -> str:
        self.set_rsvp_wpm(self.rsvp_wpm.get() + amount)
        return "break"

    def set_rsvp_wpm(self, value: int) -> None:
        minimum = RSVP_WPM_PRESETS[0]
        maximum = RSVP_WPM_PRESETS[-1]
        new_value = max(minimum, min(maximum, value))
        self.rsvp_wpm.set(new_value)
        self.rsvp_wpm_label.configure(text=f"{new_value} wpm")
        if self.rsvp_after_id is not None:
            self.stop_rsvp_playback()
            self.start_rsvp_playback()

    def open_rsvp_wpm_picker(self, event: tk.Event | None = None) -> None:
        if self.rsvp_wpm_picker is not None and self.rsvp_wpm_picker.winfo_exists():
            self.rsvp_wpm_picker.lift()
            return

        picker = tk.Toplevel(self.root)
        self.rsvp_wpm_picker = picker
        picker.title("WPM")
        picker.configure(bg="white")
        picker.resizable(False, False)
        picker.transient(self.root)

        x = self.rsvp_wpm_label.winfo_rootx()
        y = self.rsvp_wpm_label.winfo_rooty() - 220
        picker.geometry(f"180x560+{x}+{max(y, 0)}")

        arrow_row = tk.Frame(picker, bg="white", highlightbackground="black", highlightthickness=4)
        arrow_row.pack(fill="x")
        up_button = tk.Button(arrow_row, text="△", font=("Arial", 28), bg="white", bd=0, command=lambda: self.change_rsvp_wpm(50))
        down_button = tk.Button(arrow_row, text="▽", font=("Arial", 28), bg="white", bd=0, command=lambda: self.change_rsvp_wpm(-50))
        up_button.pack(side="left", expand=True, fill="x")
        down_button.pack(side="left", expand=True, fill="x")

        for preset in sorted(RSVP_WPM_PRESETS, reverse=True):
            preset_button = tk.Button(
                picker,
                text=str(preset),
                font=("Arial", 34),
                bg="white",
                activebackground="#eeeeee",
                bd=0,
                highlightbackground="black",
                highlightthickness=3,
                command=lambda selected=preset: self.choose_rsvp_wpm(selected),
            )
            preset_button.pack(fill="x", ipady=6)

        picker.bind("<Up>", lambda key_event: self.change_rsvp_wpm(50))
        picker.bind("<Right>", lambda key_event: self.change_rsvp_wpm(50))
        picker.bind("<Down>", lambda key_event: self.change_rsvp_wpm(-50))
        picker.bind("<Left>", lambda key_event: self.change_rsvp_wpm(-50))
        picker.bind("<Escape>", lambda key_event: picker.destroy())
        picker.protocol("WM_DELETE_WINDOW", picker.destroy)

    def choose_rsvp_wpm(self, value: int) -> None:
        self.set_rsvp_wpm(value)
        if self.rsvp_wpm_picker is not None and self.rsvp_wpm_picker.winfo_exists():
            self.rsvp_wpm_picker.destroy()

    def toggle_rsvp_playback(self) -> None:
        if self.rsvp_after_id is None:
            self.start_rsvp_playback()
        else:
            self.stop_rsvp_playback()

    def advance_rsvp_word(self) -> None:
        self.rsvp_after_id = None
        self.rsvp_word_index = (self.rsvp_word_index + 1) % max(len(self.rsvp_words), 1)
        self.draw_rsvp_view()
        self.start_rsvp_playback()

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
            self.color_picker.grid()
            self.text_box.focus_set()
            self.status.set("Edit mode is active: you can edit text or select text, choose a color, and click Mark.")
        else:
            self.mark_button.grid_remove()
            self.color_picker.grid_remove()
            self.status.set("View mode is active: the text is protected from changes.")

    def toggle_selection_mark(self) -> None:
        try:
            start = self.text_box.index("sel.first")
            end = self.text_box.index("sel.last")
        except tk.TclError:
            self.status.set("Select text first, then click Mark.")
            return

        start, end = self.get_trimmed_selection_range(start, end)
        if start is None or end is None:
            self.status.set("Select visible text first, then click Mark.")
            return

        selected_tag, _ = self.highlight_tags[self.selected_highlight_color.get()]
        active_highlight_tag = self.get_highlight_tag_in_range(start, end)
        if active_highlight_tag:
            self.text_box.tag_remove(active_highlight_tag, start, end)
            self.status.set("Mark removed from the selected text.")
        else:
            self.add_letter_only_highlight(selected_tag, start, end)
            self.status.set(f"Only letters were marked in {self.selected_highlight_color.get().lower()}.")

    def add_letter_only_highlight(self, tag_name: str, start: str, end: str) -> None:
        selected_text = self.text_box.get(start, end)
        segment_start: str | None = None
        current_index = start

        for character in selected_text:
            next_index = self.text_box.index(f"{current_index}+1c")
            if character.isalpha():
                if segment_start is None:
                    segment_start = current_index
            elif segment_start is not None:
                self.text_box.tag_add(tag_name, segment_start, current_index)
                segment_start = None
            current_index = next_index

        if segment_start is not None:
            self.text_box.tag_add(tag_name, segment_start, current_index)

    def get_trimmed_selection_range(self, start: str, end: str) -> tuple[str | None, str | None]:
        selected_text = self.text_box.get(start, end)
        leading_whitespace = len(selected_text) - len(selected_text.lstrip())
        trailing_whitespace = len(selected_text) - len(selected_text.rstrip())
        if leading_whitespace == len(selected_text):
            return None, None

        trimmed_start = self.text_box.index(f"{start}+{leading_whitespace}c")
        trimmed_end = self.text_box.index(f"{end}-{trailing_whitespace}c")
        if not self.text_box.compare(trimmed_start, "<", trimmed_end):
            return None, None
        return trimmed_start, trimmed_end

    def get_highlight_tag_in_range(self, start: str, end: str) -> str | None:
        for tag_name, _ in self.highlight_tags.values():
            tag_ranges = self.text_box.tag_ranges(tag_name)
            for tag_start, tag_end in zip(tag_ranges[0::2], tag_ranges[1::2]):
                if self.text_box.compare(tag_start, "<", end) and self.text_box.compare(tag_end, ">", start):
                    return tag_name
        return None

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
