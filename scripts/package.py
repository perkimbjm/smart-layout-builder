"""Build ZIP plugin yang siap di-install ke QGIS Plugin Manager.

Output: dist/smart_layout_builder-<version>.zip dengan satu folder top-level
`smart_layout_builder/` (sesuai ekspektasi Plugin Repo).

Pakai:  python scripts/package.py
"""

from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "slb"
DIST = ROOT / "dist"
PKG_DIRNAME = "smart_layout_builder"

EXCLUDE_DIRS = {"__pycache__", "tests"}
EXCLUDE_SUFFIX = {".pyc", ".pyo"}


def _read_version() -> str:
    text = (SRC / "version.py").read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not m:
        sys.exit("ERROR: __version__ tidak ditemukan di slb/version.py")
    return m.group(1)


def _check_metadata_version(version: str) -> None:
    meta = (SRC / "metadata.txt").read_text(encoding="utf-8")
    m = re.search(r"^version=(.+)$", meta, flags=re.MULTILINE)
    if not m:
        sys.exit("ERROR: 'version=' tidak ada di metadata.txt")
    if m.group(1).strip() != version:
        sys.exit(
            f"ERROR: versi tidak cocok — version.py={version} "
            f"metadata.txt={m.group(1).strip()}"
        )


def _iter_files(base: Path):
    for path in base.rglob("*"):
        if any(part in EXCLUDE_DIRS for part in path.relative_to(base).parts):
            continue
        if path.suffix in EXCLUDE_SUFFIX:
            continue
        if path.is_file():
            yield path


def main() -> None:
    version = _read_version()
    _check_metadata_version(version)

    DIST.mkdir(exist_ok=True)
    out_zip = DIST / f"{PKG_DIRNAME}-{version}.zip"
    if out_zip.exists():
        out_zip.unlink()

    count = 0
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in _iter_files(SRC):
            arc = Path(PKG_DIRNAME) / f.relative_to(SRC)
            zf.write(f, arc.as_posix())
            count += 1

    print(f"OK: {out_zip}  ({count} files, v{version})")


if __name__ == "__main__":
    main()
