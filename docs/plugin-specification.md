# Smart Layout Builder — Plugin Specification (MVP Rewrite)

> **Status:** Active. Supersedes the original enterprise plugin spec.
> **Scope:** Minimum required to ship to the QGIS Plugin Repository and have a maintainable release process.

---

## 1. Plugin Identity

| Field | Value |
|-------|-------|
| Plugin name | Smart Layout Builder |
| Plugin folder name | `smart_layout_builder` |
| Python package | `slb` |
| License | GPL-3.0-or-later |
| Initial version | 1.0.0 |
| Min QGIS LTR | The current LTR at first release (e.g., 3.34 or 3.40) |
| Repository | `https://github.com/<org>/smart-layout-builder` |
| Issue tracker | Same repo, GitHub Issues |

---

## 2. `metadata.txt`

QGIS reads `metadata.txt` (INI format) at install/load time. The canonical form for MVP:

```ini
[general]
name=Smart Layout Builder
qgisMinimumVersion=3.34
description=Auto layout generation, smart legend cleaning, and batch atlas export for QGIS.
about=Smart Layout Builder makes producing balanced map layouts and batch atlas PDFs fast. Generate a layout from your project state in one click, prune the legend of irrelevant layers automatically, and export hundreds of map sheets sequentially with great progress UX.
version=1.0.0
author=Smart Layout Builder Maintainers
email=hello@example.org
homepage=https://github.com/<org>/smart-layout-builder
tracker=https://github.com/<org>/smart-layout-builder/issues
repository=https://github.com/<org>/smart-layout-builder
icon=resources/icons/slb_logo.svg
experimental=True
deprecated=False
category=Plugins
tags=layout,print,atlas,cartography,export
changelog=See CHANGELOG.md
```

### 2.1 Notes on Each Field

| Field | Notes |
|-------|-------|
| `qgisMinimumVersion` | Pin to the latest LTR at release time. Widen only if/when we test older LTRs. |
| `qgisMaximumVersion` | **Omit.** Don't bound the upper limit; we'll bump if a real incompatibility appears. |
| `experimental=True` | Until 1.0.0 is in the wild for ~4 weeks without CRITICAL bugs, then set to `False` in 1.0.x patch. |
| `hasProcessingProvider` | Omit / `False`. No Processing provider in MVP. |
| `server` | Omit / `False`. Not a server plugin. |
| `supportsQt6` | Omit. Add when we test PyQt6. |
| `plugin_dependencies` | Empty. No dependencies on other plugins. |
| Localized fields (`description[xx]`, `about[xx]`) | Omit until we ship a translation. |

`metadata.txt` reads `version=` from `slb/version.py` via the packaging script (single source of truth).

---

## 3. Runtime Requirements

| Component | Minimum | Notes |
|-----------|---------|-------|
| QGIS | Current LTR | One LTR target at MVP |
| Python | Matches QGIS LTR (currently 3.9+) | Whatever the QGIS LTR ships with |
| PyQt | PyQt5 (whatever QGIS ships) | PyQt6 support added when QGIS ships PyQt6 by default |
| OS | Linux / macOS / Windows | Linux is the only one CI runs at MVP |
| RAM | 4 GB | Real number depends on project size |
| Disk | 50 MB free for cache + presets | Small footprint |

### 3.1 Optional Dependencies

| Package | Used for | Behavior if missing |
|---------|----------|---------------------|
| `pypdf` *(or `PyPDF2`)* | Merging atlas PDFs into one | Merge checkbox hidden; everything else works |

**No mandatory external dependencies.** The plugin runs against a vanilla QGIS install.

---

## 4. Compatibility Matrix

A small, honest matrix at 1.0:

| SLB | QGIS LTR | Python | PyQt | CI status |
|-----|----------|--------|------|-----------|
| 1.0.x | Current LTR | matches LTR | PyQt5 | ✅ Linux only |
| 1.1.x | + previous LTR | matches LTR | PyQt5 | ✅ Linux + ?Windows |
| Future | +PyQt6 | 3.10+ | PyQt5 / PyQt6 | When justified |

Drops are pre-announced one minor release ahead.

---

## 5. Plugin Loading Lifecycle

```mermaid
sequenceDiagram
    participant QGIS
    participant SLB

    QGIS->>SLB: classFactory(iface)
    Note over SLB: returns SmartLayoutBuilder(iface)
    QGIS->>SLB: initGui()
    Note over SLB: register toolbar/menu; lazy dock; configure logging
    QGIS->>SLB: unload()
    Note over SLB: disconnect signals; remove UI; cleanup dock
```

