import json
import os

import pytest

from conftest import load

config_mod = load("config")


@pytest.fixture
def cfg(tmp_path):
    store = config_mod.Config(str(tmp_path / "user_files"))
    store.ensure_dirs()
    return store


def write_raw(store, data):
    store.ensure_dirs()
    with open(store.config_json, "w", encoding="utf-8") as f:
        json.dump(data, f)


def test_load_creates_defaults_when_missing(cfg):
    data = cfg.load()
    assert data["auto_add"] == "true"
    assert data["all_lang"] == [config_mod.PLACEHOLDER_LANG]
    assert os.path.exists(cfg.config_json)


def test_load_keeps_existing_values_and_adds_new_keys(cfg):
    # a config written by 1.0.5, before sen_min_len/target_field existed
    write_raw(
        cfg,
        {
            "lang": "English",
            "all_lang": ["-- Select Language --", "English"],
            "text_color": "#ff0000",
            "word_color": "#00ff00",
            "word_html": "",
            "sen_html": "",
            "auto_add": "false",
            "open_all_sen_window": "true",
            "sen_contain_space": "true",
            "sen_len": "50",
            "num_of_sen": "3",
            "English": "/old/path/eng.db",
        },
    )

    data = cfg.load()

    assert data["lang"] == "English"
    assert data["text_color"] == "#ff0000"
    assert data["sen_len"] == "50"
    assert data["English"] == "/old/path/eng.db"
    # keys introduced later are filled in with defaults
    assert data["sen_min_len"] == "0"
    assert data["target_field"] == ""
    assert data["db_contain_pair"] == "false"


def test_load_survives_corrupt_config(cfg):
    cfg.ensure_dirs()
    with open(cfg.config_json, "w", encoding="utf-8") as f:
        f.write("{not json")

    data = cfg.load()
    assert data["auto_add"] == "true"


def test_db_path_accepts_legacy_absolute_path(cfg, tmp_path):
    legacy_db = tmp_path / "elsewhere" / "eng.db"
    legacy_db.parent.mkdir()
    legacy_db.write_text("")
    cfg.update(lang="English", all_lang=["English"], English=str(legacy_db))

    assert cfg.db_path(cfg.load()) == str(legacy_db)


def test_db_path_finds_db_after_addon_folder_moved(cfg):
    """A 1.0.6 config points at a path that no longer exists."""
    moved = os.path.join(cfg.lang_db_folder, "eng.db")
    open(moved, "w").close()
    cfg.update(
        lang="English",
        all_lang=["English"],
        English="/Users/someone-else/Anki2/addons21/1682655437/user_files/lang_db/eng.db",
    )

    assert cfg.db_path(cfg.load()) == moved


def test_db_path_none_for_placeholder_or_missing_file(cfg):
    data = cfg.load()
    assert cfg.db_path(data) is None

    cfg.update(lang="Gone", all_lang=["Gone"], Gone="gone.db")
    assert cfg.db_path(cfg.load()) is None


def test_add_language_stores_relative_name_and_dedupes(cfg):
    first = cfg.add_language("English", "/tmp/eng.db")
    second = cfg.add_language("English", "/tmp/eng2.db")

    data = cfg.load()
    assert first == "English"
    assert second == "English2"
    assert data["lang_db"]["English"] == "eng.db"
    assert data["lang_db"]["English2"] == "eng2.db"
    assert data["all_lang"].count("English") == 1


def test_a_language_named_like_a_setting_does_not_overwrite_it(cfg):
    """Databases used to be stored as top level keys."""
    db = os.path.join(cfg.lang_db_folder, "lang.db")
    open(db, "w").close()
    cfg.add_language("lang", db)
    cfg.update(lang="lang", sen_len="42")

    data = cfg.load()
    assert data["sen_len"] == "42"
    assert data["lang"] == "lang"
    assert cfg.db_path(data) == db


def test_remove_language_deletes_file_and_resets_selection(cfg):
    db = os.path.join(cfg.lang_db_folder, "eng.db")
    open(db, "w").close()
    cfg.add_language("English", db)
    cfg.update(lang="English")

    data = cfg.remove_language("English")

    assert "English" not in data
    assert "English" not in data["all_lang"]
    assert data["lang"] == config_mod.DEFAULT_CONFIG["lang"]
    assert not os.path.exists(db)


def test_remove_language_with_broken_path_does_not_raise(cfg):
    cfg.update(all_lang=["Ghost"], Ghost="/nowhere/ghost.db")
    data = cfg.remove_language("Ghost")
    assert "Ghost" not in data["all_lang"]


@pytest.mark.parametrize(
    "value,expected",
    [("true", True), ("false", False), (True, True), (False, False), (None, False),
     ("", False), ("TRUE", True), ("1", True)],
)
def test_as_bool(value, expected):
    assert config_mod.as_bool(value) is expected


@pytest.mark.parametrize(
    "value,expected",
    [("30", 30), (30, 30), ("", 7), (None, 7), ("abc", 7), (" 12 ", 12)],
)
def test_as_int(value, expected):
    assert config_mod.as_int(value, 7) == expected


def test_is_placeholder_lang():
    assert config_mod.is_placeholder_lang(" -- Select Language -- ")
    assert config_mod.is_placeholder_lang("")
    assert not config_mod.is_placeholder_lang("English")
