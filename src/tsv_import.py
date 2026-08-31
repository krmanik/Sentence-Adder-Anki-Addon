# -*- coding: utf-8 -*-
##############################################
##                                          ##
##              Sentence Adder              ##
##                                          ##
##          Copyright (c) Mani 2021         ##
##      (https://github.com/krmanik)        ##
##                                          ##
##############################################

"""Building a language database from a tsv file.

Imports nothing from ``aqt``/``anki`` so it can be unit tested.
"""

import csv
import os
import sqlite3


def read_row(row, is_pair, from_tatoeba):
    """Pick the sentence columns out of one tsv row, or None to skip the row.

    Tatoeba sentence exports are ``id \t language \t text`` and their sentence
    pair exports are ``id \t sentence \t id \t translation``.  With
    ``from_tatoeba`` off the columns are read as ``sentence`` /
    ``sentence \t translation``, which is what a hand made tsv looks like.
    """
    if from_tatoeba:
        if is_pair:
            if len(row) != 4:
                return None
            sentence, translation = row[1], row[3]
        else:
            if len(row) < 3:
                return None
            sentence, translation = row[2], None
    else:
        if not row:
            return None
        if is_pair:
            if len(row) < 2:
                return None
            sentence, translation = row[0], row[1]
        else:
            sentence, translation = row[0], None

    sentence = (sentence or "").strip()
    if not sentence:
        return None
    if is_pair:
        return (sentence, (translation or "").strip())
    return (sentence,)


def create_db(db_file, is_pair):
    conn = sqlite3.connect(db_file)
    curs = conn.cursor()
    if is_pair:
        curs.execute(
            "CREATE TABLE examples (id INTEGER PRIMARY KEY, sentence TEXT, translation TEXT);")
    else:
        curs.execute(
            "CREATE TABLE examples (id INTEGER PRIMARY KEY, sentence TEXT);")
    conn.commit()
    return conn


def import_tsv(tsv_path, db_file, is_pair, from_tatoeba, on_progress=None, batch_size=20000):
    """Import ``tsv_path`` into a new ``db_file``, returning the row count.

    The database file is removed again when the import fails or finds nothing,
    so a failed attempt never leaves a half written language behind.
    """
    if not os.path.exists(tsv_path):
        raise IOError("File not found: %s" % tsv_path)

    conn = create_db(db_file, is_pair)
    count = 0
    try:
        if is_pair:
            sql = "INSERT INTO examples (sentence, translation) VALUES (?,?);"
        else:
            sql = "INSERT INTO examples (sentence) VALUES (?);"

        pending = []
        with open(tsv_path, "r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
            for row in reader:
                values = read_row(row, is_pair, from_tatoeba)
                if values is None:
                    continue
                pending.append(values)
                count += 1
                if len(pending) >= batch_size:
                    conn.executemany(sql, pending)
                    pending = []
                    if on_progress:
                        on_progress(count)
        if pending:
            conn.executemany(sql, pending)
        conn.commit()
    except Exception:
        conn.close()
        _remove(db_file)
        raise
    conn.close()

    if count == 0:
        _remove(db_file)
    return count


def _remove(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
