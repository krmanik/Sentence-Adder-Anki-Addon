"""Batch adder tests, run against a real Anki collection.

These cover the reports the add-on kept getting: "Error: 'word_color'", an
empty error message, and "it updates nothing at all".
"""

import os
import sqlite3

import pytest

import fake_anki
from conftest import load_addon_module

recorder = fake_anki.install()
batch_edit = load_addon_module("batch_edit")
editor_mod = load_addon_module("editor")

from anki.collection import Collection  # noqa: E402  (needs no fakes)


@pytest.fixture
def col(tmp_path):
    collection = Collection(str(tmp_path / "collection.anki2"))
    yield collection
    collection.close()


@pytest.fixture
def store(tmp_path, monkeypatch):
    store = editor_mod.config_mod.Config(str(tmp_path / "user_files"))
    store.ensure_dirs()
    monkeypatch.setattr(editor_mod, "config_store", store)
    recorder.tooltips.clear()
    return store


def note_type(col, name="SentenceTest", fields=("Word", "Sentence", "Translation")):
    models = col.models
    model = models.new(name)
    for field in fields:
        models.add_field(model, models.new_field(field))
    template = models.new_template("Card 1")
    template["qfmt"] = "{{%s}}" % fields[0]
    template["afmt"] = "{{%s}}" % fields[1]
    models.add_template(model, template)
    models.add(model)
    return models.by_name(name)


def add_note(col, model, values):
    note = col.new_note(model)
    for field, value in values.items():
        note[field] = value
    col.add_note(note, col.decks.id("Default"))
    return note.id


def make_db(store, rows, name="lang.db", pair=False):
    path = os.path.join(store.lang_db_folder, name)
    con = sqlite3.connect(path)
    if pair:
        con.execute("CREATE TABLE examples (id INTEGER PRIMARY KEY, sentence TEXT, translation TEXT)")
        con.executemany("INSERT INTO examples (sentence, translation) VALUES (?,?)", rows)
    else:
        con.execute("CREATE TABLE examples (id INTEGER PRIMARY KEY, sentence TEXT)")
        con.executemany("INSERT INTO examples (sentence) VALUES (?)", [(r,) for r in rows])
    con.commit()
    con.close()
    lang = store.add_language(name.split(".")[0], path)
    store.update(lang=lang)
    return path


def run_batch(col, nids, options):
    """Run the batch operation the way CollectionOp would."""
    fake_anki.FakeCollectionOp.collection = col
    result = {}

    def on_complete(updated, not_found):
        result["updated"] = updated
        result["not_found"] = not_found

    batch_edit.batch_edit_notes(None, nids, options, on_complete)
    return result


BASE_OPTIONS = {
    "word_field": "Word",
    "sen_field": "Sentence",
    "trans_field": "",
    "overwrite": False,
}


def test_batch_fills_the_sentence_field(col, store):
    make_db(store, ["I like cats.", "The cat sleeps."])
    store.update(num_of_sen="1", sen_len="100")
    model = note_type(col)
    nid = add_note(col, model, {"Word": "cat"})

    result = run_batch(col, [nid], dict(BASE_OPTIONS))

    note = col.get_note(nid)
    assert result["updated"] == 1
    assert "cat" in note["Sentence"]
    assert note["Word"] == "cat"


def test_batch_runs_with_colors_configured(col, store):
    """The reported crash: Error: 'word_color' with colours set in the config."""
    make_db(store, ["The cat sleeps."])
    store.update(num_of_sen="1", word_color="#ff0000", text_color="#0000ff")
    model = note_type(col)
    nid = add_note(col, model, {"Word": "cat"})

    result = run_batch(col, [nid], dict(BASE_OPTIONS))

    assert result["updated"] == 1
    assert '<font color="#ff0000">cat</font>' in col.get_note(nid)["Sentence"]


def test_batch_without_a_translation_field_does_not_fail(col, store):
    """Writing to the empty translation field raised KeyError: ''."""
    make_db(store, [("私は猫が好きです。", "I like cats.")], pair=True)
    store.update(num_of_sen="1", sen_len="100")
    model = note_type(col)
    nid = add_note(col, model, {"Word": "猫"})

    result = run_batch(col, [nid], dict(BASE_OPTIONS, trans_field=""))

    note = col.get_note(nid)
    assert result["updated"] == 1
    assert note["Sentence"] == "私は猫が好きです。<br>I like cats.<br>"
    assert note["Translation"] == ""


def test_batch_writes_translations_to_their_own_field(col, store):
    make_db(store, [("私は猫が好きです。", "I like cats.")], pair=True)
    store.update(num_of_sen="1", sen_len="100")
    model = note_type(col)
    nid = add_note(col, model, {"Word": "猫"})

    run_batch(col, [nid], dict(BASE_OPTIONS, trans_field="Translation"))

    note = col.get_note(nid)
    assert note["Sentence"] == "私は猫が好きです。<br>"
    assert note["Translation"] == "I like cats.<br>"


def test_word_field_html_is_ignored_when_searching(col, store):
    make_db(store, ["The cat sleeps."])
    store.update(num_of_sen="1")
    model = note_type(col)
    nid = add_note(col, model, {"Word": "<b>cat</b>&nbsp;"})

    result = run_batch(col, [nid], dict(BASE_OPTIONS))

    assert result["updated"] == 1
    assert "The cat sleeps." in col.get_note(nid)["Sentence"]


