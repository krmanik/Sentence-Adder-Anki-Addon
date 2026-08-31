import os
import sqlite3

import pytest

from conftest import load

tsv_import = load("tsv_import")


def write_tsv(tmp_path, name, lines):
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def rows(db_file, columns="sentence"):
    con = sqlite3.connect(db_file)
    try:
        return con.execute("select %s from examples order by id" % columns).fetchall()
    finally:
        con.close()


def test_read_row_tatoeba_sentences():
    assert tsv_import.read_row(["1", "eng", "Hello."], False, True) == ("Hello.",)
    # short/ragged rows are skipped instead of raising
    assert tsv_import.read_row(["1", "eng"], False, True) is None
    assert tsv_import.read_row([], False, True) is None


def test_read_row_tatoeba_pairs():
    row = ["1", "私は猫が好きです。", "2", "I like cats."]
    assert tsv_import.read_row(row, True, True) == ("私は猫が好きです。", "I like cats.")
    assert tsv_import.read_row(["1", "a", "2"], True, True) is None


def test_read_row_own_tsv():
    assert tsv_import.read_row(["Hello."], False, False) == ("Hello.",)
    assert tsv_import.read_row(["Hola.", "Hello."], True, False) == ("Hola.", "Hello.")
    assert tsv_import.read_row(["only one column"], True, False) is None
    assert tsv_import.read_row(["   "], False, False) is None


def test_import_tatoeba_export(tmp_path):
    tsv = write_tsv(tmp_path, "eng.tsv", [
        "1\teng\tI like cats.",
        "2\teng\tShe reads a book.",
        "broken line without tabs",
        "3\teng\t   ",
    ])
    db_file = str(tmp_path / "eng.db")

    count = tsv_import.import_tsv(tsv, db_file, is_pair=False, from_tatoeba=True)

    assert count == 2
    assert rows(db_file) == [("I like cats.",), ("She reads a book.",)]


def test_import_pairs_creates_translation_column(tmp_path):
    tsv = write_tsv(tmp_path, "jpn.tsv", [
        "1\t私は猫が好きです。\t2\tI like cats.",
        "3\t本を読む。\t4\tRead a book.",
    ])
    db_file = str(tmp_path / "jpn.db")

    count = tsv_import.import_tsv(tsv, db_file, is_pair=True, from_tatoeba=True)

    assert count == 2
    assert rows(db_file, "sentence, translation")[0] == ("私は猫が好きです。", "I like cats.")


def test_import_own_tsv_without_tatoeba_columns(tmp_path):
    tsv = write_tsv(tmp_path, "mine.tsv", ["My own sentence.", "Another one."])
    db_file = str(tmp_path / "mine.db")

    assert tsv_import.import_tsv(tsv, db_file, is_pair=False, from_tatoeba=False) == 2
    assert rows(db_file) == [("My own sentence.",), ("Another one.",)]


def test_quotes_and_apostrophes_are_kept_verbatim(tmp_path):
    tsv = write_tsv(tmp_path, "eng.tsv", [
        '1\teng\tHe said "hi".',
        "2\teng\tIt's Tom's book.",
    ])
    db_file = str(tmp_path / "eng.db")

    tsv_import.import_tsv(tsv, db_file, is_pair=False, from_tatoeba=True)

    assert rows(db_file) == [('He said "hi".',), ("It's Tom's book.",)]


def test_wrong_format_leaves_no_database_behind(tmp_path):
    """Picking 'downloaded from tatoeba' for an own tsv used to create an empty db."""
    tsv = write_tsv(tmp_path, "mine.tsv", ["My own sentence.", "Another one."])
    db_file = str(tmp_path / "mine.db")

    assert tsv_import.import_tsv(tsv, db_file, is_pair=False, from_tatoeba=True) == 0
    assert not os.path.exists(db_file)


def test_missing_file_raises_and_leaves_no_database(tmp_path):
    db_file = str(tmp_path / "gone.db")
    with pytest.raises(IOError):
        tsv_import.import_tsv(str(tmp_path / "gone.tsv"), db_file, False, True)
    assert not os.path.exists(db_file)


def test_progress_callback_is_batched(tmp_path):
    tsv = write_tsv(tmp_path, "eng.tsv", ["%d\teng\tSentence %d." % (i, i) for i in range(25)])
    db_file = str(tmp_path / "eng.db")
    seen = []

    count = tsv_import.import_tsv(
        tsv, db_file, False, True, on_progress=seen.append, batch_size=10)

    assert count == 25
    assert seen == [10, 20]
