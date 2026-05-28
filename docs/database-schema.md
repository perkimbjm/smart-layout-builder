# Smart Layout Builder — Storage Strategy (MVP Rewrite)

> **Status:** Active. Supersedes the original 15-table SQLite schema.
> **Punchline:** **There is no database in MVP.** Everything is `QSettings` + JSON files.

---

## 1. Why No Database

A QGIS plugin's storage needs are small enough that a database adds more friction than it removes:

| Concern | Database overhead avoided |
|---------|---------------------------|
| Migrations | None to write, test, fail on |
| Connection management | None across threads |
| Backup / portability | A folder of JSON files; `cp -r` works |
| User inspection | Open in any editor |
| Conflict on plugin reload | None |
| Locked-DB errors | Impossible |
| Schema versioning | One `"schema": N` field per JSON file |

If we later need queries (analytics, deduplication, search), we add SQLite *just for that feature*. Not preemptively.

---

## 2. Storage Layout on Disk

```
~/.qgis/SLB/
├── presets/
│   ├── classic_a4_portrait.json
│   ├── classic_a3_landscape.json
│   └── <user-defined>.json
├── history.jsonl                  # (Phase 1.1) append-only export history
├── logs/
│   ├── slb.log
│   ├── slb.log.1
│   └── slb.log.2
└── tmp/                           # short-lived; cleaned on success / cancel
    └── <job_uuid>/
        ├── part_001.pdf
        └── …
```

Plus runtime preferences in **`QSettings("SLB", "SLB")`** (per QGIS profile).

That's the full storage surface. ~3 directories + 1 settings key namespace.

---

## 3. QSettings Keys

Single namespace: `QSettings("SLB", "SLB")`.

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `defaults/paper` | str | `"A4"` | Default paper size |
| `defaults/orientation` | str | `"portrait"` | Default orientation |
| `defaults/output_dir` | str | `~/Documents/SLB-exports` | Default atlas output folder |
| `defaults/preset` | str | `"classic_a4_portrait"` | Last-selected preset name |
| `defaults/legend_mode` | str | `"safe"` | `"safe"` or `"extent"` |
| `defaults/filename_template` | str | `"map_{feature_id}.pdf"` | Last-used filename template |
| `defaults/dpi` | int | `300` | Atlas export DPI |
| `defaults/merge_pdf` | bool | `false` | Whether to merge atlas output |
| `dock/geometry` | bytes | (empty) | `QByteArray` from `dock.saveGeometry()` |
| `dock/state` | bytes | (empty) | `QByteArray` from `dock.saveState()` |
| `first_run_complete` | bool | `false` | Set true after `ensure_defaults_installed()` |

Read pattern:

```python
from qgis.PyQt.QtCore import QSettings
def setting(key: str, default):
    return QSettings("SLB", "SLB").value(key, default)
```

That's the whole settings system.

---

## 4. Preset JSON Schema

One file per preset at `~/.qgis/SLB/presets/<name>.json`.

```json
{
  "schema": 1,
  "name": "Classic A4 Portrait",
  "paper": "A4",
  "orientation": "portrait",
  "strategy": "single_column",
  "items": [
    {
      "role": "title",
      "anchor": "top",
      "h_mm": 12,
      "style": {"font_size_pt": 18, "weight": "bold"},
      "binding": "[%@project_title%]"
    },
    {"role": "map", "fill": "center"},
    {
      "role": "legend",
      "anchor": "bottom-left",
      "w_mm": 80,
      "h_mm": 50,
      "style": {"columns": 1}
    },
    {
      "role": "scale_bar",
      "anchor": "bottom",
      "h_mm": 10,
      "style": {"units": "auto", "segments": 4}
    },
    {
      "role": "north_arrow",
      "anchor": "bottom-right",
      "w_mm": 20,
      "h_mm": 20
    },
    {
      "role": "attribution",
      "anchor": "bottom",
      "h_mm": 5,
      "style": {"font_size_pt": 7},
      "binding": "Source: {sources}"
    }
  ]
}
```

### 4.1 Field Reference

| Field | Required | Notes |
|-------|----------|-------|
| `schema` | ✅ | Integer. Today only `1`. Used by future migrator if/when needed. |
| `name` | ✅ | Human-readable. Doesn't need to match filename. |
| `paper` | ✅ | `"A4"` \| `"A3"` \| `"Letter"`. |
| `orientation` | ✅ | `"portrait"` \| `"landscape"`. |
| `strategy` | ✅ | `"single_column"` \| `"two_column"`. |
| `items` | ✅ | Array of item specs (see below). |
| Top-level extras | optional | Ignored; preserved on save (forward-compatibility). |

### 4.2 Item Spec

