"""Tests for the editor button, the path users say works well.

The point here is that it keeps working after the rewrite, including the
cases that used to fail silently: no database selected, a word with only one
matching sentence, and a field that lost focus.
"""

import os
import sqlite3

import pytest

import fake_anki
from conftest import load_addon_module

recorder = fake_anki.install()
editor_mod = load_addon_module("editor")


class FakeNote:
    def __init__(self, fields, names=("Word", "Sentence", "Translation")):
        self.fields = list(fields)
        self._names = list(names)

    def keys(self):
        return list(self._names)


class FakeEditor:
    """Enough of aqt's editor for add_sentences()."""

    def __init__(self, note, current_field=0, selection="cat"):
        self.note = note
        self.currentField = current_field
        self.last_field_index = current_field
        self.selection = selection
        self.loaded_focus = None
        self.web = self
        self._links = {}

    def evalWithCallback(self, js, callback):
        callback(self.selection)

    def loadNote(self, focusTo=None):
        self.loaded_focus = focusTo

    def _addButton(self, icon, cmd, tip="", **kwargs):
        return "<button %s icon=%s>" % (cmd, os.path.basename(icon))


@pytest.fixture
def addon(tmp_path, monkeypatch):
    """Point the add-on at a throwaway user_files folder."""
    store = editor_mod.config_mod.Config(str(tmp_path / "user_files"))
    store.ensure_dirs()
    monkeypatch.setattr(editor_mod, "config_store", store)
    recorder.tooltips.clear()
    return store


def make_db(store, rows, name="eng.db", pair=False):
    path = str(store.lang_db_folder + "/" + name)
    con = sqlite3.connect(path)
    if pair:
        con.execute("CREATE TABLE examples (id INTEGER PRIMARY KEY, sentence TEXT, translation TEXT)")
        con.executemany("INSERT INTO examples (sentence, translation) VALUES (?,?)", rows)
    else:
        con.execute("CREATE TABLE examples (id INTEGER PRIMARY KEY, sentence TEXT)")
        con.executemany("INSERT INTO examples (sentence) VALUES (?)", [(r,) for r in rows])
    con.commit()
    con.close()
    store.add_language("English", path)
    store.update(lang="English")
    return path


def test_adds_a_sentence_to_the_focused_field(addon):
    make_db(addon, ["I like cats.", "The cat sleeps."])
    addon.update(num_of_sen="1", sen_len="100")
    note = FakeNote(["cat", "", ""])
    ed = FakeEditor(note, current_field=1)

    editor_mod.add_sentences(ed)

    assert note.fields[1].endswith("<br>")
    assert "cat" in note.fields[1]
    assert ed.loaded_focus == 1


def test_keeps_what_the_field_already_had(addon):
    make_db(addon, ["The cat sleeps."])
    addon.update(num_of_sen="1", sen_len="100")
    note = FakeNote(["cat", "existing text", ""])
    ed = FakeEditor(note, current_field=1)

    editor_mod.add_sentences(ed)

    assert note.fields[1].startswith("existing text<br>")


def test_one_matching_sentence_is_enough(addon):
    """Asking for 2 sentences when only 1 matched used to add nothing."""
    make_db(addon, ["The cat sleeps."])
    addon.update(num_of_sen="2", sen_len="100")
    note = FakeNote(["cat", "", ""])
    ed = FakeEditor(note, current_field=1)

    editor_mod.add_sentences(ed)

    assert "The cat sleeps." in note.fields[1]


def test_sentence_pair_goes_under_the_sentence(addon):
    make_db(addon, [("私は猫が好きです。", "I like cats.")], name="jpn.db", pair=True)
    addon.update(num_of_sen="1", sen_len="100")
    note = FakeNote(["猫", "", ""])
    ed = FakeEditor(note, current_field=1, selection="猫")

    editor_mod.add_sentences(ed)

    assert note.fields[1] == "私は猫が好きです。<br>I like cats.<br>"


def test_no_database_selected_explains_itself(addon):
    note = FakeNote(["cat", "", ""])
    ed = FakeEditor(note, current_field=1)

    editor_mod.add_sentences(ed)

    assert "Database not found" in recorder.last_tooltip
    assert note.fields[1] == ""


