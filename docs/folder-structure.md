# Smart Layout Builder — Folder Structure (MVP Rewrite)

> **Status:** Active. Supersedes the original 30-directory enterprise layout.
> **Target:** 6 packages under `slb/`, ~12–15 real Python files, 2,500–4,000 LOC.

---

## 1. Top-Level Tree

```
smart-layout-builder/
├── .github/
│   └── workflows/
│       └── ci.yml                 # Lint + unit tests on Linux, latest QGIS LTR
├── docs/                          # Planning, review, user docs
├── scripts/
│   ├── package.py                 # Build installable .zip
│   ├── compile_resources.sh       # pyrcc5 resources.qrc (only if used)
│   └── dev_qgis.sh                # Launch QGIS with plugin symlinked
├── slb/                           # The plugin package (everything below)
├── tests/
│   ├── conftest.py
│   ├── fixtures/                  # Sample .qgz + tiny coverage layer
│   ├── unit/
│   └── integration/
├── pyproject.toml                 # ruff + black + (light) mypy config
├── requirements-dev.txt
├── Makefile                       # make package | make test | make lint
├── LICENSE                        # GPL-3.0-or-later
├── CHANGELOG.md
├── README.md
└── USAGE.md
```

That's it. No `requirements.txt` (zero mandatory runtime deps), no docs-build pipeline, no separate translations directory until a translator volunteers.

---

## 2. The `slb/` Package

```
slb/
├── __init__.py                    # classFactory
├── metadata.txt                   # QGIS plugin manifest
├── plugin.py                      # SmartLayoutBuilder lifecycle
├── version.py                     # __version__ = "1.0.0"
├── errors.py                      # SLBError hierarchy (one file)
│
├── core/                          # Layout composition
│   ├── __init__.py
│   ├── layout.py                  # generate_layout(...)
│   ├── legend.py                  # prune_legend(...)
│   └── strategies.py              # two_column / single_column
│
├── export/                        # Atlas + single export
│   ├── __init__.py
│   ├── atlas.py                   # run_atlas(...)
│   ├── progress.py                # AtlasProgressReporter (QObject)
│   └── pdf_merge.py               # Optional, guards on pypdf import
│
├── presets/                       # Preset CRUD over JSON files
│   ├── __init__.py
│   ├── repository.py              # list/load/save/delete
│   └── defaults.py                # ensure_defaults_installed()
│
├── ui/                            # PyQt widgets
│   ├── __init__.py
│   ├── dock.py                    # SLBDock with Compose + Atlas tabs
│   ├── settings_dialog.py
│   └── designer/                  # Optional .ui files
│       ├── dock.ui
│       └── settings_dialog.ui
│
├── io/                            # Filesystem helpers
│   ├── __init__.py
│   └── safe_paths.py              # user_dir(), atomic write, path sanitize
│
├── utils/                         # Cross-cutting helpers
│   ├── __init__.py
│   ├── logging.py                 # configure_logging()
│   └── qgis_compat.py             # Tiny shim for QGIS API drift (often empty)
│
└── resources/
    ├── icons/
    │   ├── slb_logo.svg
    │   ├── compose.svg
    │   ├── atlas.svg
    │   └── settings.svg
    └── builtin_presets/
        ├── classic_a4_portrait.json
        └── classic_a3_landscape.json
```

**6 top-level packages.** `core/`, `export/`, `presets/`, `ui/`, `io/`, `utils/`. Plus `resources/` (data, not code).

---

## 3. Purpose of Each Folder

### `slb/` (root)

| File | Purpose |
|------|---------|
| `__init__.py` | QGIS entry point: `def classFactory(iface): from .plugin import SmartLayoutBuilder; return SmartLayoutBuilder(iface)` |
| `metadata.txt` | QGIS plugin manifest (name, version, qgisMinimumVersion, …) |
| `plugin.py` | The `SmartLayoutBuilder` class: `initGui` / `unload` / `show_dock` |
| `version.py` | `__version__ = "1.0.0"` — single source of truth; metadata reads it |
| `errors.py` | `SLBError`, `ValidationError`, `ExportError`, `ExportCancelled`, `PresetError` |

### `core/` — Layout composition logic

- Pure functions over PyQGIS objects.
- `layout.py`: takes a `QgsProject` + options, returns a `QgsPrintLayout`.
- `legend.py`: prunes a layout's legend in place; returns count removed.
- `strategies.py`: two pure functions returning lists of item-spec `dict`s.

