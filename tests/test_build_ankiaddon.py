"""The packaged .ankiaddon has to match what AnkiWeb accepts."""

import importlib.util
import json
import os
import pathlib
import sys
import zipfile

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "build_ankiaddon", ROOT / "tools" / "build_ankiaddon.py")
build_ankiaddon = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = build_ankiaddon
spec.loader.exec_module(build_ankiaddon)


@pytest.fixture
def built(tmp_path):
    path = build_ankiaddon.build(out_dir=str(tmp_path))
    with zipfile.ZipFile(path) as zf:
        yield path, zf.namelist(), zf


def test_the_add_on_folder_itself_is_not_in_the_zip(built):
    _, names, _ = built

    assert "manifest.json" in names
    assert "__init__.py" in names
    assert not any(name.startswith("src/") for name in names)


def test_every_module_and_the_icon_are_packaged(built):
    _, names, _ = built

    for name in ("__init__.py", "config.py", "editor.py", "batch_edit.py",
                 "sentences.py", "tsv_import.py", "utils.py", "icon.png",
                 "settings_icon.png"):
        assert name in names


def test_nothing_ankiweb_rejects_is_packaged(built):
    _, names, _ = built

    assert not [n for n in names if "__pycache__" in n or n.endswith(".pyc")]
    # the databases of whoever builds the file must not ship with it
    assert not [n for n in names if n.startswith("user_files")]
    assert "meta.json" not in names


def test_manifest_in_the_zip_is_valid_for_anki(built):
    _, _, zf = built
    manifest = json.loads(zf.read("manifest.json"))

    assert manifest["package"] == "sentence-adder"
    assert manifest["name"]
    # min_point_version 50 means Anki 2.1.50; newer releases report 250904
    assert manifest["min_point_version"] == 50


def test_file_name_carries_the_version(built):
    path, _, _ = built
    assert os.path.basename(path) == "sentence-adder-1.1.0.ankiaddon"


def test_the_version_in_the_manifest_matches_the_code(built):
    _, _, zf = built
    manifest = json.loads(zf.read("manifest.json"))
    source = zf.read("__init__.py").decode("utf-8")

    assert 'anki_addon_version = "%s"' % manifest["human_version"] in source


def test_build_refuses_a_folder_without_a_manifest(tmp_path):
    (tmp_path / "__init__.py").write_text("")
    with pytest.raises(Exception):
        build_ankiaddon.build(src=str(tmp_path), out_dir=str(tmp_path / "dist"))
