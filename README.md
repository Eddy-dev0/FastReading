# FastReading

FastReading is a small desktop app for importing `.txt` and `.pdf` files, reviewing the extracted text, and reading it with RSVP. The app is built with Tkinter and supports drag and drop, manual file selection, inline PDF images, text highlighting, RSVP playback, and embedded multiple-choice questions.

## What RSVP means

RSVP stands for **Rapid Serial Visual Presentation**. Instead of showing a full paragraph, RSVP displays one word at a time at a fixed point on the screen. FastReading highlights the word's pivot character in red so your eyes can stay near the same position while the words change. This can reduce eye movement and help you practice faster reading, while the pause settings still let you slow down at sentence endings, images, long words, or numbers.

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
4. Recognized text appears in the **Inserted Text** box in protected view mode.
5. Click **EDIT** to edit the text. The **Mark** button and color picker appear next to it.
6. Choose a highlight color, select text, and click **Mark** to highlight only letters. Spaces, numbers, punctuation, line gaps, and other non-letter characters stay unmarked, so no large color blocks appear between words or lines. Select an already highlighted area and click **Mark** again to remove that highlight.
7. Use the top tabs to switch between **FastReading Import**, **RSVP**, **Questions**, and **Settings**.
8. Open the **RSVP** tab to read the current imported text one word at a time on a black background. The red character is the pivot character; for words with an even number of letters, the pivot is rounded down to the left middle letter.
9. Press **Space** to play or pause RSVP playback. When playback is paused, use the green seek bar to scrub through the current text.
10. Change the RSVP speed only with the keyboard:
    - **Right Arrow** or **Up Arrow**: increase speed by 25 wpm.
    - **Left Arrow** or **Down Arrow**: decrease speed by 25 wpm.
11. Press **F** while the RSVP tab is active to enter fullscreen mode. Press **Escape** to leave fullscreen mode.
12. Imported PDF images are displayed inline in the inserted-text box when they can be extracted from the PDF. RSVP can also pause on imported images.
13. Open **Settings** to configure sentence-ending pauses, image pauses, long-word speed, and number speed.
14. Click **DONE** to return to protected view mode after editing.

## Adding questions with ChatGPT

FastReading can detect embedded multiple-choice questions when they use this format:

```text
?([(Question text) 1: First answer, 2: Second answer, 3: Third answer] 2)?
```

The number after the closing bracket is the correct answer number. You can paste these question blocks directly into your imported text. RSVP hides the question blocks while reading, and the **Questions** tab makes questions available as you reach their position in the text.

To generate useful questions with ChatGPT, append this prompt to the text you want to prepare:

```text
Create concise multiple-choice comprehension questions for this text. Insert each question directly after the relevant paragraph using exactly this format: ?([(Question text) 1: First answer, 2: Second answer, 3: Third answer, 4: Fourth answer] correct_number)?. Use English only. Make one answer clearly correct, make the distractors plausible, and set correct_number to the number of the correct answer. Do not change the original text except for inserting the question blocks.
```

## Question format example

```text
RSVP shows one word at a time so the reader can focus on a stable visual point.
?([(What does RSVP show during playback?) 1: One word at a time, 2: A full book page, 3: Only images, 4: A list of settings] 1)?
```
