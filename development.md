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

## Look at the options window

```commandline
QT_QPA_PLATFORM=offscreen \
~/Library/Application\ Support/AnkiProgramFiles/.venv/bin/python tools/screenshot_options.py
```

Writes one PNG per tab into `dist/`, which is quicker than restarting Anki
when checking spacing or a label that does not fit.

## Build the .ankiaddon file

```commandline
python tools/build_ankiaddon.py
```

Writes `dist/sentence-adder-<version>.ankiaddon`, which is a zip of the
*contents* of `src/` (`manifest.json` and `__init__.py` at the top level, the
folder itself is not in the archive, as
[the add-on docs](https://addon-docs.ankiweb.net/sharing.html) require).
`__pycache__`, `.pyc` files, `meta.json` and `user_files` are left out:
AnkiWeb rejects archives holding `__pycache__`, and `user_files` holds the
sentence databases of whoever runs the build.

Upload the file at <https://ankiweb.net/shared/addons/>. Bump the version in
`src/manifest.json` (`human_version`) and in `anki_addon_version` in
`src/__init__.py` first; a test checks that the two match.

`min_point_version` in the manifest is the oldest Anki that can run the add-on
(50 means 2.1.50; newer releases report versions like 250904 and compare fine).

## Check the dialogs against the installed Anki

The tests fake Qt, so they cannot catch a Qt call that a newer Anki removed.
`tools/qt_smoke.py` builds every dialog for real, using the python inside
Anki's own program folder (macOS path shown):

```commandline
QT_QPA_PLATFORM=offscreen \
~/Library/Application\ Support/AnkiProgramFiles/.venv/bin/python tools/qt_smoke.py
```
