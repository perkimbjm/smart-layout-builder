"""Installer preset bawaan (first-run copy).

Menyalin file di ``slb/resources/builtin_presets/*.json`` ke folder preset user
(``<profil>/SLB/presets/``) bila belum ada. File milik user yang sudah ada
**tidak pernah** ditimpa — pembaruan plugin di versi berikutnya tidak akan
mengganggu modifikasi user (database-schema.md §5: "updates to the bundled
files in newer plugin versions do not overwrite user copies").

Idempoten: pemanggilan kedua = no-op. Dipanggil sekali dari
``plugin.initGui()`` (api-design.md §10/§13); biaya ~5 ms (dua kali ``stat`` +
copy bila perlu).

Kegagalan I/O di-log lalu di-swallow — defaults installer tidak boleh
membatalkan ``initGui``. Bila bundled dir tidak ada (paket rusak), juga
di-log dan return 0, biarkan plugin tetap loadable.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from . import repository as repomod

log = logging.getLogger("slb.presets.defaults")


def bundled_dir() -> Path:
    """Folder bundled preset di paket plugin (read-only).

    Modul-level supaya test bisa monkey-patch satu titik (pola yang sama
    dipakai untuk ``repository.presets_dir``).
    """
    return Path(__file__).resolve().parent.parent / "resources" / "builtin_presets"


def ensure_defaults_installed() -> int:
    """Salin bundled preset ke folder user bila belum ada. Return jumlah file
    yang disalin (0 bila semua sudah terpasang).

    Aturan:
    - File user yang sudah ada (cek by nama file) **tidak ditimpa**.
    - Hanya `*.json` di bundled dir yang dipertimbangkan.
    - Idempoten; aman dipanggil tiap ``initGui``.
    - Kegagalan I/O per-file di-log dan dilewati (tidak menggagalkan instal
      file lain).
    """
    src_dir = bundled_dir()
    if not src_dir.is_dir():
        log.warning("Folder bundled preset tidak ditemukan: %s", src_dir)
        return 0

    dst_dir = repomod.presets_dir()
    copied = 0
    for src in sorted(src_dir.glob("*.json")):
        dst = dst_dir / src.name
        if dst.exists():
            continue
        try:
            shutil.copyfile(src, dst)
        except OSError as exc:  # filesystem penuh / izin / dll.
            log.warning("Gagal menyalin preset %s ke %s: %s", src.name, dst, exc)
            continue
        copied += 1
        log.info("Preset bawaan terinstal: %s", dst.name)
    return copied
