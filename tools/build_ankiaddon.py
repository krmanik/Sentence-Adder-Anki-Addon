#!/usr/bin/env python3
"""Package src/ into a .ankiaddon file ready for AnkiWeb.

    python tools/build_ankiaddon.py [-o dist]

A .ankiaddon file is a zip of the *contents* of the add-on folder: manifest.json
and __init__.py sit at the top level, the folder itself is not included.
AnkiWeb rejects archives containing __pycache__, and user_files holds the
sentence databases of whoever built the file, so both are left out.

https://addon-docs.ankiweb.net/sharing.html
"""

import argparse
import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")

EXCLUDED_DIRS = {"__pycache__", "user_files", ".idea"}
EXCLUDED_FILES = {"meta.json", ".DS_Store"}
EXCLUDED_SUFFIXES = (".pyc", ".pyo", ".orig", ".rej")


def wanted_files(src=SRC):
    """Every file that belongs in the archive, as (full path, name in zip)."""
    found = []
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        for name in sorted(filenames):
            if name in EXCLUDED_FILES or name.endswith(EXCLUDED_SUFFIXES):
                continue
            full = os.path.join(dirpath, name)
            found.append((full, os.path.relpath(full, src).replace(os.sep, "/")))
    return found


def read_manifest(src=SRC):
    with open(os.path.join(src, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    for key in ("package", "name"):
        if not manifest.get(key):
            raise ValueError("manifest.json needs a '%s'" % key)
    return manifest


def build(src=SRC, out_dir=None):
    """Write the .ankiaddon file, returning its path."""
    manifest = read_manifest(src)
    files = wanted_files(src)

    names = [name for _, name in files]
    if "manifest.json" not in names:
        raise ValueError("manifest.json must sit next to __init__.py in %s" % src)
    if "__init__.py" not in names:
        raise ValueError("__init__.py is missing from %s" % src)

    out_dir = out_dir or os.path.join(ROOT, "dist")
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    version = manifest.get("human_version") or manifest.get("version") or "dev"
    out_path = os.path.join(out_dir, "%s-%s.ankiaddon" % (manifest["package"], version))

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for full, name in files:
            zf.write(full, name)

    return out_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out-dir", help="where to write the file (default: dist)")
    args = parser.parse_args(argv)

    out_path = build(out_dir=args.out_dir)
    with zipfile.ZipFile(out_path) as zf:
        names = zf.namelist()
    print("%s (%d files, %d KB)" % (
        os.path.relpath(out_path, ROOT), len(names),
        os.path.getsize(out_path) // 1024))
    for name in names:
        print("  " + name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
