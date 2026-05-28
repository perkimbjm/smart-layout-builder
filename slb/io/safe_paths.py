"""Helper filesystem: lokasi data user, atomic write, sanitasi nama file.

Lihat database-schema.md (storage strategy) dan api-design.md §11.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_FORBIDDEN = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def user_dir() -> Path:
    """Folder data SLB di profil QGIS aktif (dibuat bila belum ada).

    Pakai folder profil QGIS bila tersedia; fallback ke ~/.qgis/SLB untuk
    konteks tanpa QGIS (mis. unit test).
    """
    base: Path | None = None
    try:
        from qgis.core import QgsApplication

        settings_path = QgsApplication.qgisSettingsDirPath()
        if settings_path:
            base = Path(settings_path) / "SLB"
    except Exception:  # noqa: BLE001 - QGIS tidak tersedia
        base = None
    if base is None:
        base = Path.home() / ".qgis" / "SLB"
    base.mkdir(parents=True, exist_ok=True)
    return base


def ensure_dir(path: Path) -> Path:
    """mkdir(parents, exist_ok); kembalikan path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def atomic_write(path: Path, data: bytes | str) -> None:
    """Tulis ke file sementara lalu os.replace -> mencegah file korup/parsial."""
    path = Path(path)
    ensure_dir(path.parent)
    tmp = path.with_name(path.name + ".tmp")
    payload = data.encode("utf-8") if isinstance(data, str) else data
    with open(tmp, "wb") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def safe_filename(name: str) -> str:
    """Sanitasi string untuk dipakai sebagai nama file. Maks 200 char."""
    cleaned = _FORBIDDEN.sub("_", str(name)).strip().strip(".")
    return (cleaned or "unnamed")[:200]