### 5.1 Lifecycle Rules

- `__init__(iface)` stores `iface` and **does nothing else**. No imports beyond minimum, no I/O.
- `initGui()` budget: **< 200 ms**. Lazy-create dock; lazy-import heavy modules.
- `unload()` must reverse every UI registration and disconnect every signal connection — under Plugin Reloader stress, the plugin must enable/disable 5× without leaks.

### 5.2 Skeleton (also in `api-design.md`)

```python
class SmartLayoutBuilder:
    def __init__(self, iface): ...
    def initGui(self): ...
    def unload(self): ...
```

No other public methods on this class.

---

## 6. Localization Strategy (MVP)

- All user-visible strings wrapped in `self.tr("…")` (or `QCoreApplication.translate("ctx", "…")` for free functions).
- **English only** shipped at 1.0.
- **No** `.ts` / `.qm` compilation pipeline yet — added when a real translator volunteers.
- **No** `tools/update_translations.sh`, **no** Transifex integration, **no** localized `metadata.txt` fields.

When the first translation is requested:

1. Add `i18n/slb_en.ts` (extracted via `pylupdate5`).
2. Add `slb_<lang>.ts` from the translator.
3. Wire `lrelease` into `scripts/package.py` to produce `.qm` files.
4. Register `QTranslator` in `plugin.initGui()`.

Total cost: ~half a day, done lazily.

---

## 7. Packaging

### 7.1 The ZIP Layout

QGIS Plugin Repository expects a single top-level directory:

```
smart_layout_builder.zip
└── smart_layout_builder/
    ├── __init__.py
    ├── metadata.txt
    ├── plugin.py
    ├── version.py
    ├── errors.py
    ├── core/
    ├── export/
    ├── presets/
    ├── ui/
    ├── io/
    ├── utils/
    └── resources/
```

### 7.2 Build Script

`scripts/package.py`:

1. Read version from `slb/version.py`.
2. Copy `slb/` → `dist/staging/smart_layout_builder/`.
3. Remove `__pycache__/`, `*.pyc`, `tests/`, `.DS_Store`, etc.
4. Verify `metadata.txt` `version=` matches `slb/version.py`.
5. ZIP into `dist/smart_layout_builder-<version>.zip`.

Single command: `make package`. ~30 lines of Python.

### 7.3 What's Excluded From the ZIP

- `tests/`
- `docs/`
- `scripts/`
- `.github/`
- `.git*`, `.idea/`, `.vscode/`
- Markdown files **except** `README.md`, `CHANGELOG.md`, `LICENSE`
- `__pycache__/`, `*.pyc`

### 7.4 What's NOT Done (Intentionally)

- ❌ No ZIP signing (Ed25519 etc.).
- ❌ No reproducible-build verification.
- ❌ No vendored runtime dependencies.
- ❌ No PyPI mirror.
- ❌ No Docker image.

These belong to enterprise plugins, not MVP.

---

## 8. Publishing to QGIS Plugin Repository

### 8.1 First Submission

1. Create / sign in to the maintainer account at `plugins.qgis.org`.
2. Submit ZIP via web form.
3. Wait for approval (usually a day or two).
4. Iterate on reviewer feedback if any.

### 8.2 Subsequent Releases

Manual upload via the web form for MVP. Automate with the `RPC2` upload API only after **3+ successful manual releases** prove the workflow.

### 8.3 Channels

| Channel | Purpose |
|---------|---------|
| QGIS Plugin Repo (experimental) | MVP releases |
| QGIS Plugin Repo (stable) | After 1.0.0 stable |
| GitHub Releases | Mirror of the ZIP for offline installs |

That's it. No PyPI, no Docker, no custom registry.

---

## 9. Versioning Rules

- **SemVer:** `MAJOR.MINOR.PATCH`.
- **MAJOR:** breaking JSON-preset schema change without auto-migration; drop of a QGIS LTR; removal of a UI feature.
- **MINOR:** new features; new presets shipped; new optional dependency.
- **PATCH:** bug fixes only; no behavior change for existing flows.
- **Pre-release tags:** `1.0.0-beta1`, `1.0.0-rc1`. Marked `experimental=True`.

`slb/version.py`:

```python
__version__ = "1.0.0-beta1"
```

---

## 10. Pre-Release Checklist

A single, honest checklist (no enterprise theater):