def test_existing_sentences_are_kept_unless_overwrite_is_ticked(col, store):
    make_db(store, ["The cat sleeps."])
    store.update(num_of_sen="1")
    model = note_type(col)
    nid = add_note(col, model, {"Word": "cat", "Sentence": "old sentence"})

    run_batch(col, [nid], dict(BASE_OPTIONS))
    assert col.get_note(nid)["Sentence"].startswith("old sentence")

    run_batch(col, [nid], dict(BASE_OPTIONS, overwrite=True))
    assert col.get_note(nid)["Sentence"] == "The cat sleeps.<br>"


def test_overwrite_clears_the_translation_field_too(col, store):
    make_db(store, [("私は猫が好きです。", "I like cats.")], pair=True)
    store.update(num_of_sen="1")
    model = note_type(col)
    nid = add_note(col, model, {"Word": "猫", "Sentence": "old", "Translation": "old"})

    run_batch(col, [nid], dict(BASE_OPTIONS, trans_field="Translation", overwrite=True))

    note = col.get_note(nid)
    assert note["Sentence"] == "私は猫が好きです。<br>"
    assert note["Translation"] == "I like cats.<br>"


def test_words_without_a_match_are_reported_not_written(col, store, tmp_path):
    make_db(store, ["The cat sleeps."])
    model = note_type(col)
    matching = add_note(col, model, {"Word": "cat"})
    missing = add_note(col, model, {"Word": "aardvark"})

    result = run_batch(col, [matching, missing], dict(BASE_OPTIONS))

    assert result["updated"] == 1
    assert result["not_found"] == ["aardvark"]
    assert col.get_note(missing)["Sentence"] == ""


def test_not_found_file_is_only_written_when_something_is_missing(store):
    assert batch_edit.write_not_found([]) is None

    path = batch_edit.write_not_found(["aardvark", "quokka"])
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as f:
        assert f.read().split() == ["aardvark", "quokka"]


def test_a_note_type_without_the_chosen_field_is_skipped(col, store):
    """A mixed selection used to stop the run with a KeyError."""
    make_db(store, ["The cat sleeps."])
    store.update(num_of_sen="1")
    normal = note_type(col)
    other = note_type(col, name="OtherType", fields=("Front", "Back"))
    good = add_note(col, normal, {"Word": "cat"})
    unrelated = add_note(col, other, {"Front": "cat"})

    result = run_batch(col, [good, unrelated], dict(BASE_OPTIONS))

    assert result["updated"] == 1
    assert "The cat sleeps." in col.get_note(good)["Sentence"]
    assert col.get_note(unrelated)["Back"] == ""


def test_empty_word_field_is_skipped_quietly(col, store):
    make_db(store, ["The cat sleeps."])
    model = note_type(col)
    nid = add_note(col, model, {"Word": ""})

    result = run_batch(col, [nid], dict(BASE_OPTIONS))

    assert result["updated"] == 0
    assert result["not_found"] == []


def test_batch_is_a_single_undo_step(col, store):
    make_db(store, ["The cat sleeps."])
    store.update(num_of_sen="1")
    model = note_type(col)
    nids = [add_note(col, model, {"Word": "cat"}) for _ in range(3)]

    run_batch(col, nids, dict(BASE_OPTIONS))

    assert col.undo_status().undo == "Sentence Adder Batch Edit"
    col.undo()
    assert all(col.get_note(nid)["Sentence"] == "" for nid in nids)


def test_without_a_language_the_operation_says_so(col, store):
    model = note_type(col)
    nid = add_note(col, model, {"Word": "cat"})

    with pytest.raises(ValueError) as excinfo:
        run_batch(col, [nid], dict(BASE_OPTIONS))

    assert "No sentence database selected" in str(excinfo.value)


def test_field_names_covers_every_selected_note_type(col, store):
    normal = note_type(col)
    other = note_type(col, name="OtherType", fields=("Front", "Back"))
    nids = [add_note(col, normal, {"Word": "cat"}), add_note(col, other, {"Front": "x"})]

    assert batch_edit.field_names(col, nids) == [
        "Word", "Sentence", "Translation", "Front", "Back"]


def test_field_names_reads_note_types_not_every_note(col, store, monkeypatch):
    model = note_type(col)
    nids = [add_note(col, model, {"Word": "cat"}) for _ in range(5)]
    loaded = []
    real_get_note = col.get_note
    monkeypatch.setattr(col, "get_note", lambda nid: loaded.append(nid) or real_get_note(nid))

    assert batch_edit.field_names(col, nids) == ["Word", "Sentence", "Translation"]
    assert loaded == []


def test_number_of_sentences_setting_is_used(col, store):
    make_db(store, ["cat one", "cat two", "cat three", "cat four"])
    store.update(num_of_sen="3", sen_len="100")
    model = note_type(col)
    nid = add_note(col, model, {"Word": "cat"})

    run_batch(col, [nid], dict(BASE_OPTIONS))

    assert col.get_note(nid)["Sentence"].count("<br>") == 3
