"""Tkinter application for importing text and PDF files into a reading buffer."""

from dataclasses import dataclass
import random
from io import BytesIO
from pathlib import Path
import re
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

from PIL import Image, ImageTk
from pypdf import PdfReader
from tkinterdnd2 import DND_FILES, TkinterDnD

SUPPORTED_EXTENSIONS = {".txt", ".pdf"}
MAX_PDF_IMAGE_WIDTH = 760
RSVP_TEXT = """Import text in the FastReading Import tab to read it here with RSVP."""
RSVP_WPM_PRESETS = list(range(100, 1001, 50))
DEFAULT_RSVP_WPM = 300
RSVP_GUIDE_OFFSET_X_PX = 0
RSVP_WORD_OFFSET_X_PX = 0
RSVP_WORD_OFFSET_Y_PX = 0
RSVP_BASE_FONT_SIZE = 58
RSVP_BASE_GUIDE_HALF_GAP_PX = 30
RSVP_BASE_GUIDE_HALF_HEIGHT_PX = 92
RSVP_SENTENCE_PAUSE_DURATIONS_MS = {
    "1 second": 1_000,
    "2 seconds": 2_000,
    "5 seconds": 5_000,
    "10 seconds": 10_000,
}
RSVP_MANUAL_SENTENCE_PAUSE = "Until Space is pressed"
RSVP_IMAGE_PAUSE_DURATIONS_MS = {
    "1 second": 1_000,
    "5 seconds": 5_000,
    "10 seconds": 10_000,
}
RSVP_MANUAL_IMAGE_PAUSE = "Until Space is pressed"
RSVP_IMAGE_TOKEN = "[IMAGE]"
DEFAULT_LONG_WORD_MIN_LENGTH = 8
DEFAULT_LONG_WORD_WPM_PERCENT = 100
MIN_LONG_WORD_WPM_PERCENT = 25
MAX_LONG_WORD_WPM_PERCENT = 100

@dataclass
class Question:
    """Multiple-choice question embedded in the imported text."""

    prompt: str
    answers: list[str]
    correct_index: int
    reveal_word_index: int


@dataclass
class DocumentPart:
    """A text or image fragment extracted from an imported document."""

    kind: str
    content: str | bytes | ImageTk.PhotoImage