```
[ ] slb/version.py bumped
[ ] metadata.txt version matches
[ ] CHANGELOG.md entry added
[ ] CI green on latest commit
[ ] Plugin loads/unloads cleanly in a fresh QGIS profile (manual smoke test)
[ ] All MVP acceptance criteria pass (architecture.md / mvp-recommendation.md)
[ ] README + USAGE updated for any user-visible change
[ ] Git tag created (annotated, signed if maintainer has a GPG key)
[ ] make package produces ZIP
[ ] ZIP installed cleanly into a clean QGIS profile
[ ] Uploaded to QGIS Plugin Repo
[ ] GitHub Release published with ZIP attached
[ ] Announcement post drafted (QGIS forum, optional)
```

---

## 11. Plugin Settings Storage

| Setting Class | Storage |
|---------------|---------|
| Runtime prefs | `QSettings("SLB", "SLB")` |
| Saved presets | `~/.qgis/SLB/presets/*.json` |
| Logs | `~/.qgis/SLB/logs/` |
| Temp atlas files | `~/.qgis/SLB/tmp/` |
| Export history (Phase 1.1) | `~/.qgis/SLB/history.jsonl` |

See [`database-schema.md`](database-schema.md) for the full storage strategy. **No SQLite in MVP.**

---

## 12. Telemetry, Reporting, Signing

| Concern | MVP status |
|---------|------------|
| Telemetry | **None.** Plugin Repo's install counter is enough signal. |
| Crash reporting | **None.** Users send logs manually if they want. |
| Signed releases | **None.** GitHub + Plugin Repo are trusted channels. |
| Reproducible builds | **None.** Not in the threat model. |

---

## 13. Processing Provider (Deferred)

Not exposed in MVP. The plan to register `slb:generate-layout` / `slb:export-atlas` as Processing algorithms is deferred to Phase 4+, contingent on user demand.

If/when added:
- A single `SLBProcessingProvider(QgsProcessingProvider)` class.
- Algorithms wrap the existing `core/` and `export/` functions.
- Registered in `initGui()` and unregistered in `unload()`.

---

## 14. Plugin Repo Review — Things to Get Right First Time

These items historically cause Plugin Repo rejections; check each:

| Check | Detail |
|-------|--------|
| `metadata.txt` fields | All required fields present; valid INI syntax |
| `qgisMinimumVersion` | Numeric and reasonable |
| `icon` path | Exists in the ZIP at the declared path |
| No `__pycache__` in ZIP | Stripped by package script |
| GPL license file present | `LICENSE` in the ZIP root |
| No malicious code | Plain Python, no `exec`/`eval`/network on import |
| No bundled secrets | Grep before packaging |
| Plugin actually does something | The reviewer will try installing it |

The package script asserts each of these where it can.

---

## 15. End-of-Life Policy

Not relevant in MVP. Set when 2.0 is on the horizon. Until then:

- We support the latest released MAJOR (`1.x`).
- We don't promise backports to previous MAJORs (there are none yet).

---

## 16. Things Deliberately NOT in This Spec

To make the absence explicit:

- ❌ Localization pipeline (no `.ts` / `.qm` build until needed)
- ❌ Reproducible builds + Ed25519 signing
- ❌ Telemetry backend / opt-in events
- ❌ Processing provider registration
- ❌ Marketplace publishing strategy
- ❌ Docker / PyPI distribution
- ❌ Multi-profile sync
- ❌ Cloud sync
- ❌ Plugin signing infrastructure
- ❌ Multi-LTR / multi-OS CI matrix (Linux + current LTR only at MVP)

Each of these is a maintenance commitment. We add them when reality demands.

---

## 17. Comparison With Original Plan

| Aspect | Original | Rewrite |
|--------|----------|---------|
| `metadata.txt` fields | ~14 with locale variants | 11 essential |
| QGIS LTR matrix | 3.28 + 3.34 + 3.40 | Current LTR only |
| Mandatory runtime deps | ~5 | 0 |
| Optional runtime deps | various | 1 (`pypdf`) |
| Languages shipped at MVP | EN + ID | EN only |
| Signing + reproducible builds | Yes | No |
| Telemetry | Opt-in backend | No |
| Processing provider | Yes (Phase 4) | Deferred |
| Distribution channels | Plugin Repo + PyPI + Docker + GitHub | Plugin Repo + GitHub |
| Release checklist items | 12 | 13 (similar, but no ceremony items) |

---

## 18. Bottom Line

The spec for an MVP QGIS plugin is small:

1. A valid `metadata.txt`.
2. A `classFactory` that returns the plugin instance.
3. Clean `initGui()` / `unload()`.
4. A working installable ZIP.
5. Submission to the QGIS Plugin Repo.

Everything else — signing, telemetry, marketplace, multi-LTR, multi-locale — is added when there's a real reason. Not before.

---

*End of plugin-specification.md (lean rewrite).*