def test_word_without_matches_says_so(addon):
    make_db(addon, ["The cat sleeps."])
    note = FakeNote(["dog", "", ""])
    ed = FakeEditor(note, current_field=1, selection="dog")

    editor_mod.add_sentences(ed)

    assert "No sentences found" in recorder.last_tooltip


def test_nothing_selected_says_so(addon):
    note = FakeNote(["cat", "", ""])
    ed = FakeEditor(note, current_field=1, selection="")

    editor_mod.add_sentences(ed)

    assert "Select a word" in recorder.last_tooltip


def test_falls_back_to_the_last_focused_field(addon):
    make_db(addon, ["The cat sleeps."])
    addon.update(num_of_sen="1")
    note = FakeNote(["cat", "", ""])
    ed = FakeEditor(note, current_field=None)
    ed.last_field_index = 1

    editor_mod.add_sentences(ed)

    assert "cat" in note.fields[1]


def test_configured_target_field_wins_over_the_cursor(addon):
    make_db(addon, ["The cat sleeps."])
    addon.update(num_of_sen="1", target_field="Sentence")
    note = FakeNote(["cat", "", ""])
    ed = FakeEditor(note, current_field=0)

    editor_mod.add_sentences(ed)

    assert note.fields[0] == "cat"
    assert "The cat sleeps." in note.fields[1]


def test_target_field_is_matched_case_insensitively(addon):
    addon.update(target_field="sentence")
    note = FakeNote(["cat", "", ""])
    ed = FakeEditor(note, current_field=0)

    assert editor_mod.target_field_index(ed, addon.load()) == 1


def test_unknown_target_field_falls_back_to_the_cursor(addon):
    addon.update(target_field="Not a field")
    note = FakeNote(["cat", "", ""])
    ed = FakeEditor(note, current_field=2)

    assert editor_mod.target_field_index(ed, addon.load()) == 2


def test_lookup_options_read_the_length_settings(addon):
    addon.update(sen_len="60", sen_min_len="10", sen_contain_space="true")

    assert editor_mod.lookup_options(addon.load()) == {
        "min_len": 10, "max_len": 60, "whole_word": True}


def test_lookup_options_survive_empty_length_settings(addon):
    addon.update(sen_len="", sen_min_len="")

    assert editor_mod.lookup_options(addon.load()) == {
        "min_len": 0, "max_len": 0, "whole_word": False}


def test_minimum_length_keeps_short_sentences_out(addon):
    make_db(addon, ["A cat.", "The cat is sleeping on the sofa."])
    addon.update(num_of_sen="1", sen_min_len="20", sen_len="100")
    note = FakeNote(["cat", "", ""])
    ed = FakeEditor(note, current_field=1)

    editor_mod.add_sentences(ed)

    assert note.fields[1] == "The cat is sleeping on the sofa.<br>"


def test_the_editor_gets_an_add_button_and_a_settings_button(addon):
    note = FakeNote(["cat", "", ""])
    ed = FakeEditor(note, current_field=0)

    buttons = editor_mod.addSentenceButton(["existing"], ed)

    assert buttons[0] == "existing"
    assert len(buttons) == 3
    assert "icon.png" in buttons[1]
    assert "settings_icon.png" in buttons[2]
    assert "addSentence" in ed._links
    assert "sentenceAdderSettings" in ed._links


def test_settings_button_offers_the_fields_of_the_open_note(addon, monkeypatch):
    import sys

    package = sys.modules["sentence_adder_addon"]
    opened = []
    monkeypatch.setattr(package, "showSenAdder", opened.append, raising=False)
    ed = FakeEditor(FakeNote(["cat", "", ""]), current_field=0)

    editor_mod.show_settings(ed)

    assert opened == [["Word", "Sentence", "Translation"]]


def test_note_field_names_without_a_note(addon):
    ed = FakeEditor(FakeNote([""]), current_field=0)
    ed.note = None

    assert editor_mod.note_field_names(ed) == []


def test_get_random_sentence_returns_none_without_a_database(addon):
    assert editor_mod.getRandomSentence("cat") is None
