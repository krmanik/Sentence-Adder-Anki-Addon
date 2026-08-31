# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An Anki add-on (AnkiWeb id `1682655437`) that inserts example sentences from a Tatoeba-derived SQLite database into note fields. `src/` **is** the add-on package — Anki's add-on manager loads it directly; nothing here builds or packages it.

## Commands

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest                                    # whole suite
.venv/bin/python -m pytest tests/test_batch_edit.py -k undo   # one test
.venv/bin/python -m py_compile src/*.py                       # syntax check
```

To run inside Anki, symlink the package and restart Anki (`ln -s "$PWD/src" ~/Library/Application\ Support/Anki2/addons21/1682655437`; `mklink /J` on Windows — see [development.md](development.md)). Launch Anki from a terminal (`run-anki.bat`) for tracebacks: most handlers turn an exception into a `tooltip()`.

There is no linter configured.

## Testing without Anki

`aqt` cannot be imported outside Anki, so tests reach the add-on two ways, both via [tests/conftest.py](tests/conftest.py):

- `load()` — imports `config.py`, `sentences.py`, `tsv_import.py` straight from their files. These three import nothing from `anki`/`aqt`; **keep it that way**, it is what makes them testable.
- `load_addon_module()` — registers `src/` as a package under a fake name (without executing `src/__init__.py`) so relative imports resolve, then imports `editor`/`batch_edit`. [tests/fake_anki.py](tests/fake_anki.py) must be installed first: it puts stub `aqt`, `aqt.qt`, `aqt.utils`, `aqt.operations` and `anki.hooks` modules in `sys.modules`, where any Qt name resolves to a permissive dummy class. Its `FakeCollectionOp` runs the batch operation synchronously against a collection the test sets on `FakeCollectionOp.collection`.

Two constraints that break the suite if ignored: the stub recorder is a singleton (add-on modules bind `tooltip` at import time), and `load_addon_module` caches (the modules import each other and must share one object). Batch tests use a **real** `anki.collection.Collection`, so note and undo behaviour is genuinely exercised.

## Architecture

Anki imports `src/__init__.py`, which imports `editor` and `batch_edit` for their **import-time side effects** — each registers itself with `addHook` at the bottom of the file. Adding a UI surface means adding an import plus its own hook call.

Anki-free core:

- [config.py](src/config.py) — `Config` wraps `user_files/config.json`. Every access re-reads the file, which is what makes option changes apply without restarting Anki. Also owns `db_path()` and language registration.
- [sentences.py](src/sentences.py) — lookup and formatting. `SentenceDB` keeps one connection open (batch runs); `find_sentences()` is the one-off wrapper. Also `strip_html`, `pick_random`, `render`/`render_inline`.
- [tsv_import.py](src/tsv_import.py) — builds a language database from a tsv.

Anki-facing:

- [\_\_init\_\_.py](src/__init__.py) — Tools → Sentence Adder…: options, create database, remove language.
- [editor.py](src/editor.py) — editor button (`setupEditorButtons`). The selected word arrives **asynchronously** through `editor.web.evalWithCallback(...)`, so all insertion logic lives in that callback. `lookup_options()` and `find_for_word()` are shared with the batch adder.
- [batch_edit.py](src/batch_edit.py) — Browser → Edit → Sentence Batch Adder…, a `CollectionOp` running off the main thread. It must not touch Qt outside `mw.taskman.run_on_main`, and it owns its progress window (opening one by hand beforehand is what used to leave Anki hung). `update_note()` holds the per-note logic and takes plain arguments so tests can drive it.

### Config and databases

Everything user-owned lives in `src/user_files/` (gitignored; Anki preserves it across add-on updates).

`config.json` is one flat dict where **booleans are the strings `"true"`/`"false"`** and numbers are strings — read them through `config.as_bool` / `config.as_int`, never directly. Missing keys are filled from `DEFAULT_CONFIG` on load, which is how older configs are migrated; a new setting means adding it to that dict only.

Language databases are `user_files/lang_db/<name>.db`, table `examples(id, sentence[, translation])`. The `lang_db` dict in the config maps language name → **file name**. Two compatibility rules matter:

- Up to 1.0.6 the mapping lived in top-level config keys holding **absolute paths**. `Config.db_path()` still reads that form, and prefers a file of the same name in the current `lang_db` folder — that is what fixes "Database not exists!" after a move or reinstall.
- `db_contain_pair` is a stale global flag kept only for older configs. Whether a database has translations is detected per database with `sentences.has_translations()`.

### Things worth knowing before changing behaviour

- Word lookups always go through `strip_html()` first; note fields carry markup that matches nothing.
- Queries are parameterised with `LIKE ? ESCAPE '\'` and `escape_like()`. Never build the pattern by concatenation — a word with `'`, `%` or `_` breaks or widens the search.
- Whole-word mode (`sen_contain_space`) over-fetches from SQL and filters in Python with a word-boundary regex, case-insensitively, to match sqlite's ASCII-insensitive `LIKE`.
- `LIKE '%word%'` cannot use an index, so lookups are capped by `CANDIDATE_LIMIT` and sentences are chosen from that window.
