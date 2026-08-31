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
import re
import sqlite3

SAMPLE_ROWS = 50

_NUMERIC_RE = re.compile(r"^\d+$")
_LANG_CODE_RE = re.compile(r"^[a-z]{2,4}$")


def open_tsv(path):
    """Open a tsv, tolerating a byte order mark and stray bytes."""
    return open(path, "r", encoding="utf-8-sig", errors="replace", newline="")


def sample_rows(path, limit=SAMPLE_ROWS):
    rows = []
    with open_tsv(path) as f:
        for row in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if any(cell.strip() for cell in row):
                rows.append(row)
            if len(rows) >= limit:
                break
    return rows


def detect_layout(rows):
    """Which column holds what, as ``{"sentence", "translation", "id"}``.

    ``translation`` and ``id`` are None when the file has no such column.  The
    id is the tatoeba sentence id, taken from the numeric column in front of
    the sentence, which is where every tatoeba export keeps it.
    """
    sentence, translation = detect_columns(rows)

    rows = [row for row in rows if any(cell.strip() for cell in row)]
    id_column = None
    if sentence > 0:
        candidate = sentence - 1
        values = [row[candidate].strip() for row in rows if len(row) > candidate]
        filled = [value for value in values if value]
        if filled and all(_NUMERIC_RE.match(value) for value in filled):
            id_column = candidate

    return {"sentence": sentence, "translation": translation, "id": id_column}


ROLE_LABELS = [("sentence", "Sentence"), ("translation", "Translation"),
               ("id", "Tatoeba id")]


def describe_layout(layout, row=None):
    """What will be imported, as ``[(role, column label, example value)]``.

    Shown for confirmation before a database is written, so nothing is
    imported from a column the user did not mean.
    """
    described = []
    for key, label in ROLE_LABELS:
        column = layout.get(key)
        if column is None:
            described.append((label, "not used", ""))
            continue
        example = ""
        if row is not None and column < len(row):
            example = row[column].strip()
        described.append((label, "Column %d" % (column + 1), example))
    return described


def first_usable_row(rows, layout):
    """The first row the layout can actually read, or None."""
    for row in rows:
        if read_columns(row, layout) is not None:
            return row
    return None


def preview_file(path, limit=20):
    """First rows of ``path`` plus the detected layout, for the user to check."""
    rows = sample_rows(path, max(limit, SAMPLE_ROWS))
    return rows[:limit], detect_layout(rows)


def detect_columns(rows):
    """Work out which columns hold the sentence and the translation.

    Returns ``(sentence_column, translation_column_or_None)``.

    Tatoeba files carry the sentence in a different column depending on which
    export they come from, and getting that wrong stored the id column as the
    sentences, so every later lookup found nothing.  Rather than asking the
    user to describe the file, the columns are read off the file itself:
    columns that are all digits are ids, a column of short lowercase codes is
    the language, and what is left is text.
    """
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        return 0, None

    widths = [len(row) for row in rows]
    # the most common width, and the widest of those when it is a tie, so a
    # file with a couple of short lines is still read by its real layout
    width = max(set(widths), key=lambda w: (widths.count(w), w))
    rows = [row for row in rows if len(row) == width]
    if not rows:
        return 0, None

    text_columns = []
    for column in range(width):
        values = [row[column].strip() for row in rows]
        filled = [value for value in values if value]
        if not filled:
            continue
        if all(_NUMERIC_RE.match(value) for value in filled):
            continue  # an id
        if all(_LANG_CODE_RE.match(value) for value in filled):
            continue  # a language code such as cmn or eng
        text_columns.append(column)

    if not text_columns:
        return 0, None
    if len(text_columns) == 1:
        return text_columns[0], None
    return text_columns[0], text_columns[1]


def detect_file(path):
    """The layout of ``path``, as :func:`detect_layout` returns it."""
    return detect_layout(sample_rows(path))


def columns_for(is_pair, from_tatoeba):
    """The fixed column layout behind the old two checkboxes."""
    if from_tatoeba:
        return (1, 3) if is_pair else (2, None)
    return (0, 1) if is_pair else (0, None)


def read_columns(row, layout):
    """Pick the wanted columns out of one row, or None to skip the row.

    Values come back in the order the table stores them: sentence, then the
    translation and the tatoeba id when the layout has them.
    """
    if isinstance(layout, dict):
        sentence_column = layout["sentence"]
        translation_column = layout.get("translation")
        id_column = layout.get("id")
    else:  # (sentence, translation), as earlier versions passed it
        sentence_column, translation_column = layout
        id_column = None

    needed = max(column for column in
                 (sentence_column, translation_column, id_column)
                 if column is not None)
    if len(row) <= needed:
        return None

    sentence = (row[sentence_column] or "").strip()
    if not sentence:
        return None

    values = [sentence]
    if translation_column is not None:
        values.append((row[translation_column] or "").strip())
    if id_column is not None:
        value = (row[id_column] or "").strip()
        values.append(int(value) if _NUMERIC_RE.match(value) else None)
    return tuple(values)


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


def table_columns(layout):
    """The example table's columns for ``layout``, in insert order."""
    columns = ["sentence"]
    if layout.get("translation") is not None:
        columns.append("translation")
    if layout.get("id") is not None:
        columns.append("tatoeba_id")
    return columns


def create_db(db_file, layout):
    """Create the examples table.  ``layout`` may be the old is_pair flag."""
    if not isinstance(layout, dict):
        layout = {"sentence": 0, "translation": 0 if layout else None, "id": None}

    definitions = ["id INTEGER PRIMARY KEY", "sentence TEXT"]
    if layout.get("translation") is not None:
        definitions.append("translation TEXT")
    if layout.get("id") is not None:
        definitions.append("tatoeba_id INTEGER")

    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE examples (%s);" % ", ".join(definitions))
    conn.commit()
    return conn


def import_tsv(tsv_path, db_file, is_pair=None, from_tatoeba=None, layout=None,
               on_progress=None, batch_size=20000):
    """Import ``tsv_path`` into a new ``db_file``, returning the row count.

    ``layout`` is what the create dialog shows in its preview.  Without one,
    ``is_pair``/``from_tatoeba`` select the fixed layouts of earlier versions,
    and with neither the columns are detected from the file.

    The database file is removed again when the import fails or finds nothing,
    so a failed attempt never leaves a half written language behind.
    """
    if not os.path.exists(tsv_path):
        raise IOError("File not found: %s" % tsv_path)

    if layout is None:
        if is_pair is None and from_tatoeba is None:
            layout = detect_file(tsv_path)
        else:
            sentence, translation = columns_for(bool(is_pair), bool(from_tatoeba))
            layout = {"sentence": sentence, "translation": translation, "id": None}

    columns = table_columns(layout)
    conn = create_db(db_file, layout)
    count = 0
    try:
        sql = "INSERT INTO examples (%s) VALUES (%s);" % (
            ", ".join(columns), ", ".join("?" * len(columns)))

        pending = []
        with open_tsv(tsv_path) as f:
            reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
            for row in reader:
                values = read_columns(row, layout)
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
