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
6. Choose a highlight color, select text, and click **Mark** to highlight only the visible text without surrounding whitespace. Select an already highlighted area and click **Mark** again to remove that highlight.
7. Use the top tabs to switch between **FastReading Import** and the empty placeholder tab.
8. Imported PDF images are displayed inline in the inserted-text box when they can be extracted from the PDF.
9. Click **DONE** to return to protected view mode.
