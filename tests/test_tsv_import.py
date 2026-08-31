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


# choosing columns from the file ###########################################


TATOEBA_PAIRS = [
    "1\t我們試試看！\t1176908\tLet's try!",
    "2\t我该去睡觉了。\t1277\tI have to go to sleep.",
]


def test_the_reported_tatoeba_pair_file_is_read_without_being_described(tmp_path):
    """Ticking only one of the two old checkboxes stored the id column."""
    tsv = write_tsv(tmp_path, "cmn.tsv", TATOEBA_PAIRS)
    db_file = str(tmp_path / "cmn.db")

    count = tsv_import.import_tsv(tsv, db_file)

    assert count == 2
    assert rows(db_file, "sentence, translation")[0] == ("我們試試看！", "Let's try!")


@pytest.mark.parametrize(
    "lines,expected",
    [
        (TATOEBA_PAIRS, {"sentence": 1, "translation": 3, "id": 0}),
        (["1\tcmn\t我們試試看！", "2\tcmn\t我该去睡觉了。"],
         {"sentence": 2, "translation": None, "id": None}),
        (["我們試試看！", "我该去睡觉了。"],
         {"sentence": 0, "translation": None, "id": None}),
        (["我們試試看！\tLet's try!", "我该去睡觉了。\tI have to go."],
         {"sentence": 0, "translation": 1, "id": None}),
        # sentence id, sentence, translation (a "sentences with audio" export)
        (["332421\t我們試試看！\tLet's try!", "1277\t我该去睡觉了。\tI have to go."],
         {"sentence": 1, "translation": 2, "id": 0}),
    ],
)
def test_layout_detection(tmp_path, lines, expected):
    tsv = write_tsv(tmp_path, "detect.tsv", lines)
    assert tsv_import.detect_file(tsv) == expected


def test_preview_returns_the_first_rows_and_the_layout(tmp_path):
    tsv = write_tsv(tmp_path, "cmn.tsv", TATOEBA_PAIRS * 20)

    preview, layout = tsv_import.preview_file(tsv, limit=5)

    assert len(preview) == 5
    assert preview[0] == ["1", "我們試試看！", "1176908", "Let's try!"]
    assert layout["sentence"] == 1


def test_columns_chosen_by_hand_win_over_detection(tmp_path):
    """What the user picks in the preview is what gets imported."""
    tsv = write_tsv(tmp_path, "cmn.tsv", TATOEBA_PAIRS)
    db_file = str(tmp_path / "cmn.db")

    count = tsv_import.import_tsv(
        tsv, db_file, layout={"sentence": 3, "translation": 1, "id": None})

    assert count == 2
    assert rows(db_file, "sentence, translation")[0] == ("Let's try!", "我們試試看！")


def test_the_tatoeba_id_is_kept_when_the_column_is_chosen(tmp_path):
    tsv = write_tsv(tmp_path, "cmn.tsv", TATOEBA_PAIRS)
    db_file = str(tmp_path / "cmn.db")

    tsv_import.import_tsv(tsv, db_file)

    assert rows(db_file, "sentence, tatoeba_id")[0] == ("我們試試看！", 1)


def test_a_database_without_an_id_column_has_no_id_column(tmp_path):
    tsv = write_tsv(tmp_path, "own.tsv", ["I like cats."])
    db_file = str(tmp_path / "own.db")

    tsv_import.import_tsv(tsv, db_file)

    con = sqlite3.connect(db_file)
    columns = [row[1] for row in con.execute("PRAGMA table_info(examples)")]
    con.close()
    assert columns == ["id", "sentence"]


def test_a_byte_order_mark_does_not_end_up_in_the_first_sentence(tmp_path):
    path = tmp_path / "bom.tsv"
    path.write_text("I like cats.\nShe reads.\n", encoding="utf-8-sig")
    db_file = str(tmp_path / "bom.db")

    tsv_import.import_tsv(str(path), db_file)

    assert rows(db_file)[0] == ("I like cats.",)


def test_rows_too_short_for_the_chosen_columns_are_skipped(tmp_path):
    tsv = write_tsv(tmp_path, "ragged.tsv", [
        "1\t我們試試看！\t1176908\tLet's try!",
        "2\t短い",
    ])
    db_file = str(tmp_path / "ragged.db")

    assert tsv_import.import_tsv(tsv, db_file) == 1


def test_describe_layout_lists_every_role_with_an_example():
    layout = {"sentence": 1, "translation": 3, "id": 0}
    row = ["1", "我們試試看！", "1176908", "Let's try!"]

    assert tsv_import.describe_layout(layout, row) == [
        ("Sentence", "Column 2", "我們試試看！"),
        ("Translation", "Column 4", "Let's try!"),
        ("Tatoeba id", "Column 1", "1"),
    ]


def test_describe_layout_marks_columns_that_are_not_used():
    described = tsv_import.describe_layout(
        {"sentence": 0, "translation": None, "id": None}, ["I like cats."])

    assert described[1] == ("Translation", "not used", "")
    assert described[2] == ("Tatoeba id", "not used", "")


def test_first_usable_row_skips_lines_the_layout_cannot_read():
    layout = {"sentence": 1, "translation": None, "id": None}
    rows = [["only one column"], ["1", "I like cats."]]

    assert tsv_import.first_usable_row(rows, layout) == ["1", "I like cats."]
    assert tsv_import.first_usable_row([["short"]], layout) is None