### `export/` — Atlas and single export

- `atlas.py`: sequential `run_atlas` — main worker function.
- `progress.py`: small `QObject` that emits `progress(int, str)` and `finished(dict)`. Bridges worker → UI.
- `pdf_merge.py`: tries `import pypdf` (or `PyPDF2`) at top of module; exposes `merge_available` flag.

### `presets/` — Preset persistence

- `repository.py`: file-system CRUD; serializes/deserializes JSON.
- `defaults.py`: first-run install of bundled presets.

### `ui/` — PyQt widgets

- `dock.py`: the single `QDockWidget` with 2 tabs.
- `settings_dialog.py`: tiny modal with 2 fields (default paper, default output folder).
- `designer/`: optional Qt Designer `.ui` files. If we don't use Designer, this folder doesn't exist.

### `io/` — Filesystem helpers

- `safe_paths.py`: `user_dir()`, `atomic_write(path, bytes)`, `safe_filename(s)`, `ensure_dir(path)`.

### `utils/`

- `logging.py`: `configure_logging()` called once from `plugin.py`.
- `qgis_compat.py`: shims for QGIS API differences. Starts empty.

### `resources/`

- `icons/`: 4 SVGs (logo + compose + atlas + settings).
- `builtin_presets/`: 2 JSON presets shipped with the plugin; copied to user dir on first run.

We do **not** use Qt's `resources.qrc` system by default — direct file paths to `slb/resources/...` work fine and keep the build simple. If we ever need it (theme-aware icons), we add it then.

---

## 4. The `tests/` Tree

```
tests/
├── conftest.py                    # Common fixtures
├── fixtures/
│   ├── three_layers.qgz           # 3-layer project, small extent
│   ├── coverage_5.gpkg            # 5-feature coverage for atlas tests
│   └── empty.qgz
├── unit/
│   ├── test_strategies.py         # Pure-math tests on item placement
│   ├── test_legend_rules.py
│   ├── test_presets_repository.py
│   └── test_safe_paths.py
└── integration/
    ├── test_generate_layout.py    # Loads three_layers.qgz, generates, asserts items
    ├── test_prune_legend.py
    └── test_run_atlas.py          # Runs full sequential atlas; asserts 5 PDFs
```

**~10 test files.** No matrix testing in MVP. CI runs `pytest tests/` on Linux + latest QGIS LTR.

---

## 5. The `docs/` Tree

```
docs/
├── architecture.md                # ← this rewrite
├── folder-structure.md            # ← this file
├── development-roadmap.md
├── api-design.md
├── database-schema.md             # (really "storage strategy")
├── plugin-specification.md
├── coding-standards.md
├── plan.md                        # original vision (kept)
├── features.md                    # original (kept; aspirational)
├── ui-ux.md                       # original (kept; aspirational)
├── testing-strategy.md            # original (kept, mostly accurate for MVP)
├── review/                        # The brutally honest reviews
│   ├── executive-review.md
│   ├── architecture-review.md
│   ├── architecture-scorecard.md
│   ├── mvp-recommendation.md
│   ├── simplification-plan.md
│   ├── risk-analysis.md
│   ├── revised-roadmap.md
│   └── implementation-order.md
└── prompts/                       # AI prompt specs (deferred; kept as reference for post-1.0)
    └── …
```

---

## 6. The `scripts/` Tree

```
scripts/
├── package.py                     # Build .zip for QGIS Plugin Repo
├── compile_resources.sh           # Only if/when we use resources.qrc
└── dev_qgis.sh                    # Symlink slb/ into ~/.qgis/<profile>/python/plugins/
```

`package.py` does:
1. Copy `slb/` to `dist/staging/smart_layout_builder/`.
2. Strip `__pycache__`, `*.pyc`, `tests/`.
3. ZIP into `dist/smart_layout_builder-<version>.zip`.

No signing, no determinism enforcement, no reproducible-builds verification.

---

## 7. The `.github/` Tree

```
.github/
├── workflows/
│   ├── ci.yml                     # ruff + pytest on Linux, latest QGIS LTR
│   └── release.yml                # On tag → build + attach release ZIP
├── ISSUE_TEMPLATE/
│   ├── bug.yml
│   └── feature.yml
└── PULL_REQUEST_TEMPLATE.md
```

No multi-OS matrix in CI until 1.1.

---

