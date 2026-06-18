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
8. The **RSVP** tab shows the included RSVP explanation as one word at a time on a black background with dark guide lines, a red pivot letter, a pause/play button, and a 300 wpm indicator.
9. Imported PDF images are displayed inline in the inserted-text box when they can be extracted from the PDF.
10. Click **DONE** to return to protected view mode.
