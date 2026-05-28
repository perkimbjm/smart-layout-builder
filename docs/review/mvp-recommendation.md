# MVP Recommendation — Smart Layout Builder

> **Goal:** Define a 1.0 that **ships in 6–8 weeks** by a small team and proves the product idea with real users.
> **Method:** Aggressive scope cut. Replace "Phase 1 MVP" (currently 10 weeks, 8 features) with a truly minimal set.

---

## 1. Guiding Principles

1. **A shipped, narrow tool beats a planned, broad one.**
2. **Anything not on the MVP path is friction.** Even good ideas.
3. **Don't build infrastructure for features you might not ship.**
4. **Polish the 3 things you do build.** It's better to nail 3 features than half-do 8.
5. **Match scope to maintenance bandwidth.** A solo or 2-person OSS team should target features they can support for the next 18 months.

---

## 2. The Real MVP — 3 Features

### M1 — Auto Layout Generator (one-click)

The single most valuable thing. Press a button, get a balanced `QgsPrintLayout` from current project state, with sensible defaults.

**Scope:**
- Paper: A4 / A3, portrait / landscape (4 combinations).
- Items: title + map + legend + scale bar + north arrow + attribution. No inset map (defer), no grid (use QGIS native if needed).
- Composition: **one strategy** — a fixed two-column "map left / sidebar right" template, with an alternative single-column variant for portrait.
- Title: bound to `[%@project_title%]`. No fancy dynamic text engine.
- Generated layout opens in the native QGIS Layout Designer for fine-tuning.

**Out of scope:**
- Multiple composition strategies (editorial, minimal, AI).
- Adaptive layout / constraint solver.
- Live debounced preview.
- Custom dynamic text tokens beyond what `[% %]` already does.

### M2 — Smart Legend Cleaner

The differentiator that earns the plugin's name. Prune the legend of obvious noise.

**Scope:**
- Hide layers marked "excluded from legend" (QGIS property).
- Hide invisible layers.
- *Optionally* hide layers with zero features in extent — **off by default**, opt-in per generation, with a clear "this may be slow" warning.
- Idempotent: re-running on the same project produces the same output.

**Out of scope:**
- AI-suggested grouping.
- Category-level pruning (raster classes, vector sub-symbology).
- Cross-session "remember user edits" logic.

### M3 — Batch Atlas Export (sequential, with great UX)

The other major time-saver. **Sequential**, not parallel. Beats native QGIS on UX alone.

**Scope:**
- Coverage layer dropdown.
- Optional filter expression (passes through to QGIS native).
- Filename template: `peta_[%kelurahan%].pdf` style.
- Format: PDF only (PNG/SVG later).
- Progress bar with ETA, current feature name, cancel button.
- Optional: merge per-feature PDFs into a single PDF at the end (using `pypdf` if available; if not, skip with a notice).
- Output folder picker with collision warning.

**Out of scope:**
- Parallel rendering. **Critical:** explicitly out of MVP. Add later behind an experimental flag once spike-validated.
- Resume after crash.
- GeoPDF, SVG, multi-format.
- Per-feature template selection.
- Bookmarks in merged PDF (nice but ~2 extra days).

---

## 3. MVP Feature Classification

### 3.1 Must-Have (M0 — ship blockers)

| Code | Feature | Notes |
|------|---------|-------|
| M1 | Auto Layout Generator | One strategy only |
| M2 | Smart Legend Cleaner | Visibility + excluded rules |
| M3 | Batch Atlas Export (sequential) | PDF only, with progress |
| M4 | Dock panel UI (2 tabs: Compose, Atlas) | No Templates/AI tabs |
| M5 | Settings dialog (minimal) | Just default paper, default output folder |
| M6 | Plugin metadata + packaging | `metadata.txt`, ZIP build script |
| M7 | Smoke tests | Layout generation + atlas (5-feature fixture) |
| M8 | README + 1 user-guide page | "Getting Started" only |

### 3.2 Should-Have (S1 — ship if time permits in weeks 7–8)

| Code | Feature | Notes |
|------|---------|-------|
| S1 | Save / load named layout configurations | **JSON files**, no SQLite, no version history, no locking |
| S2 | Last-used settings remembered | Via `QSettings` |
| S3 | "Open in QGIS Layout Designer" button | One-liner after generating |
| S4 | Atlas merge-into-single-PDF | If `pypdf` available |
| S5 | Basic input validation messages | "Output folder must exist", etc. |
| S6 | Localization scaffolding (EN only) | Wrap strings in `self.tr()` |