| Field | Required | Notes |
|-------|----------|-------|
| `role` | ✅ | One of: `title`, `map`, `legend`, `scale_bar`, `north_arrow`, `attribution`. |
| `anchor` | one of these | `top`, `bottom`, `top-left`, `top-right`, `bottom-left`, `bottom-right`. |
| `fill` | one of these | `"center"` for the map item (fills available space). |
| `w_mm`, `h_mm` | conditional | Required unless `fill` is set. |
| `style` | optional | Role-specific dict; passed through to the layout-item materializer. |
| `binding` | optional | QGIS expression for text items. |

### 4.3 Validation Rules

- Must have a `map` item (exactly one).
- All `role` values must be from the allowed set.
- `anchor` and `fill` are mutually exclusive on a single item.
- Validation runs on `load_preset()` and `save_preset()`; failure raises `PresetError`.

---

## 5. Bundled Presets

Two presets ship in `slb/resources/builtin_presets/`:

| File | Description |
|------|-------------|
| `classic_a4_portrait.json` | A4 portrait, single-column layout, simple |
| `classic_a3_landscape.json` | A3 landscape, two-column layout, more sidebar items |

On first run (controlled by `first_run_complete` QSettings flag), `defaults.ensure_defaults_installed()`:

1. Creates `~/.qgis/SLB/presets/` if missing.
2. For each bundled file: copies to user dir **only if a same-name file doesn't exist**.
3. Sets `first_run_complete = true`.

Users may freely edit their copies; updates to the bundled files in newer plugin versions **do not** overwrite user copies. (Acceptable trade-off; users rarely edit defaults, and we avoid clobbering anything they did edit.)

---

## 6. Export History (Phase 1.1)

When implemented, `~/.qgis/SLB/history.jsonl` (one JSON object per line):

```json
{"job_id":"a1b2","when":"2026-06-12T10:33:00","kind":"atlas","layout":"My Layout","output_dir":"/home/u/maps","count":56,"duration_s":342,"status":"ok"}
{"job_id":"a1b3","when":"2026-06-12T11:48:00","kind":"atlas","layout":"My Layout","output_dir":"/home/u/maps","count":56,"duration_s":7,"status":"cancelled"}
```

### 6.1 Trim Strategy

Before appending, the writer:
1. Counts lines in the file (cheap via `wc -l` style on small files).
2. If > 500, rewrites keeping the last 200 entries.

No locking. Single writer (the dock). Reads are best-effort.

### 6.2 Why JSONL?

- Append-only writes are atomic on POSIX & Windows.
- One-line-per-record is grep-friendly.
- No schema migrations.
- Easy to drop into pandas / a spreadsheet if a user wants stats.

---

## 7. Logs

`~/.qgis/SLB/logs/slb.log` via Python's `RotatingFileHandler`:
- Max 1 MB per file.
- Keep 3 backups (`slb.log`, `slb.log.1`, `slb.log.2`).
- Plain text, one record per line, format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`.

Set up once in `utils/logging.configure_logging()`:

```python
import logging
from logging.handlers import RotatingFileHandler
from .io.safe_paths import user_dir, ensure_dir