class FastReadingApp:
    """Small desktop UI that accepts .txt and .pdf files via drag and drop."""

    def __init__(self, root: TkinterDnD.Tk) -> None:
        self.root = root
        self.root.title("FastReading")
        self.root.geometry("1100x760")
        self.root.minsize(900, 620)

        self.ui_font = tkfont.Font(family="Arial", size=12)
        self.ui_bold_font = tkfont.Font(family="Arial", size=12, weight="bold")
        self.ui_heading_font = tkfont.Font(family="Arial", size=18, weight="bold")
        self.ui_text_font = tkfont.Font(family="Arial", size=13)
        self.ui_wrap_labels: list[tk.Label | ttk.Label] = []

        self.status = tk.StringVar(value="Drop .txt or .pdf files into the field, or choose files manually.")
        self.is_editing = tk.BooleanVar(value=False)
        self.edit_button_text = tk.StringVar(value="EDIT")
        self.selected_highlight_color = tk.StringVar(value="Yellow")
        self.rsvp_sentence_pause_mode = tk.StringVar(value=RSVP_MANUAL_SENTENCE_PAUSE)
        self.rsvp_image_pause_mode = tk.StringVar(value="5 seconds")
        self.rsvp_wpm = tk.IntVar(value=DEFAULT_RSVP_WPM)
        self.rsvp_long_word_min_length = tk.IntVar(value=DEFAULT_LONG_WORD_MIN_LENGTH)
        self.rsvp_long_word_wpm_percent = tk.IntVar(value=DEFAULT_LONG_WORD_WPM_PERCENT)
        self.rsvp_long_word_wpm_label = tk.StringVar(value=self.format_long_word_wpm_label())
        self.question_mode = tk.StringVar(value="Chronological")
        self.questions: list[Question] = []
        self.current_question: Question | None = None
        self.current_question_index = 0
        self.current_question_choices: list[tk.IntVar] = []
        self.rsvp_sentence_pause_flags: list[bool] = []
        self.rsvp_image_tokens: list[ImageTk.PhotoImage | None] = []
        self.rsvp_source_parts: list[DocumentPart] = []
        self.rsvp_is_sentence_pause = False
        self.rsvp_is_image_pause = False
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
        self.root.bind("<Configure>", self.update_responsive_layout, add="+")
        self.update_responsive_layout()

    def _build_layout(self) -> None:
        self.is_rsvp_fullscreen = False
        self.rsvp_fullscreen_frame: tk.Frame | None = None
        self.rsvp_windowed_widgets: tuple[tk.Canvas, tk.Label, tk.Scale] | None = None
        self.rsvp_fullscreen_visual_offset: tuple[float, float] | None = None

        notebook = ttk.Notebook(self.root)
        self.notebook = notebook
        notebook.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

        style = ttk.Style(self.root)
        style.configure(".", font=self.ui_font)
        style.configure("TButton", padding=(14, 8))
        style.configure("TCheckbutton", font=self.ui_font)
        style.configure("TRadiobutton", font=self.ui_font)
        style.configure("TLabelframe.Label", font=self.ui_bold_font)

        main_frame = ttk.Frame(notebook, padding=0)
        rsvp_tab = tk.Frame(notebook, bg="black")
        questions_tab = ttk.Frame(notebook, padding=24)
        settings_tab = ttk.Frame(notebook, padding=28)
        notebook.add(main_frame, text="FastReading Import")
        notebook.add(rsvp_tab, text="RSVP")
        notebook.add(questions_tab, text="Questions")
        notebook.add(settings_tab, text="Settings")

        self.rsvp_words, self.rsvp_sentence_pause_flags = self.build_rsvp_tokens(RSVP_TEXT)
        self.rsvp_image_tokens = [None] * len(self.rsvp_words)
        self.rsvp_word_index = 0
        self.rsvp_after_id: str | None = None
        self.rsvp_is_paused = tk.BooleanVar(value=True)
        self.rsvp_progress = tk.IntVar(value=0)
        self.rsvp_wpm_picker: tk.Toplevel | None = None
        self.build_rsvp_tab(rsvp_tab)
        self.build_questions_tab(questions_tab)
        self.build_settings_tab(settings_tab)
        notebook.bind("<<NotebookTabChanged>>", self.handle_tab_changed)

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
            font=self.ui_font,
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

        self.text_box = tk.Text(text_frame, wrap="word", undo=True, font=self.ui_text_font)
        self.text_box.grid(row=1, column=0, sticky="nsew")
        for tag_name, color in self.highlight_tags.values():
            self.text_box.tag_configure(tag_name, background=color)

        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.text_box.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.text_box.configure(state="disabled", yscrollcommand=scrollbar.set)
        self.text_box.bind("<<Modified>>", self.handle_text_modified)

        status_label = ttk.Label(main_frame, textvariable=self.status, anchor="w")
        status_label.grid(row=2, column=0, sticky="ew", pady=(8, 0))

    def update_responsive_layout(self, event: tk.Event | None = None) -> None:
        """Scale the UI up with the current window size instead of staying tiny."""
        width = max(self.root.winfo_width(), self.root.winfo_reqwidth(), 1)
        height = max(self.root.winfo_height(), self.root.winfo_reqheight(), 1)
        scale = max(1.0, min(width / 1100, height / 760))
        base_size = round(12 * scale)

        self.ui_font.configure(size=base_size)
        self.ui_bold_font.configure(size=base_size, weight="bold")
        self.ui_heading_font.configure(size=round(18 * scale), weight="bold")
        self.ui_text_font.configure(size=round(13 * scale))

        style = ttk.Style(self.root)
        style.configure(".", font=self.ui_font)
        style.configure("TButton", padding=(round(14 * scale), round(8 * scale)))
        style.configure("TCheckbutton", font=self.ui_font)
        style.configure("TRadiobutton", font=self.ui_font)
        style.configure("TLabelframe.Label", font=self.ui_bold_font)

        wraplength = max(360, width - round(150 * scale))
        for label in self.ui_wrap_labels:
            if label.winfo_exists():
                label.configure(wraplength=wraplength)

    def build_questions_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(parent)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        toolbar.columnconfigure(0, weight=1)

        ttk.Label(toolbar, text="Question order:").grid(row=0, column=1, sticky="e", padx=(0, 8))
        ttk.Radiobutton(
            toolbar,
            text="Chronological",
            value="Chronological",
            variable=self.question_mode,
            command=self.refresh_question_view,
        ).grid(row=0, column=2, sticky="e", padx=(0, 8))
        ttk.Radiobutton(
            toolbar,
            text="Random",
            value="Random",
            variable=self.question_mode,
            command=self.refresh_question_view,
        ).grid(row=0, column=3, sticky="e")

        question_frame = ttk.LabelFrame(parent, text="Questions")
        question_frame.grid(row=1, column=0, sticky="nsew")
        question_frame.columnconfigure(0, weight=1)
        question_frame.rowconfigure(1, weight=1)

        self.question_status = tk.StringVar(value="No questions found in the inserted text.")
        question_status_label = ttk.Label(question_frame, textvariable=self.question_status, wraplength=760, justify="left", font=self.ui_font)
        question_status_label.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 12))
        self.ui_wrap_labels.append(question_status_label)

        self.question_prompt = tk.StringVar(value="")
        question_prompt_label = ttk.Label(
            question_frame,
            textvariable=self.question_prompt,
            wraplength=760,
            justify="left",
            font=self.ui_heading_font,
        )
        question_prompt_label.grid(row=1, column=0, sticky="new", padx=18, pady=(0, 14))
        self.ui_wrap_labels.append(question_prompt_label)

        self.answers_frame = ttk.Frame(question_frame)
        self.answers_frame.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 14))
        self.answers_frame.columnconfigure(0, weight=1)

        button_row = ttk.Frame(question_frame)
        button_row.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))
        button_row.columnconfigure(0, weight=1)
        self.question_feedback = tk.StringVar(value="")
        question_feedback_label = ttk.Label(button_row, textvariable=self.question_feedback, wraplength=620, justify="left", font=self.ui_font)
        question_feedback_label.grid(row=0, column=0, sticky="w")
        self.ui_wrap_labels.append(question_feedback_label)
        ttk.Button(button_row, text="Weiter", command=self.advance_to_next_question).grid(row=0, column=1, sticky="e")

    def refresh_question_view(self) -> None:
        available_questions = self.get_available_questions()
        if not available_questions:
            self.current_question = None
            self.current_question_index = 0
            self.question_prompt.set("")
            self.question_feedback.set("")
            self.question_status.set("No questions are available yet." if self.questions else "No questions found in the inserted text.")
            self.clear_answer_widgets()
            return

        if self.question_mode.get() == "Random":
            if self.current_question not in available_questions:
                self.current_question = random.choice(available_questions)
        else:
            if self.current_question in available_questions:
                self.current_question_index = available_questions.index(self.current_question)
            else:
                self.current_question_index = min(self.current_question_index, len(available_questions) - 1)
                self.current_question = available_questions[self.current_question_index]
        self.show_current_question(available_questions)

    def show_current_question(self, available_questions: list[Question] | None = None) -> None:
        if self.current_question is None:
            return
        if available_questions is None:
            available_questions = self.get_available_questions()
        self.question_status.set(f"{len(available_questions)} of {len(self.questions)} question(s) available.")
        self.question_prompt.set(self.current_question.prompt)
        self.question_feedback.set("")
        self.render_answer_widgets(self.current_question)

    def advance_to_next_question(self) -> None:
        available_questions = self.get_available_questions()
        if not available_questions:
            self.refresh_question_view()
            return

        if self.question_mode.get() == "Random":
            next_questions = [
                question for question in available_questions if question is not self.current_question
            ]
            self.current_question = random.choice(next_questions or available_questions)
        else:
            if self.current_question in available_questions:
                self.current_question_index = available_questions.index(self.current_question)
            self.current_question_index = (self.current_question_index + 1) % len(available_questions)
            self.current_question = available_questions[self.current_question_index]
        self.show_current_question(available_questions)

    def get_available_questions(self) -> list[Question]:
        if self.question_mode.get() == "Random":
            return self.questions
        return [question for question in self.questions if question.reveal_word_index <= self.rsvp_word_index]

    def clear_answer_widgets(self) -> None:
        for child in self.answers_frame.winfo_children():
            child.destroy()
        self.current_question_choices = []

    def render_answer_widgets(self, question: Question) -> None:
        self.clear_answer_widgets()
        for row, answer in enumerate(question.answers):
            choice = tk.IntVar(value=0)
            self.current_question_choices.append(choice)
            ttk.Checkbutton(self.answers_frame, text=f"{row + 1}: {answer}", variable=choice).grid(
                row=row, column=0, sticky="w", pady=6
            )

    def check_current_question_answer(self) -> None:
        if self.current_question is None:
            return
        selected = [index for index, choice in enumerate(self.current_question_choices, start=1) if choice.get()]
        correct_answer = self.current_question.answers[self.current_question.correct_index - 1]
        if selected == [self.current_question.correct_index]:
            self.question_feedback.set(f"Correct. The correct answer is: {correct_answer}")
        else:
            self.question_feedback.set(f"The correct answer is: {correct_answer}")

    def build_settings_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        for row in range(3):
            parent.rowconfigure(row, weight=1, uniform="settings_rows")

        pause_frame = ttk.LabelFrame(parent, text="Pause")
        pause_frame.grid(row=0, column=0, sticky="nsew")
        pause_frame.columnconfigure(0, weight=1)

        description = ttk.Label(
            pause_frame,
            text=(
                "Choose what RSVP should do at sentence endings. "
                "A sentence ending is detected after ., ?, or ! only when the next non-space "
                "character is uppercase."
            ),
            wraplength=720,
            justify="left",
            font=self.ui_font,
        )
        description.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 12))
        self.ui_wrap_labels.append(description)

        options = [RSVP_MANUAL_SENTENCE_PAUSE, *RSVP_SENTENCE_PAUSE_DURATIONS_MS]
        for row, option in enumerate(options, start=1):
            ttk.Radiobutton(
                pause_frame,
                text=option,
                value=option,
                variable=self.rsvp_sentence_pause_mode,
            ).grid(row=row, column=0, sticky="w", padx=18, pady=5)

        image_pause_frame = ttk.LabelFrame(parent, text="Image Pause")
        image_pause_frame.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        image_pause_frame.columnconfigure(0, weight=1)

        image_pause_description = ttk.Label(
            image_pause_frame,
            text=(
                "Choose how long RSVP should pause when an imported PDF image is shown "
                "at the reading pivot."
            ),
            wraplength=720,
            justify="left",
            font=self.ui_font,
        )
        image_pause_description.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 12))
        self.ui_wrap_labels.append(image_pause_description)

        image_options = [RSVP_MANUAL_IMAGE_PAUSE, *RSVP_IMAGE_PAUSE_DURATIONS_MS]
        for row, option in enumerate(image_options, start=1):
            ttk.Radiobutton(
                image_pause_frame,
                text=option,
                value=option,
                variable=self.rsvp_image_pause_mode,
            ).grid(row=row, column=0, sticky="w", padx=18, pady=5)

        long_word_frame = ttk.LabelFrame(parent, text="Duration long words")
        long_word_frame.grid(row=2, column=0, sticky="nsew", pady=(18, 0))
        long_word_frame.columnconfigure(1, weight=1)

        long_word_description = ttk.Label(
            long_word_frame,
            text=(
                "Slow down words from the selected letter count. "
                "100% keeps them at the normal RSVP wpm; lower percentages display them longer."
            ),
            wraplength=720,
            justify="left",
            font=self.ui_font,
        )
        long_word_description.grid(row=0, column=0, columnspan=3, sticky="ew", padx=18, pady=(18, 12))
        self.ui_wrap_labels.append(long_word_description)

        ttk.Label(long_word_frame, text="From letters:").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        min_length_spinbox = ttk.Spinbox(
            long_word_frame,
            from_=1,
            to=40,
            textvariable=self.rsvp_long_word_min_length,
            width=6,
            command=self.handle_long_word_settings_changed,
        )
        min_length_spinbox.grid(row=1, column=1, sticky="w", padx=12, pady=6)
        min_length_spinbox.bind("<FocusOut>", self.handle_long_word_settings_changed)
        min_length_spinbox.bind("<Return>", self.handle_long_word_settings_changed)

        ttk.Label(long_word_frame, text="Long-word speed:").grid(row=2, column=0, sticky="w", padx=12, pady=(6, 12))
        speed_slider = ttk.Scale(
            long_word_frame,
            from_=MIN_LONG_WORD_WPM_PERCENT,
            to=MAX_LONG_WORD_WPM_PERCENT,
            variable=self.rsvp_long_word_wpm_percent,
            command=self.handle_long_word_settings_changed,
        )
        speed_slider.grid(row=2, column=1, sticky="ew", padx=12, pady=(6, 12))
        ttk.Label(long_word_frame, textvariable=self.rsvp_long_word_wpm_label, width=18).grid(
            row=2,
            column=2,
            sticky="e",
            padx=12,
            pady=(6, 12),
        )

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
        self.show_rsvp_progress_bar()

    def is_rsvp_tab_active(self) -> bool:
        return self.notebook.tab(self.notebook.select(), "text") == "RSVP"

    def handle_tab_changed(self, event: tk.Event | None = None) -> None:
        if not self.is_rsvp_tab_active():
            self.pause_rsvp_playback()

    def toggle_rsvp_fullscreen(self, event: tk.Event | None = None) -> str:
        if self.is_rsvp_fullscreen:
            return self.exit_rsvp_fullscreen(event)
        if not self.is_rsvp_tab_active():
            self.pause_rsvp_playback()
            return "break"
        return self.enter_rsvp_fullscreen()

    def enter_rsvp_fullscreen(self) -> str:
        if self.is_rsvp_fullscreen:
            return "break"

        self.rsvp_fullscreen_visual_offset = self.get_rsvp_windowed_visual_offset()
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

        self.rsvp_fullscreen_visual_offset = None
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
        visual_offset_x, visual_offset_y = self.get_rsvp_visual_offset()
        guide_x = (width / 2) + visual_offset_x + RSVP_GUIDE_OFFSET_X_PX
        guide_y = self.get_rsvp_visual_center_y(height) + visual_offset_y
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
        current_index = self.rsvp_word_index % len(self.rsvp_words)
        image = self.rsvp_image_tokens[current_index] if current_index < len(self.rsvp_image_tokens) else None
        if image is not None:
            canvas.create_image(guide_x, guide_y, image=image, anchor="center")
            return

        word = self.rsvp_words[current_index]
        pivot = self.get_rsvp_pivot_index(word)
        before = word[:pivot]
        pivot_char = word[pivot : pivot + 1]
        after = word[pivot + 1 :]

        font = ("Times New Roman", round(RSVP_BASE_FONT_SIZE * scale))
        pivot_probe = canvas.create_text(-10_000, -10_000, text=pivot_char, font=font, anchor="nw", fill="black")
        pivot_bbox = canvas.bbox(pivot_probe)
        canvas.delete(pivot_probe)
        pivot_width = (pivot_bbox[2] - pivot_bbox[0]) if pivot_bbox else 0
        pivot_left_x = word_x - (pivot_width / 2)

        canvas.create_text(pivot_left_x, word_y, text=before, fill="white", font=font, anchor="e")
        pivot_item = canvas.create_text(pivot_left_x, word_y, text=pivot_char, fill="#ff3045", font=font, anchor="w")
        pivot_bbox = canvas.bbox(pivot_item)
        after_x = pivot_bbox[2] if pivot_bbox else pivot_left_x
        canvas.create_text(after_x, word_y, text=after, fill="white", font=font, anchor="w")

    def get_rsvp_visual_offset(self) -> tuple[float, float]:
        if self.is_rsvp_fullscreen and self.rsvp_fullscreen_visual_offset is not None:
            return self.rsvp_fullscreen_visual_offset
        return (0.0, 0.0)

    def get_rsvp_windowed_visual_offset(self) -> tuple[float, float]:
        self.root.update_idletasks()
        canvas_center_x = self.rsvp_canvas.winfo_rootx() + (self.rsvp_canvas.winfo_width() / 2)
        canvas_center_y = self.rsvp_canvas.winfo_rooty() + self.get_rsvp_visual_center_y(self.rsvp_canvas.winfo_height())
        root_center_x = self.root.winfo_rootx() + (self.root.winfo_width() / 2)
        root_center_y = self.root.winfo_rooty() + (self.root.winfo_height() / 2)
        return (canvas_center_x - root_center_x, canvas_center_y - root_center_y)

    @staticmethod
    def get_rsvp_visual_center_y(canvas_height: int) -> float:
        return canvas_height / 2

    @staticmethod
    def get_rsvp_pivot_index(word: str) -> int:
        letters = [index for index, character in enumerate(word) if character.isalpha()]
        if not letters:
            return 0
        return letters[(len(letters) - 1) // 2]

    def start_rsvp_playback(self) -> None:
        if not self.is_rsvp_tab_active():
            self.pause_rsvp_playback()
            return
        if self.rsvp_after_id is None:
            self.rsvp_after_id = self.root.after(self.get_rsvp_interval_ms(), self.advance_rsvp_word)

    def stop_rsvp_playback(self) -> None:
        if self.rsvp_after_id is not None:
            self.root.after_cancel(self.rsvp_after_id)
            self.rsvp_after_id = None

    def handle_rsvp_space(self, event: tk.Event) -> str | None:
        if event.widget == self.text_box:
            return None
        if not self.is_rsvp_tab_active():
            self.pause_rsvp_playback()
            return None
        self.toggle_rsvp_playback()
        return "break"

    def get_rsvp_interval_ms(self) -> int:
        if self.should_pause_for_current_rsvp_image():
            return 1
        return int(60_000 / max(self.get_current_rsvp_wpm(), 1))

    def get_current_rsvp_wpm(self) -> int:
        base_wpm = self.rsvp_wpm.get()
        if not self.rsvp_words:
            return base_wpm

        current_word = self.rsvp_words[self.rsvp_word_index % len(self.rsvp_words)]
        if self.get_rsvp_letter_count(current_word) < self.rsvp_long_word_min_length.get():
            return base_wpm

        percent = max(
            MIN_LONG_WORD_WPM_PERCENT,
            min(MAX_LONG_WORD_WPM_PERCENT, self.rsvp_long_word_wpm_percent.get()),
        )
        return max(1, round(base_wpm * (percent / 100)))

    @staticmethod
    def get_rsvp_letter_count(word: str) -> int:
        return sum(1 for character in word if character.isalpha())

    def format_long_word_wpm_label(self) -> str:
        percent = max(
            MIN_LONG_WORD_WPM_PERCENT,
            min(MAX_LONG_WORD_WPM_PERCENT, self.rsvp_long_word_wpm_percent.get()),
        )
        effective_wpm = max(1, round(self.rsvp_wpm.get() * (percent / 100)))
        return f"{percent}% ({effective_wpm} wpm)"

    def handle_long_word_settings_changed(self, event: tk.Event | str | None = None) -> None:
        try:
            min_length = int(self.rsvp_long_word_min_length.get())
        except (tk.TclError, ValueError):
            min_length = DEFAULT_LONG_WORD_MIN_LENGTH
        self.rsvp_long_word_min_length.set(max(1, min(40, min_length)))
        self.rsvp_long_word_wpm_percent.set(
            max(
                MIN_LONG_WORD_WPM_PERCENT,
                min(MAX_LONG_WORD_WPM_PERCENT, round(self.rsvp_long_word_wpm_percent.get())),
            )
        )
        self.rsvp_long_word_wpm_label.set(self.format_long_word_wpm_label())
        if self.rsvp_after_id is not None:
            self.stop_rsvp_playback()
            self.start_rsvp_playback()

    def change_rsvp_wpm(self, amount: int) -> str:
        self.set_rsvp_wpm(self.rsvp_wpm.get() + amount)
        return "break"

    def set_rsvp_wpm(self, value: int) -> None:
        minimum = RSVP_WPM_PRESETS[0]
        maximum = RSVP_WPM_PRESETS[-1]
        new_value = max(minimum, min(maximum, value))
        self.rsvp_wpm.set(new_value)
        self.rsvp_wpm_label.configure(text=f"{new_value} wpm")
        self.rsvp_long_word_wpm_label.set(self.format_long_word_wpm_label())
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
        if not self.is_rsvp_tab_active():
            self.pause_rsvp_playback()
            return
        if self.rsvp_after_id is None:
            if self.rsvp_is_sentence_pause or self.rsvp_is_image_pause:
                self.advance_rsvp_word_after_pause()
                return
            self.rsvp_is_sentence_pause = False
            self.rsvp_is_image_pause = False
            self.rsvp_is_paused.set(False)
            self.hide_rsvp_progress_bar()
            self.start_rsvp_playback()
        else:
            self.pause_rsvp_playback()

    def pause_rsvp_playback(self) -> None:
        self.stop_rsvp_playback()
        self.rsvp_is_sentence_pause = False
        self.rsvp_is_image_pause = False
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
        if not self.is_rsvp_tab_active():
            self.pause_rsvp_playback()
            return
        if self.should_pause_for_current_rsvp_image():
            self.start_rsvp_image_pause()
            return
        if self.should_pause_after_current_rsvp_word():
            self.start_rsvp_sentence_pause()
            return
        self.advance_rsvp_word_after_pause()

    def advance_rsvp_word_after_pause(self) -> None:
        self.rsvp_after_id = None
        if not self.is_rsvp_tab_active():
            self.pause_rsvp_playback()
            return
        self.rsvp_is_sentence_pause = False
        self.rsvp_is_image_pause = False
        self.rsvp_is_paused.set(False)
        self.hide_rsvp_progress_bar()
        self.rsvp_word_index = (self.rsvp_word_index + 1) % max(len(self.rsvp_words), 1)
        self.rsvp_progress.set(self.rsvp_word_index)
        self.draw_rsvp_view()
        self.refresh_question_view()
        self.start_rsvp_playback()

    def should_pause_for_current_rsvp_image(self) -> bool:
        if not self.rsvp_image_tokens:
            return False
        return self.rsvp_image_tokens[self.rsvp_word_index % len(self.rsvp_image_tokens)] is not None

    def should_pause_after_current_rsvp_word(self) -> bool:
        if not self.rsvp_sentence_pause_flags:
            return False
        return self.rsvp_sentence_pause_flags[self.rsvp_word_index % len(self.rsvp_sentence_pause_flags)]

    def start_rsvp_image_pause(self) -> None:
        pause_mode = self.rsvp_image_pause_mode.get()
        if pause_mode == RSVP_MANUAL_IMAGE_PAUSE:
            self.rsvp_is_image_pause = True
            self.rsvp_is_paused.set(True)
            self.show_rsvp_progress_bar()
            return

        pause_ms = RSVP_IMAGE_PAUSE_DURATIONS_MS.get(pause_mode, 5_000)
        self.rsvp_after_id = self.root.after(pause_ms, self.advance_rsvp_word_after_pause)

    def start_rsvp_sentence_pause(self) -> None:
        pause_mode = self.rsvp_sentence_pause_mode.get()
        if pause_mode == RSVP_MANUAL_SENTENCE_PAUSE:
            self.rsvp_is_sentence_pause = True
            self.rsvp_is_paused.set(True)
            self.show_rsvp_progress_bar()
            return

        pause_ms = RSVP_SENTENCE_PAUSE_DURATIONS_MS.get(pause_mode, 0)
        self.rsvp_after_id = self.root.after(pause_ms, self.advance_rsvp_word_after_pause)

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
            self.refresh_rsvp_words_from_import(use_source_parts=True)
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
        header = f"{separator}===== {path.name} =====\n"
        self.text_box.insert("end", header)
        self.rsvp_source_parts.append(DocumentPart("text", header))
        for part in content:
            if part.kind == "text":
                text_content = f"{part.content}\n\n"
                self.text_box.insert("end", text_content)
                self.rsvp_source_parts.append(DocumentPart("text", text_content))
            elif part.kind == "image":
                photo = self.insert_pdf_image(part.content)
                if photo is not None:
                    self.rsvp_source_parts.append(DocumentPart("image", photo))
        self.text_box.see("end")
        self.text_box.edit_modified(False)
        if not was_editing:
            self.text_box.configure(state="disabled")

    def refresh_rsvp_words_from_import(self, use_source_parts: bool = False) -> None:
        if use_source_parts and self.rsvp_source_parts:
            self.questions = self.extract_questions_from_parts(self.rsvp_source_parts)
            self.rsvp_words, self.rsvp_sentence_pause_flags, self.rsvp_image_tokens = self.build_rsvp_tokens_from_parts(
                self.rsvp_source_parts
            )
        else:
            imported_text = self.text_box.get("1.0", "end-1c").strip()
            self.questions = self.extract_questions(imported_text)
            self.rsvp_words, self.rsvp_sentence_pause_flags = self.build_rsvp_tokens(imported_text or RSVP_TEXT)
            self.rsvp_image_tokens = [None] * len(self.rsvp_words)
        self.rsvp_word_index = min(self.rsvp_word_index, max(len(self.rsvp_words) - 1, 0))
        self.rsvp_progress_bar.configure(to=max(len(self.rsvp_words) - 1, 0))
        self.rsvp_progress.set(self.rsvp_word_index)
        self.draw_rsvp_view()
        self.refresh_question_view()

    def handle_text_modified(self, event: tk.Event) -> None:
        if not self.text_box.edit_modified():
            return
        self.text_box.edit_modified(False)
        self.refresh_rsvp_words_from_import()

    def build_rsvp_tokens_from_parts(
        self,
        parts: list[DocumentPart],
    ) -> tuple[list[str], list[bool], list[ImageTk.PhotoImage | None]]:
        words: list[str] = []
        pause_flags: list[bool] = []
        image_tokens: list[ImageTk.PhotoImage | None] = []

        for part in parts:
            if part.kind == "text" and isinstance(part.content, str):
                part_words, part_pause_flags = self.build_rsvp_tokens(part.content)
                words.extend(part_words)
                pause_flags.extend(part_pause_flags)
                image_tokens.extend([None] * len(part_words))
            elif part.kind == "image" and isinstance(part.content, ImageTk.PhotoImage):
                words.append(RSVP_IMAGE_TOKEN)
                pause_flags.append(False)
                image_tokens.append(part.content)

        if not words:
            fallback_words, fallback_pause_flags = self.build_rsvp_tokens(RSVP_TEXT)
            return fallback_words, fallback_pause_flags, [None] * len(fallback_words)
        return words, pause_flags, image_tokens

    @staticmethod
    def strip_question_blocks(text: str) -> str:
        return re.sub(r"\?\(\[.*?\]\s*\d+\s*\)\?", " ", text, flags=re.DOTALL)

    @classmethod
    def build_rsvp_tokens(cls, text: str) -> tuple[list[str], list[bool]]:
        text = cls.strip_question_blocks(text)
        word_matches = list(re.finditer(r"\S+", text))
        words = [match.group(0) for match in word_matches]
        pause_flags: list[bool] = []

        for match in word_matches:
            word = match.group(0).rstrip("\"')]}›»”’")
            should_pause = False
            if word.endswith((".", "?", "!")):
                following_text = text[match.end() :]
                next_match = re.search(r"\S", following_text)
                should_pause = bool(next_match and following_text[next_match.start()].isupper())
            pause_flags.append(should_pause)

        if not words:
            return RSVP_TEXT.split(), [False] * len(RSVP_TEXT.split())
        return words, pause_flags


    @classmethod
    def extract_questions_from_parts(cls, parts: list[DocumentPart]) -> list[Question]:
        text = "\n".join(part.content for part in parts if part.kind == "text" and isinstance(part.content, str))
        return cls.extract_questions(text)

    @classmethod
    def extract_questions(cls, text: str) -> list[Question]:
        questions: list[Question] = []
        question_pattern = re.compile(r"\?\(\[(.*?)\]\s*(\d+)\s*\)\?", re.DOTALL)
        for match in question_pattern.finditer(text):
            body = " ".join(match.group(1).split())
            correct_index = int(match.group(2))
            prompt_match = re.match(r"\((.*?)\)\s*(.*)", body)
            if not prompt_match:
                continue
            prompt = prompt_match.group(1).strip()
            answer_body = prompt_match.group(2).strip()
            answer_matches = list(re.finditer(r"(\d+)\s*:\s*(.*?)(?=,\s*\d+\s*:|$)", answer_body))
            answers = [answer_match.group(2).strip().rstrip("?").strip() for answer_match in answer_matches]
            if not prompt or not answers or correct_index < 1 or correct_index > len(answers):
                continue
            reveal_word_index = len(re.findall(r"\S+", cls.strip_question_blocks(text[: match.end()])))
            questions.append(Question(prompt, answers, correct_index, reveal_word_index))
        return questions

    def insert_pdf_image(self, image_data: str | bytes) -> ImageTk.PhotoImage | None:
        if not isinstance(image_data, bytes):
            return None
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
            return None

        self.pdf_images.append(photo)
        self.text_box.image_create("end", image=photo)
        self.text_box.insert("end", "\n\n")
        return photo


def main() -> None:
    root = TkinterDnD.Tk()
    FastReadingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
