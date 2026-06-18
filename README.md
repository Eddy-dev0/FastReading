# FastReading

FastReading ist eine kleine Tkinter-Anwendung, mit der `.txt`- und `.pdf`-Dateien per Drag & Drop oder Dateiauswahl importiert werden können. Der extrahierte Text wird in einer Textbox unterhalb des Importbereichs angezeigt. Standardmäßig ist die Textbox schreibgeschützt; über den **EDIT**-Button kann der Bearbeitungsmodus ein- und ausgeschaltet werden.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> Hinweis: Tkinter muss auf dem System verfügbar sein. Unter Debian/Ubuntu kann dafür z. B. `python3-tk` nötig sein.

## Start

```bash
python app.py
```

## Nutzung

1. Starte die Anwendung.
2. Ziehe eine oder mehrere `.txt`- oder `.pdf`-Dateien in das Drag-&-Drop-Feld.
3. Alternativ kannst du über **Dateien auswählen** Dateien öffnen.
4. Der erkannte Text erscheint in der darunterliegenden Textbox zunächst im geschützten Anzeigemodus.
5. Klicke auf **EDIT**, um den Text im Fenster zu bearbeiten; mit **Bearbeitung beenden** wird er wieder schreibgeschützt angezeigt.