def configure_logging():
    log_dir = ensure_dir(user_dir() / "logs")
    handler = RotatingFileHandler(log_dir / "slb.log", maxBytes=1_000_000, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root = logging.getLogger("slb")
    root.setLevel(logging.INFO)
    root.addHandler(handler)
```

---

## 8. Temp Files (Atlas)

During an atlas job: `~/.qgis/SLB/tmp/<job_uuid>/part_<NNN>.pdf`.

| Event | Action |
|-------|--------|
| Successful export | Files atomically moved to `output_dir`; `tmp/<job_uuid>/` removed |
| Cancelled | `tmp/<job_uuid>/` removed |
| Plugin crash mid-job | `tmp/<job_uuid>/` persists; user can manually delete or future "resume" feature (1.1) can reuse |
| Plugin startup | Best-effort: clean any `tmp/<*>/` older than 7 days |

---

## 9. What We Don't Persist

- No AI request cache (no AI in MVP).
- No layer thumbnail cache (no live preview in MVP).
- No template metadata (no templates in MVP, just presets).
- No settings audit log.
- No multi-user accounts.
- No telemetry.

When/if any becomes needed, we add storage for *that* feature with the simplest approach.

---

## 10. Backup, Restore, Reset

These are trivially "open the folder" operations:

| Operation | Steps |
|-----------|-------|
| Backup | `cp -r ~/.qgis/SLB ~/slb-backup` (or zip it) |
| Restore | Reverse |
| Reset | Delete `~/.qgis/SLB/`; relaunch QGIS; defaults reinstall |
| Inspect | Open any preset JSON in a text editor |
| Migrate to a new machine | Copy the folder |

Settings dialog will expose: `[Open data folder]` and `[Reset to defaults]` buttons.

---

## 11. Migration Strategy (when needed, not now)

If we ever bump the preset schema:

```python
def migrate_preset(data: dict) -> dict:
    schema = data.get("schema", 1)
    if schema == 1:
        # transform to v2 (e.g. rename a key)
        data["new_key"] = data.pop("old_key", default)
        schema = 2
    if schema == 2:
        # next migration when needed
        ...
    data["schema"] = schema
    return data
```

Migrations run on `load_preset()`. They're functions, not framework. We write the first one *only when we change the schema*.

---

## 12. Threading

- All persistent storage is accessed from the **main (UI) thread**.
- `QgsTask` workers receive their needed data via constructor and don't read QSettings or load presets themselves.
- This eliminates write races without needing locks.

---

## 13. Security

- File permissions: best-effort `chmod 600` on POSIX for `~/.qgis/SLB/` and JSON files. (Not load-bearing — these files contain no secrets.)
- No secrets stored. If AI is later added, API keys live in the OS keyring (`keyring` module) — not on disk.
- ZIP-slip protection is not needed (no ZIP loading in MVP).

---

## 14. Example: Full Save/Load Cycle

```python
# slb/presets/repository.py (sketch)

import json
from pathlib import Path
from ..io.safe_paths import user_dir, atomic_write, ensure_dir, safe_filename
from ..errors import PresetError

VALID_ROLES = {"title", "map", "legend", "scale_bar", "north_arrow", "attribution"}

def _presets_dir() -> Path:
    return ensure_dir(user_dir() / "presets")

def _path_for(name: str) -> Path:
    return _presets_dir() / f"{safe_filename(name)}.json"

def _validate(data: dict) -> None:
    if data.get("schema") != 1:
        raise PresetError(f"Unknown preset schema {data.get('schema')}",
                          hint="This preset was created with a newer SLB. Update the plugin.")
    if not data.get("name"):     raise PresetError("Preset name is required.")
    if not data.get("paper"):    raise PresetError("paper is required.")
    if not data.get("orientation"): raise PresetError("orientation is required.")
    items = data.get("items") or []
    if not any(it.get("role") == "map" for it in items):
        raise PresetError("Preset must contain a 'map' item.")
    bad = {it.get("role") for it in items} - VALID_ROLES
    if bad: raise PresetError(f"Unknown roles: {sorted(bad)}")

def save_preset(name: str, data: dict) -> Path:
    data = {**data, "schema": 1, "name": name}
    _validate(data)
    p = _path_for(name)
    atomic_write(p, json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"))
    return p

def load_preset(name: str) -> dict:
    p = _path_for(name)
    if not p.exists():
        raise PresetError(f"Preset '{name}' not found.",
                          hint="Open Settings to see your installed presets.")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PresetError(f"Preset '{name}' is corrupt: {e}",
                          hint=f"Edit or delete {p}.") from e
    _validate(data)
    return data
```

That's the complete storage adapter. ~50 LOC. No SQL, no migrations, no triggers.

---

## 15. Comparison With the Original Plan

| Aspect | Original | Rewrite |
|--------|----------|---------|
| Storage backend | SQLite | None (JSON + QSettings) |
| Tables / files | 15+ tables | 2 JSON shapes + QSettings keys |
| Migrations | Numbered SQL files | Function chain in code (added when needed) |
| Triggers / views | Yes | None |
| WAL / connection pooling | Yes | N/A |
| Multi-user table | Yes | None |
| Settings audit | Yes | None |
| AI cache | Yes | None |
| Thumb cache | Yes | None |
| Preset versions | Yes | None (Git-friendly JSON, users version externally if they want) |
| Backup | Custom export tool | `cp -r` |
| Inspection | DB browser | Any text editor |
| LOC overhead | ~500 (migrator, schema, adapter) | ~50 (`repository.py`) |

---

## 16. When We'd Reconsider SQLite

Add SQLite **only when** one of:
- Export history grows past ~10k entries and full-file scans become annoying.
- A new feature needs queries over many records (e.g., "find all atlases of layer X").
- Cache eviction logic needs LRU with many entries.

Even then, add it for that one feature; don't move presets into it.

---

## 17. Bottom Line

The whole storage system fits on a notepad:

- **`QSettings("SLB", "SLB")`** for runtime prefs.
- **`~/.qgis/SLB/presets/*.json`** for presets.
- **`~/.qgis/SLB/history.jsonl`** for export history (1.1+).
- **`~/.qgis/SLB/logs/`** for rotating log file.
- **`~/.qgis/SLB/tmp/`** for in-flight atlas temp files.

Boring. Inspectable. Backup-able. Crash-safe. Zero migration debt.

---

*End of database-schema.md (now: storage strategy).*
