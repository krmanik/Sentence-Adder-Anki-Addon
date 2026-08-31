# Setup Addons Development Environment

## Clone this repository

```commandline
git clone https://github.com/krmanik/Sentence-Adder-Anki-Addon.git
```

## Link src into Anki

`src` is the add-on itself, so link it into the add-ons folder and restart Anki.

Windows (Command Prompt as Administrator):
```cmd
cd Sentence-Adder-Anki-Addon
mklink /J %appdata%\Anki2\addons21\1682655437 src
```

macOS:
```commandline
ln -s "$PWD/src" ~/Library/Application\ Support/Anki2/addons21/1682655437
```

Linux:
```commandline
ln -s "$PWD/src" ~/.local/share/Anki2/addons21/1682655437
```

Start Anki from a terminal (`run-anki.bat` on Windows) to see tracebacks and
`print()` output.

## Run the tests

The tests do not need a running Anki. `config.py`, `sentences.py` and
`tsv_import.py` import nothing from Anki, and `editor.py`/`batch_edit.py` are
tested against fake Qt modules and a real `anki` collection.

```commandline
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
```

A single test:
```commandline
.venv/bin/python -m pytest tests/test_batch_edit.py::test_batch_fills_the_sentence_field
```

`aqt` is only listed so an IDE can resolve the imports; at runtime Anki
provides `anki` and `aqt` itself.
