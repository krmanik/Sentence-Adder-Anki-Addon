"""Upgrading must not ask anyone to rebuild anything.

A user upgrading from 1.0.6 has a config.json without the newer keys, holding
an absolute path per language, and a lang_db folder full of databases. Both
the editor button and the batch adder have to work with that untouched.
"""

import json
import os
import sqlite3

import pytest

import fake_anki
from conftest import load_addon_module

recorder = fake_anki.install()
batch_edit = load_addon_module("batch_edit")
editor_mod = load_addon_module("editor")

from anki.collection import Collection  # noqa: E402

from test_batch_edit import BASE_OPTIONS, add_note, note_type, run_batch  # noqa: E402
from test_editor import FakeEditor, FakeNote  # noqa: E402

OLD_CONFIG = {
    "lang": "English",
    "all_lang": ["-- Select Language --", "English"],
    "text_color": "#0000ff",
    "word_color": "#ff0000",
    "word_html": "",
    "sen_html": "",
    "auto_add": "true",
    "open_all_sen_window": "false",
    "sen_contain_space": "true",
    "db_contain_pair": "false",
    "sen_len": "30",
    "num_of_sen": "2",
}


@pytest.fixture
def old_install(tmp_path, monkeypatch):
    """A user_files folder exactly as 1.0.6 left it."""
    user_folder = tmp_path / "user_files"
    lang_db = user_folder / "lang_db"
    lang_db.mkdir(parents=True)

    db_file = lang_db / "eng.db"
    con = sqlite3.connect(str(db_file))
    con.execute("CREATE TABLE examples (id INTEGER PRIMARY KEY, sentence TEXT)")
    con.executemany(
        "INSERT INTO examples (sentence) VALUES (?)",
        [("I like cats.",), ("The cat sleeps.",), ("A dog barks.",)],
    )
    con.commit()
    con.close()

    config = dict(OLD_CONFIG)
    config["English"] = str(db_file)  # 1.0.6 stored an absolute path
    with open(user_folder / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f)

    store = editor_mod.config_mod.Config(str(user_folder))
    monkeypatch.setattr(editor_mod, "config_store", store)
    recorder.tooltips.clear()
    return store


@pytest.fixture
def col(tmp_path):
    collection = Collection(str(tmp_path / "collection.anki2"))
    yield collection
    collection.close()


def test_old_settings_are_kept(old_install):
    config = old_install.load()

    assert config["word_color"] == "#ff0000"
    assert config["sen_len"] == "30"
    assert config["sen_contain_space"] == "true"
    assert config["English"] == old_install.load()["English"]
    assert config["sen_min_len"] == "0"


def test_old_config_still_finds_its_database(old_install):
    assert old_install.db_path(old_install.load()).endswith("lang_db/eng.db")


def test_editor_button_works_on_an_old_install(old_install):
    note = FakeNote(["cat", "", ""])
    ed = FakeEditor(note, current_field=1)

    editor_mod.add_sentences(ed)

    assert '<font color="#ff0000">cat</font>' in note.fields[1]


def test_batch_adder_works_on_an_old_install(col, old_install):
    model = note_type(col)
    nid = add_note(col, model, {"Word": "cat"})

    result = run_batch(col, [nid], dict(BASE_OPTIONS))

    assert result["updated"] == 1
    assert "cat" in col.get_note(nid)["Sentence"]


def test_the_database_file_is_not_touched(old_install):
    db_path = old_install.db_path(old_install.load())
    before = os.path.getsize(db_path)

    editor_mod.getRandomSentence("cat")

    assert os.path.getsize(db_path) == before


def test_a_database_left_where_1_0_6_put_it_is_still_found(tmp_path, monkeypatch):
    """The add-on folder was renamed or the profile moved."""
    user_folder = tmp_path / "user_files"
    lang_db = user_folder / "lang_db"
    lang_db.mkdir(parents=True)
    db_file = lang_db / "eng.db"
    con = sqlite3.connect(str(db_file))
    con.execute("CREATE TABLE examples (id INTEGER PRIMARY KEY, sentence TEXT)")
    con.execute("INSERT INTO examples (sentence) VALUES ('The cat sleeps.')")
    con.commit()
    con.close()

    config = dict(OLD_CONFIG)
    config["English"] = "/Volumes/OldMac/Anki2/addons21/1682655437/user_files/lang_db/eng.db"
    with open(user_folder / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f)

    store = editor_mod.config_mod.Config(str(user_folder))
    monkeypatch.setattr(editor_mod, "config_store", store)

    assert store.db_path(store.load()) == str(db_file)