### 3.3 Nice-to-Have (N1 — defer, but easy when time comes)

| Code | Feature | Realistic Phase |
|------|---------|-----------------|
| N1 | Onboarding wizard | 1.1 |
| N2 | Export history (JSONL file, not DB) | 1.1 |
| N3 | Inset map item | 1.1 |
| N4 | Grid + grid labels item | 1.1 |
| N5 | PNG / SVG atlas formats | 1.1 |
| N6 | Indonesian (id) translation | 1.1 |
| N7 | More than one composition strategy | 1.1 |
| N8 | Static layout preview thumbnail in dock | 1.1 |

### 3.4 Future (F1 — only after 1.0 has real users)

| Code | Feature | Realistic Phase |
|------|---------|-----------------|
| F1 | Adaptive layout (anchor-based, not solver-based) | 1.2 |
| F2 | Templates as JSON packages (no ZIP) | 1.2 |
| F3 | Live debounced preview | 1.2 |
| F4 | Dynamic text tokens (a small fixed set) | 1.3 |
| F5 | Parallel atlas export (experimental flag) | 1.3, after spike |
| F6 | Report Builder (composite PDF) | 2.0 |

### 3.5 Experimental / Maybe-Never (X1 — explicitly NOT planned)

| Code | Feature | Status |
|------|---------|--------|
| X1 | AI Layout Assistant | Reconsider after 1.0 + 6 months feedback |
| X2 | Multi-provider AI abstraction | Pick one provider IF building AI at all |
| X3 | Custom constraint solver | Use anchors; never build cassowary |
| X4 | `.slbtmpl` ZIP archive format | Use JSON instead |
| X5 | Template Marketplace | Vapor until plugin has 5,000+ users |
| X6 | Cloud Sync (Git/S3) | Vapor; users can sync `~/.qgis/SLB/` themselves |
| X7 | Ed25519 template signing | No threat model justifies this |
| X8 | Telemetry backend | Use GitHub + Plugin Repo stats |
| X9 | Reproducible builds + signed releases | Out of proportion for OSS plugin |
| X10 | Multi-user `users` table | One profile, one user, period |
| X11 | `settings_audit` table | Settings dialog logs nothing |
| X12 | Vision/screenshot upload to AI | Don't open this can of worms |
| X13 | CLI mode (`qgis_process slb:…`) | Use native QGIS atlas CLI; no value-add |

---

## 4. What Gets Removed (vs Original Plan)

### 4.1 Entire features dropped from MVP

- F03 Adaptive Layout (deferred)
- F05 Dynamic Text Engine (deferred)
- F07 AI Layout Assistant (deferred indefinitely)
- F08 Report Export (deferred)
- F09 Live Preview (deferred; replaced with simple "open in Designer")
- F10 Template Marketplace (kill)
- F11 Cloud Sync (kill)
- F12 Template Manager — keep ONLY preset save/load (not template install/lock/migrate)
- F13 Onboarding Wizard (deferred to 1.1)
- F14 Export History (deferred to 1.1; then file-based not DB)

### 4.2 Architecture removed from MVP

| Removed | Replaced With |
|---------|---------------|
| Hexagonal architecture / ports / adapters | Flat module structure |
| DI container | Plain attributes on the plugin class |
| EventBus | Direct Qt signals where needed |
| Application use cases | Service methods on `LayoutService`/`ExportService` |
| Constraint solver | Fixed two-column composition |
| Custom `.slbtmpl` format | One JSON file per preset |
| SQLite database + 15 tables + migrations | `QSettings` + JSON files |
| AI provider abstraction | (not built) |
| Telemetry | (not built) |
| Public extensibility registries | (not built) |
| Processing provider | (not built; possible 1.x) |
| Localization for 5 languages | English only |

### 4.3 Documentation deferred

- ADRs system (do them lazily, only for choices that bite)
- mkdocs site (use the GitHub repo `README.md` + a `USAGE.md`)
- API reference auto-generation
- User docs for non-existent features

---

## 5. What Stays — A Tight MVP Footprint

The plugin should be approximately:

| Metric | Estimate |
|--------|----------|
| Python LOC | 2,500–4,000 |
| Top-level packages | 5–6 |
| External deps | 0 mandatory + 1 optional (`pypdf`) |
| Tests | 30–60 focused tests |
| CI targets | Linux + latest QGIS LTR + PyQt5 |
| Files in package | ~30–50 |

