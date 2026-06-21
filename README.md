# FastReading

FastReading is a small Tkinter application for importing `.txt` and `.pdf` files by drag and drop or by file picker. Extracted text is shown in the reading box below the import area. The box is read-only by default; use the **EDIT** button to switch editing on and reveal extra editing tools.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> Note: Tkinter must be available on your system. On Debian/Ubuntu, you may need to install `python3-tk`.

## Start

```bash
python app.py
```

## Usage

1. Start the application.
2. Drag one or more `.txt` or `.pdf` files into the drag-and-drop area.
3. Alternatively, open files with **Choose files**.
4. Recognized text appears in the inserted-text box in protected view mode.
5. Click **EDIT** to edit the text. The **Mark** button and color picker appear next to it.
6. Choose a highlight color, select text, and click **Mark** to highlight only letters. Spaces, numbers, punctuation, line gaps, and other non-letter characters stay unmarked, so no large color blocks appear between words or lines. Select an already highlighted area and click **Mark** again to remove that highlight.
7. Use the top tabs to switch between **FastReading Import** and the **RSVP** tab.
8. The **RSVP** tab reads the current text from **FastReading Import** one word at a time on a black background with dark guide lines, a centered red pivot letter, and a 300 wpm indicator. The pivot is the middle letter; for words with an even number of letters, the pivot is rounded down to the left middle letter. Click the wpm indicator to open a clean upward wpm picker. Use arrow keys to adjust the speed by 25 wpm. Press Space to pause and reveal the green seek bar for scrubbing through the current text. While paused, a **?** button appears in the top-left corner. It opens **Abfragen**, where you can generate comprehension questions from the beginning, from the last generated question range, or from a custom slider-selected reading position. Questions are generated locally by selecting meaningful sentences, extracting keywords, and turning them into short understanding prompts with model answers.
9. Imported PDF images are displayed inline in the inserted-text box when they can be extracted from the PDF.
10. Open **Settings** to choose sentence-ending pauses for RSVP: wait until Space is pressed, or pause automatically for 1, 2, 5, or 10 seconds. Sentence endings are detected after `.`, `?`, or `!` when the next non-space character is uppercase.
11. In **Settings**, use **Duration long words** to choose the minimum word length and the percentage speed for those long words. At 100%, long words use the normal wpm. Below 100%, long words are displayed longer; for example, 50% at 300 wpm displays matching long words at 150 wpm.
12. Click **DONE** to return to protected view mode.
