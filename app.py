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
RSVP_TEXT = """Import text in the FastReading Import tab to read it here with RSVP."""
RSVP_WPM_PRESETS = list(range(100, 1001, 50))
DEFAULT_RSVP_WPM = 300
RSVP_GUIDE_OFFSET_X_PX = 0
RSVP_WORD_OFFSET_X_PX = -20
RSVP_WORD_OFFSET_Y_PX = 0
RSVP_BASE_FONT_SIZE = 58
RSVP_BASE_GUIDE_HALF_GAP_PX = 30
RSVP_BASE_GUIDE_HALF_HEIGHT_PX = 92


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
        self.is_rsvp_fullscreen = False
        self.rsvp_fullscreen_frame: tk.Frame | None = None
        self.rsvp_windowed_widgets: tuple[tk.Canvas, tk.Label, tk.Scale] | None = None
        self.rsvp_fullscreen_visual_offset_y: float | None = None

        notebook = ttk.Notebook(self.root)
        self.notebook = notebook
        notebook.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        main_frame = ttk.Frame(notebook, padding=0)
        rsvp_tab = tk.Frame(notebook, bg="black")
        notebook.add(main_frame, text="FastReading Import")
        notebook.add(rsvp_tab, text="RSVP")

        self.rsvp_words = RSVP_TEXT.split()
        self.rsvp_word_index = 0
        self.rsvp_after_id: str | None = None
        self.rsvp_is_paused = tk.BooleanVar(value=False)
        self.rsvp_wpm = tk.IntVar(value=DEFAULT_RSVP_WPM)
        self.rsvp_progress = tk.IntVar(value=0)
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
        self.root.bind("<Left>", lambda event: self.change_rsvp_wpm(-25))
        self.root.bind("<Right>", lambda event: self.change_rsvp_wpm(25))
        self.root.bind("<Down>", lambda event: self.change_rsvp_wpm(-25))
        self.root.bind("<Up>", lambda event: self.change_rsvp_wpm(25))
        self.root.bind("<f>", self.toggle_rsvp_fullscreen)
        self.root.bind("<F>", self.toggle_rsvp_fullscreen)
        self.root.bind("<Escape>", self.exit_rsvp_fullscreen)

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

        self.rsvp_progress_bar = tk.Scale(
            parent,
            from_=0,
            to=max(len(self.rsvp_words) - 1, 0),
            orient="horizontal",
            variable=self.rsvp_progress,
            command=self.seek_rsvp_word,
            showvalue=False,
            bg="black",
            fg="#88E788",
            troughcolor="black",
            activebackground="#88E788",
            highlightthickness=0,
            bd=0,
            sliderlength=72,
            width=24,
            relief="flat",
        )
        self.rsvp_progress_bar.grid(row=2, column=0, sticky="ew", padx=38, pady=(0, 22))
        self.rsvp_progress_bar.grid_remove()

        self.start_rsvp_playback()


    def toggle_rsvp_fullscreen(self, event: tk.Event | None = None) -> str:
        if self.is_rsvp_fullscreen:
            return self.exit_rsvp_fullscreen(event)
        return self.enter_rsvp_fullscreen()

    def enter_rsvp_fullscreen(self) -> str:
        if self.is_rsvp_fullscreen:
            return "break"

        self.rsvp_fullscreen_visual_offset_y = self.get_rsvp_windowed_visual_offset_y()
        self.rsvp_windowed_widgets = (self.rsvp_canvas, self.rsvp_wpm_label, self.rsvp_progress_bar)
        self.notebook.pack_forget()
        self.root.attributes("-fullscreen", True)

        fullscreen_frame = tk.Frame(self.root, bg="black")
        fullscreen_frame.pack(fill=tk.BOTH, expand=True)
        self.rsvp_fullscreen_frame = fullscreen_frame

        self.rsvp_canvas = tk.Canvas(fullscreen_frame, bg="black", highlightthickness=0, bd=0)
        self.rsvp_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.rsvp_canvas.bind("<Configure>", self.draw_rsvp_view)

        fullscreen_controls = tk.Frame(fullscreen_frame, bg="black")
        fullscreen_controls.place(relx=1, rely=1, anchor="se", x=-56, y=-46)
        self.rsvp_wpm_label = tk.Label(
            fullscreen_controls,
            text=f"{self.rsvp_wpm.get()} wpm",
            bg="black",
            fg="#3a3a3a",
            font=("Arial", 24, "italic"),
        )
        self.rsvp_wpm_label.grid(row=0, column=1, sticky="e", padx=(0, 32))
        self.rsvp_wpm_label.bind("<Button-1>", self.open_rsvp_wpm_picker)
        self.rsvp_wpm_label.configure(cursor="hand2")

        self.rsvp_progress_bar = tk.Scale(
            fullscreen_frame,
            from_=0,
            to=max(len(self.rsvp_words) - 1, 0),
            orient="horizontal",
            variable=self.rsvp_progress,
            command=self.seek_rsvp_word,
            showvalue=False,
            bg="black",
            fg="#88E788",
            troughcolor="black",
            activebackground="#88E788",
            highlightthickness=0,
            bd=0,
            sliderlength=72,
            width=24,
            relief="flat",
        )
        if self.rsvp_is_paused.get():
            self.rsvp_progress_bar.place(relx=0.5, rely=1, anchor="s", relwidth=1, width=-76, y=-22)

        self.is_rsvp_fullscreen = True
        self.draw_rsvp_view()
        return "break"

    def exit_rsvp_fullscreen(self, event: tk.Event | None = None) -> str:
        if not self.is_rsvp_fullscreen:
            return "break"

        if self.rsvp_fullscreen_frame is not None:
            self.rsvp_fullscreen_frame.destroy()
            self.rsvp_fullscreen_frame = None
        if self.rsvp_windowed_widgets is not None:
            self.rsvp_canvas, self.rsvp_wpm_label, self.rsvp_progress_bar = self.rsvp_windowed_widgets
            self.rsvp_windowed_widgets = None

        self.rsvp_fullscreen_visual_offset_y = None
        self.root.attributes("-fullscreen", False)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        if self.rsvp_is_paused.get():
            self.rsvp_progress_bar.grid()
        else:
            self.rsvp_progress_bar.grid_remove()
        self.is_rsvp_fullscreen = False
        self.draw_rsvp_view()
        return "break"

    def draw_rsvp_view(self, event: tk.Event | None = None) -> None:
        canvas = self.rsvp_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 1)
        height = max(canvas.winfo_height(), 1)
        scale = max(1.0, min(width / 640, height / 360))
        guide_x = (width / 2) + RSVP_GUIDE_OFFSET_X_PX
        guide_y = self.get_rsvp_visual_center_y(height) + self.get_rsvp_visual_offset_y()
        word_x = guide_x + RSVP_WORD_OFFSET_X_PX
        word_y = guide_y + RSVP_WORD_OFFSET_Y_PX
        guide_half_gap = RSVP_BASE_GUIDE_HALF_GAP_PX * scale
        guide_half_height = RSVP_BASE_GUIDE_HALF_HEIGHT_PX * scale
        guide_width = max(5, round(5 * scale))

        line_color = "#161616"
        canvas.create_line(0, guide_y - guide_half_height, width, guide_y - guide_half_height, fill=line_color, width=guide_width)
        canvas.create_line(0, guide_y + guide_half_height, width, guide_y + guide_half_height, fill=line_color, width=guide_width)
        canvas.create_line(guide_x, guide_y - guide_half_height, guide_x, guide_y - guide_half_gap, fill=line_color, width=guide_width)
        canvas.create_line(guide_x, guide_y + guide_half_gap, guide_x, guide_y + guide_half_height, fill=line_color, width=guide_width)

        if not self.rsvp_words:
            return
        word = self.rsvp_words[self.rsvp_word_index % len(self.rsvp_words)]
        pivot = self.get_rsvp_pivot_index(word)
        before = word[:pivot]
        pivot_char = word[pivot : pivot + 1]
        after = word[pivot + 1 :]

        font = ("Times New Roman", round(RSVP_BASE_FONT_SIZE * scale))
        canvas.create_text(word_x, word_y, text=before, fill="white", font=font, anchor="e")
        pivot_item = canvas.create_text(word_x, word_y, text=pivot_char, fill="#ff3045", font=font, anchor="w")
        pivot_bbox = canvas.bbox(pivot_item)
        after_x = pivot_bbox[2] if pivot_bbox else word_x
        canvas.create_text(after_x, word_y, text=after, fill="white", font=font, anchor="w")

    def get_rsvp_visual_offset_y(self) -> float:
        if self.is_rsvp_fullscreen and self.rsvp_fullscreen_visual_offset_y is not None:
            return self.rsvp_fullscreen_visual_offset_y
        return 0.0

    def get_rsvp_windowed_visual_offset_y(self) -> float:
        self.root.update_idletasks()
        canvas_center_y = self.rsvp_canvas.winfo_rooty() + self.get_rsvp_visual_center_y(self.rsvp_canvas.winfo_height())
        root_center_y = self.root.winfo_rooty() + (self.root.winfo_height() / 2)
        return canvas_center_y - root_center_y

    @staticmethod
    def get_rsvp_visual_center_y(canvas_height: int) -> float:
        return canvas_height / 2

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
        picker.configure(bg="black")
        picker.resizable(False, False)
        picker.transient(self.root)
        picker.overrideredirect(True)

        width = 150
        item_height = 44
        height = item_height * len(RSVP_WPM_PRESETS)
        x = self.rsvp_wpm_label.winfo_rootx() + self.rsvp_wpm_label.winfo_width() - width
        y = self.rsvp_wpm_label.winfo_rooty() - height - 10
        picker.geometry(f"{width}x{height}+{x}+{max(y, 0)}")

        for preset in sorted(RSVP_WPM_PRESETS, reverse=True):
            preset_button = tk.Button(
                picker,
                text=f"{preset} wpm",
                font=("Arial", 24, "italic"),
                fg="#4a4a4a" if preset != self.rsvp_wpm.get() else "white",
                bg="black",
                activeforeground="white",
                activebackground="#151515",
                bd=0,
                highlightthickness=0,
                relief="flat",
                command=lambda selected=preset: self.choose_rsvp_wpm(selected),
            )
            preset_button.pack(fill="x", ipady=2)

        picker.bind("<Up>", lambda key_event: self.change_rsvp_wpm(25))
        picker.bind("<Right>", lambda key_event: self.change_rsvp_wpm(25))
        picker.bind("<Down>", lambda key_event: self.change_rsvp_wpm(-25))
        picker.bind("<Left>", lambda key_event: self.change_rsvp_wpm(-25))
        picker.bind("<Escape>", lambda key_event: picker.destroy())
        picker.protocol("WM_DELETE_WINDOW", picker.destroy)

    def choose_rsvp_wpm(self, value: int) -> None:
        self.set_rsvp_wpm(value)
        if self.rsvp_wpm_picker is not None and self.rsvp_wpm_picker.winfo_exists():
            self.rsvp_wpm_picker.destroy()

    def toggle_rsvp_playback(self) -> None:
        if self.rsvp_after_id is None:
            self.rsvp_is_paused.set(False)
            self.hide_rsvp_progress_bar()
            self.start_rsvp_playback()
        else:
            self.stop_rsvp_playback()
            self.rsvp_is_paused.set(True)
            self.show_rsvp_progress_bar()

    def show_rsvp_progress_bar(self) -> None:
        self.rsvp_progress_bar.configure(to=max(len(self.rsvp_words) - 1, 0))
        self.rsvp_progress.set(self.rsvp_word_index)
        if self.is_rsvp_fullscreen:
            self.rsvp_progress_bar.place(relx=0.5, rely=1, anchor="s", relwidth=1, width=-76, y=-22)
        else:
            self.rsvp_progress_bar.grid()

    def hide_rsvp_progress_bar(self) -> None:
        if self.is_rsvp_fullscreen:
            self.rsvp_progress_bar.place_forget()
        else:
            self.rsvp_progress_bar.grid_remove()

    def seek_rsvp_word(self, value: str) -> None:
        if not self.rsvp_is_paused.get():
            return
        self.rsvp_word_index = int(float(value))
        self.draw_rsvp_view()

    def advance_rsvp_word(self) -> None:
        self.rsvp_after_id = None
        self.rsvp_word_index = (self.rsvp_word_index + 1) % max(len(self.rsvp_words), 1)
        self.rsvp_progress.set(self.rsvp_word_index)
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
            self.refresh_rsvp_words_from_import()
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

    def refresh_rsvp_words_from_import(self) -> None:
        imported_text = self.text_box.get("1.0", "end-1c").strip()
        self.rsvp_words = imported_text.split() or RSVP_TEXT.split()
        self.rsvp_word_index = min(self.rsvp_word_index, max(len(self.rsvp_words) - 1, 0))
        self.rsvp_progress_bar.configure(to=max(len(self.rsvp_words) - 1, 0))
        self.rsvp_progress.set(self.rsvp_word_index)
        self.draw_rsvp_view()

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