For comparison: this is similar in size to [DataPlotly](https://github.com/ghtmtt/DataPlotly), a well-loved QGIS plugin.

---

## 6. Suggested MVP Folder Structure

```
slb/
├── __init__.py             # classFactory
├── metadata.txt
├── plugin.py               # SmartLayoutBuilder: initGui, unload, wire signals
├── ui/
│   ├── dock.py             # SLBDock (Compose tab + Atlas tab in one widget)
│   ├── settings_dialog.py
│   └── designer/           # Optional .ui files
├── core/
│   ├── layout.py           # generate_layout(project, opts) -> QgsPrintLayout
│   ├── legend.py           # prune_legend(layout, rules)
│   └── strategies.py       # Two-column / single-column composition
├── export/
│   ├── atlas.py            # run_atlas(coverage, filter, out, fmt, on_progress, cancel)
│   ├── pdf_merge.py        # Optional, guarded by `pypdf` availability
│   └── progress.py         # QObject-based progress signaler
├── presets/
│   ├── repository.py       # CRUD over ~/.qgis/SLB/presets/*.json
│   └── defaults.py         # 2 default presets shipped with plugin
├── io/
│   └── safe_paths.py       # Atomic writes, path helpers
├── resources/
│   ├── icons/              # 4 SVGs
│   └── builtin_presets/    # 2 starter JSONs
└── utils/
    ├── logging.py
    └── qgis_compat.py      # tiny shim for QGIS version differences
```

That's the entire codebase. ~12 files of real code.

---

## 7. MVP Acceptance Criteria

The plugin is "MVP-done" when:

- [ ] Fresh QGIS profile installs the plugin from a ZIP.
- [ ] Plugin loads in ≤ 300ms (measured, not promised).
- [ ] User clicks "Generate Layout" → a `QgsPrintLayout` opens within 3s on a 10-layer project.
- [ ] Generated layout contains: title, map, pruned legend, scale bar, north arrow, attribution.
- [ ] "Open in Layout Designer" button works.
- [ ] User saves the current configuration as a named preset → JSON file appears in `~/.qgis/SLB/presets/`.
- [ ] User reloads QGIS → preset survives, is selectable.
- [ ] User runs Atlas → 56 PDFs produced in a folder, with correct filenames.
- [ ] Progress bar updates and ETA is approximately accurate.
- [ ] Cancel works; no half-written PDFs left.
- [ ] Optional: merged PDF contains 56 pages.
- [ ] Unload removes toolbar, dock, and the plugin reloads cleanly.
- [ ] README and `USAGE.md` cover the above flow.

If any of these fail, **fix before tagging 1.0**.

---

## 8. What the MVP Deliberately Does NOT Promise

Be explicit with users in the README:

- ❌ No AI assistance (yet).
- ❌ No marketplace.
- ❌ No cloud sync.
- ❌ No parallel atlas (yet).
- ❌ No adaptive layout (yet).
- ❌ Not a replacement for the native Layout Designer for advanced editing.
- ❌ English only.
- ❌ Beta-quality. Backups recommended.

Honesty here protects the plugin's reputation while it stabilizes.

---

## 9. Post-MVP — Earning the Right to Be Ambitious

After 1.0:

1. **Listen for 4 weeks.** What do users actually ask for? Atlas resume? Inset map? PNG output? Indonesian translation? Build the next 1.x release from real signal, not roadmap fantasy.
2. **Spike risky things in branches.** Parallel atlas, dynamic text tokens — proof-of-concept before promising.
3. **Stay narrow.** Resist scope creep. "Smart layout, smart legend, smart atlas." Not "QGIS but with AI".
4. **Re-evaluate AI from scratch.** By then you'll know if users want it (most won't).

---

## 10. Bottom Line

| Original Plan | Recommended MVP |
|---------------|-----------------|
| 14 features | 3 features |
| 11 docs | 2 docs (README + USAGE) |
| 15-table SQLite | 0 SQLite |
| 4 AI providers | 0 AI |
| 12-month roadmap | 6–8 weeks to 1.0-beta |
| Hexagonal + DI + ports | Flat ~6-module structure |
| 5 languages | English |
| Custom `.slbtmpl` | JSON files |
| Marketplace + Cloud Sync | (deleted) |
| Parallel atlas (week 10) | Sequential atlas + parallel as 1.3 spike |

**Build M1, M2, M3. Ship in 6 weeks. Let users tell you what 1.1 needs.**

---

*End of mvp-recommendation.md*