## 8. Naming Conventions

| Kind | Rule | Example |
|------|------|---------|
| Module / package | `snake_case` | `core/layout.py` |
| Class | `PascalCase` | `SLBDock` |
| Function / method | `snake_case` | `generate_layout()` |
| Constant | `SCREAMING_SNAKE_CASE` | `DEFAULT_PAPER = "A4"` |
| Test file | mirrors source path with `test_` prefix | `tests/unit/test_strategies.py` |
| Preset file | `kebab-or-snake.json` | `classic_a4_portrait.json` |
| Icon file | `kebab-case.svg` | `north-arrow.svg` |

---

## 9. Comparison With the Original Plan

| Aspect | Original | Rewrite |
|--------|----------|---------|
| Top-level packages under `slb/` | 14 | 6 |
| Sub-packages with 1–2 files | many | none |
| `application/` use cases | yes | removed |
| `domain/` with entities/value_objects/engine/strategies/policies | yes | removed |
| `ports/` interfaces | yes | removed |
| `infrastructure/qgis_adapter/` | yes | removed |
| `infrastructure/storage/migrations/` | yes | removed |
| `ai/` | yes | removed |
| `services/` | yes | removed (logic lives in `core/`, `export/`, `presets/`) |
| `ui/wizards/` | yes | removed (no wizard in MVP) |
| `ui/widgets/` reusable | yes | removed (inline in `dock.py` until reuse forces extraction) |
| `ui/theme/` | yes | removed (inherit QGIS theme) |
| `i18n/` directory | yes | removed (added when a translator volunteers) |
| Real Python files | ~80 | ~15 |
| LOC target | 10,000–15,000 | 2,500–4,000 |

---

## 10. Rules for Adding New Files

Before creating a new file, ask:

1. **Does an existing module fit?** If a new function fits in `core/layout.py` (under 500 lines), put it there.
2. **Is there a real second caller / variant?** If `BaseExporter` would have one concrete subclass today, **don't make the base class**. Add it when subclass #2 arrives.
3. **Is this UI or logic?** Don't put SQL/network/parsing in `ui/`. Don't put `QWidget` in `core/`.
4. **Is this a `dict` or a `dataclass`?** Use plain `dict` until access patterns or invariants justify a `dataclass`.

---

## 11. Files We'll Add in 1.1 (Not Now)

For reference. Do not pre-create.

| Phase | Likely new file |
|-------|-----------------|
| 1.1 | `export/history.py` — JSONL append/read for past exports |
| 1.1 | `core/inset_map.py` — if users ask for inset map |
| 1.1 | `slb/i18n/slb_id.ts` + compile pipeline — if a translator volunteers |
| 1.2 | `core/adaptive.py` — if anchors aren't enough |
| 1.2 | `export/parallel.py` — only after a successful spike + flag |

We **do not** scaffold these now. Empty files invite premature design.

---

## 12. What's Deliberately Missing

To make the absence explicit:

- ❌ No `ports/` — direct PyQGIS imports.
- ❌ No `infrastructure/` — direct filesystem + QSettings.
- ❌ No `application/use_cases/` — widgets call services/functions directly.
- ❌ No `domain/` — composition logic lives in `core/`.
- ❌ No `services/` directory — `core/`, `export/`, `presets/` are already the "services".
- ❌ No `ai/` — feature is out of scope.
- ❌ No `infrastructure/storage/migrations/` — no SQL.
- ❌ No `infrastructure/secrets/` — no secrets to store.
- ❌ No `infrastructure/event_bus/` — Qt signals only.
- ❌ No `ui/wizards/` — no wizard in MVP.
- ❌ No `infrastructure/i18n/` — `tr()` wrapping only, no compile pipeline yet.

---

## 13. Bottom Line

The structure is small enough that a new contributor can `tree slb/` and understand the entire codebase in one screenful. Every file maps to a sentence:

- `plugin.py` — start the plugin, register the UI.
- `core/layout.py` — make a layout.
- `core/legend.py` — clean the legend.
- `core/strategies.py` — decide where items go.
- `export/atlas.py` — run an atlas.
- `presets/repository.py` — load/save presets.
- `ui/dock.py` — the dock panel.
- `ui/settings_dialog.py` — the settings dialog.

If a piece of work doesn't fit any of those sentences, that's a signal to question the work — not to add a new folder.

---

*End of folder-structure.md (lean rewrite).*
