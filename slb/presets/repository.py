"""CRUD preset berbasis file JSON.

Storage: ``<profil QGIS>/SLB/presets/<safe_filename(name)>.json`` — satu file
per preset, JSON polos, idiom yang sama dipakai logs/history (lihat
``docs/database-schema.md`` §3–4 & ``docs/architecture.md`` §5.5 / §6.3).

Validasi sengaja minimal (lihat ``docs/api-design.md`` §9): wajib punya key
``name``/``paper``/``orientation``/``items`` dan ``schema`` (bila ada) harus
``1`` — selebihnya dibiarkan lewat agar bidang ``style``/``binding`` per-item
forward-compatible. Pelanggaran → :class:`~slb.errors.PresetError` (UI tinggal
menampilkan ``str(e)`` + ``e.hint``).

Bertumpu pada :func:`slb.io.safe_paths.atomic_write` agar tulis-tukar JSON tak
pernah meninggalkan file korup/parsial, dan :func:`safe_filename` untuk
memastikan ``name`` apapun (termasuk berisi karakter terlarang Windows) tetap
menghasilkan nama file yang sah.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from ..errors import PresetError
from ..io.safe_paths import atomic_write, ensure_dir, safe_filename, user_dir

#: Versi schema yang didukung saat ini (lihat ``database-schema.md`` §11 untuk
#: rencana migrator forward bila kelak dibutuhkan).
_SCHEMA = 1

#: Field wajib di setiap file preset (api-design.md §9).
_REQUIRED_KEYS = ("name", "paper", "orientation", "items")


class PresetMeta(TypedDict):
    """Metadata ringkas tiap preset untuk dropdown UI (api-design.md §9).

    ``name`` di sini adalah **kunci** preset (stem nama file) yang dapat
    diumpankan kembali ke :func:`load_preset`/:func:`delete_preset`. Nama
    tampilan ("Classic A4 Portrait") ada di dalam dict hasil load.
    """

    name: str
    path: Path
    paper: str
    orientation: str


def presets_dir() -> Path:
    """Folder preset user (``<profil>/SLB/presets/``); dibuat bila belum ada."""
    return ensure_dir(user_dir() / "presets")


def _preset_path(name: str) -> Path:
    """Path JSON untuk ``name`` (kunci preset), via :func:`safe_filename`."""
    return presets_dir() / f"{safe_filename(name)}.json"


def _validate(data: object) -> dict:
    """Validasi minimal sebuah dict preset (api-design.md §9).

    Mengembalikan dict yang sama (tanpa mutasi) bila lolos; kalau tidak,
    raise :class:`PresetError` dengan hint actionable.
    """
    if not isinstance(data, dict):
        raise PresetError(
            "Isi preset bukan objek JSON.",
            hint="File preset harus berupa objek (dict) JSON di tingkat akar.",
        )
    missing = [key for key in _REQUIRED_KEYS if key not in data]
    if missing:
        raise PresetError(
            f"Preset kehilangan field wajib: {', '.join(missing)}.",
            hint="Field wajib: name, paper, orientation, items.",
        )
    schema = data.get("schema", _SCHEMA)
    if schema != _SCHEMA:
        raise PresetError(
            f"Versi schema preset {schema!r} tidak didukung.",
            hint=f"SLB versi ini hanya membaca schema={_SCHEMA}.",
        )
    return data


def list_presets() -> list[PresetMeta]:
    """Daftar metadata semua preset di folder user, terurut berdasar nama file.

    File yang gagal dibaca/parse/divalidasi dilewati diam-diam supaya UI
    dropdown tetap responsif; :func:`load_preset` akan melaporkan detailnya
    saat user memilih preset bermasalah.
    """
    metas: list[PresetMeta] = []
    for path in sorted(presets_dir().glob("*.json")):
        try:
            raw = path.read_text(encoding="utf-8")
            data = _validate(json.loads(raw))
        except (PresetError, json.JSONDecodeError, OSError):
            continue
        metas.append(
            PresetMeta(
                name=path.stem,
                path=path,
                paper=str(data["paper"]),
                orientation=str(data["orientation"]),
            )
        )
    return metas


def load_preset(name: str) -> dict:
    """Baca + parse + validasi preset ``name``. Raise :class:`PresetError`."""
    path = _preset_path(name)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PresetError(
            f"Preset {name!r} tidak ditemukan.",
            hint=f"Diharapkan di: {path}",
        ) from exc
    except OSError as exc:
        raise PresetError(
            f"Gagal membaca preset {name!r}.",
            hint=str(exc),
        ) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PresetError(
            f"Preset {name!r} bukan JSON yang valid.",
            hint=f"Parser: {exc.msg} (baris {exc.lineno}, kolom {exc.colno}).",
        ) from exc
    return _validate(data)


def save_preset(name: str, data: dict) -> Path:
    """Validasi + tulis preset secara atomic. Return path file yang ditulis."""
    validated = _validate(data)
    payload = json.dumps(validated, ensure_ascii=False, indent=2, sort_keys=False)
    path = _preset_path(name)
    try:
        atomic_write(path, payload)
    except OSError as exc:
        raise PresetError(
            f"Gagal menyimpan preset {name!r}.",
            hint=str(exc),
        ) from exc
    return path


def delete_preset(name: str) -> None:
    """Hapus file preset ``name``. Raise :class:`PresetError` bila tidak ada."""
    path = _preset_path(name)
    try:
        path.unlink()
    except FileNotFoundError as exc:
        raise PresetError(
            f"Preset {name!r} tidak ditemukan.",
            hint=f"Diharapkan di: {path}",
        ) from exc
    except OSError as exc:
        raise PresetError(
            f"Gagal menghapus preset {name!r}.",
            hint=str(exc),
        ) from exc
