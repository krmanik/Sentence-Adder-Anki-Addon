# -*- coding: utf-8 -*-
##############################################
##                                          ##
##              Sentence Adder              ##
##                                          ##
##          Copyright (c) Mani 2021         ##
##      (https://github.com/krmanik)        ##
##                                          ##
##############################################

"""Configuration storage for the add-on.

This module deliberately imports nothing from ``aqt``/``anki`` so that it can be
unit tested outside of Anki.

Every value is stored the way older versions of the add-on stored it (booleans
as the strings ``"true"``/``"false"``, numbers as strings), so an existing
``config.json`` keeps working untouched.
"""

import json
import os

PLACEHOLDER_LANG = "-- Select Language --"

DEFAULT_CONFIG = {
    "lang": " -- Select Language -- ",
    "all_lang": [PLACEHOLDER_LANG],
    # language name -> database file name; up to 1.0.6 this was kept as
    # top level keys, where a language called "lang" or "sen_len" overwrote
    # the setting of the same name
    "lang_db": {},
    "text_color": "",
    "word_color": "",
    "word_html": "",
    "sen_html": "",
    "auto_add": "true",
    "open_all_sen_window": "false",
    "sen_contain_space": "false",
    "db_contain_pair": "false",
    "sen_len": "30",
    "num_of_sen": "2",
    # added in 1.1.0
    "sen_min_len": "0",
    "target_field": "",
    "target_trans_field": "",
}


def as_bool(value, default=False):
    """Read a config flag that may be a string, a bool or missing."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def as_int(value, default):
    """Read a numeric config value that may be a string, a float or garbage."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def is_placeholder_lang(lang):
    return not lang or lang.strip() == PLACEHOLDER_LANG


class Config:
    """Reads and writes ``user_files/config.json``.

    The config is re-read from disk on every access so that changes made in the
    options dialog take effect without restarting Anki.
    """

    def __init__(self, user_folder):
        self.user_folder = user_folder
        self.config_json = os.path.join(user_folder, "config.json")
        self.lang_db_folder = os.path.join(user_folder, "lang_db")

    def ensure_dirs(self):
        for path in (self.user_folder, self.lang_db_folder):
            if not os.path.exists(path):
                os.makedirs(path)

    def load(self):
        """Return the config, filling in any key a previous version didn't have."""
        data = {}
        if os.path.exists(self.config_json):
            try:
                with open(self.config_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (ValueError, OSError):
                # A corrupt config must not stop the add-on from loading.
                data = {}
        if not isinstance(data, dict):
            data = {}

        merged = dict(DEFAULT_CONFIG)
        merged["all_lang"] = list(DEFAULT_CONFIG["all_lang"])
        merged["lang_db"] = {}
        merged.update(data)

        if not isinstance(merged.get("all_lang"), list):
            merged["all_lang"] = list(DEFAULT_CONFIG["all_lang"])
        if not isinstance(merged.get("lang_db"), dict):
            merged["lang_db"] = {}

        if merged != data:
            self.save(merged)
        return merged

    def save(self, data):
        self.ensure_dirs()
        with open(self.config_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def update(self, **values):
        data = self.load()
        data.update(values)
        self.save(data)
        return data

    # language databases ####################################################

    def db_path(self, config, lang=None):
        """Resolve the database file for ``lang``.

        Up to 1.0.6 an absolute path was stored, which broke whenever the
        profile, the add-on folder or the machine changed.  New entries store a
        bare file name; both forms are accepted and the file name is always
        looked up in the current ``lang_db`` folder first.
        """
        if lang is None:
            lang = config.get("lang", "")
        if is_placeholder_lang(lang):
            return None

        stored = config.get("lang_db", {}).get(lang)
        if not stored and lang not in DEFAULT_CONFIG:
            # written by 1.0.6 or earlier, which stored the path at top level
            stored = config.get(lang)
        if not stored or not isinstance(stored, str):
            return None

        in_folder = os.path.join(self.lang_db_folder, os.path.basename(stored))
        if os.path.exists(in_folder):
            return in_folder
        if os.path.exists(stored):
            return stored
        return None

    def add_language(self, lang_name, db_file_name):
        """Register a language, returning the (possibly de-duplicated) name."""
        config = self.load()
        name = lang_name
        suffix = 1
        while name in config["all_lang"]:
            suffix += 1
            name = "%s%d" % (lang_name, suffix)

        config["all_lang"].append(name)
        config["lang_db"][name] = os.path.basename(db_file_name)
        self.save(config)
        return name

    def remove_language(self, lang_name):
        """Forget a language and delete its database file if we still find it."""
        config = self.load()
        path = self.db_path(config, lang_name)

        config["lang_db"].pop(lang_name, None)
        if lang_name not in DEFAULT_CONFIG:
            config.pop(lang_name, None)
        if lang_name in config["all_lang"]:
            config["all_lang"].remove(lang_name)
        if config.get("lang") == lang_name:
            config["lang"] = DEFAULT_CONFIG["lang"]
        self.save(config)

        if path and os.path.exists(path):
            os.remove(path)
        return config
