# Architecture Review — Smart Layout Builder

> **Reviewer hat:** PyQGIS engineer with maintenance scars.
> **Format:** Each finding has Severity, Impact, and Recommendation.
> **Severity scale:** 🟥 Critical · 🟧 High · 🟨 Medium · 🟩 Low.

---

## A. Architectural Style

### A1 — 🟥 Hexagonal architecture is the wrong style for this plugin

**Finding.** The plan adopts ports + adapters + domain + application + infrastructure layers, with a hard rule that `domain/` cannot import `qgis.*`.

**Impact.**
- The plugin's *entire purpose* is to manipulate `QgsPrintLayout`, `QgsLegendModel`, and `QgsLayoutItem*`. A "domain" decoupled from these is either trivial (just dataclasses) or constantly translating between abstract and concrete shapes.
- Every new feature requires: domain entity → port → adapter → service → use case → UI binding. For a 50-line feature, you pay 200 lines of plumbing.
- Onboarding contributors will be brutal. PyQGIS volunteers rarely have hexagonal-architecture experience and will be discouraged.
- Solo maintainers cannot sustain 5-layer ceremony.

**Recommendation.** Use a **flat, pragmatic structure** with ~6 top-level packages:

```
slb/
├── plugin.py           # SmartLayoutBuilder, lifecycle
├── ui/                 # Widgets, dialogs, dock
├── core/               # Layout composition (allowed to import qgis.*)
├── export/             # Atlas + single export
├── presets/            # Preset CRUD (JSON files)
├── io/                 # Filesystem, ZIP helpers
└── utils/              # Small helpers, logging
```

No `ports/`, no `application/`, no `domain/`. Direct `qgis.*` imports where useful. Test by injecting a real `QgsProject` fixture, not a fake port.

---

### A2 — 🟧 Dependency-injection container is overkill

**Finding.** `infrastructure/container.py` with `cached_property` singletons for every service.

**Impact.**
- Python modules are already singletons.
- The DI container will need to be reasoned about every time you add a service.
- It hides dependencies behind a magic `self._container.layout_service`.

**Recommendation.** Construct services lazily on first use in `plugin.py`. If you need them shared, store them as plain attributes on the plugin class. ~30 LOC instead of ~300.

---

### A3 — 🟨 The "use case" layer is ceremony with no payoff

**Finding.** `application/generate_layout.py` wraps `LayoutEngine.compose()` in a `GenerateLayoutCommand` / `GenerateLayoutUC` / `GenerateLayoutResult` triplet.

**Impact.**
- For an interactive desktop plugin, each user action is one method call. Wrapping it in command/result objects is enterprise CQRS pattern theater.
- Use cases shine when you have multiple entry points (web + CLI + queue worker). SLB has one: the user clicking a button.

**Recommendation.** Skip use cases. Let widgets call services directly: `self.layout_service.generate(preset, paper)`.

---

### A4 — 🟧 PyQt5/PyQt6 abstraction layer reinvents `qgis.PyQt`

**Finding.** `slb/utils/qt.py` documented as a centralized re-export to shield against PyQt5↔6 differences.

**Impact.** QGIS already ships `qgis.PyQt.QtWidgets`, `qgis.PyQt.QtCore`, etc., which abstracts PyQt5/6 for plugins. The proposed shim duplicates this.

**Recommendation.** Delete the shim. Import directly from `qgis.PyQt.*`.

---

## B. Plugin Lifecycle

### B1 — 🟧 `initGui()` does too much

**Finding.** Plan describes DI bootstrap + toolbar + menu + dock + processing provider + welcome wizard all in `initGui()`.

**Impact.** `initGui()` runs synchronously at QGIS startup if the plugin is auto-loaded. Slow plugins degrade user experience and may be silently disabled by users blaming startup time.

**Recommendation.**
- `initGui()`: register actions + (empty) dock placeholder only. Target ≤ 100ms.
- Lazy-load services on first action invocation.
- Welcome wizard: schedule via `QTimer.singleShot(0, ...)` so QGIS finishes booting first.
- Processing provider: register synchronously (cheap) but defer algorithm import.

---

### B2 — 🟨 Unload path may leak signals

**Finding.** Plan's `unload()` removes actions + dock + processing provider. No mention of disconnecting `QgsProject` signals, `QgsMapLayerRegistry` signals, or the EventBus subscribers.

**Impact.** Reloading the plugin (Plugin Reloader is common in dev) will accumulate signal subscribers → crashes, double-execution, memory leaks.

**Recommendation.** Maintain a list of `(signal, slot)` tuples in the plugin class; `unload()` iterates and `disconnect`s each. The EventBus should expose a `dispose()` that drops every subscriber.

---

## C. Threading & Concurrency

### C1 — 🟥 Parallel atlas with N `QgsProject.read()` workers is dangerous

**Finding.** Atlas Orchestrator design slices the coverage into N subsets and runs N independent `QgsTask`s, each presumably opening its own `QgsProject` clone.

**Impact.**
- `QgsProject` is not designed to be cloned cheaply. Loading the same `.qgz` N times can multiply RAM by N (each layer pyramid, each style, each renderer).
- Many `QgsLayerProvider` backends (PostGIS, WFS, even GPKG with WAL) are *not thread-safe in parallel rendering*. Crashes are intermittent and hard to reproduce.
- `QgsMapRendererSequentialJob` can be run in workers, but rendering inside `QgsTask` already had bugs in QGIS 3.10–3.20. Today it's better but still finicky on some platforms.
- Symbolology cache contention between workers can degrade throughput vs serial.
- Cooperative cancellation across N workers + temp file cleanup + resume is a *substantial* subsystem.

**Recommendation.**
1. **Spike before committing.** Build a 200-line proof-of-concept and stress-test it on the matrix.
2. **Default to sequential atlas with good progress UI.** This alone beats native UX dramatically and ships safely.
3. **Add parallelism behind an experimental flag** once you have data. Cap workers at 2 to start; benchmark.
4. **Document raster-heavy projects as a known scaling cliff.**

This is the single most likely failure point in the entire architecture.

---

### C2 — 🟧 Event bus on the publishing thread will deadlock UI

**Finding.** "Handlers run on the publishing thread; long-running work must be re-dispatched to QgsTask."

**Impact.** This rule will be forgotten. The first time a long handler runs on the GUI thread, the UI freezes. The first time a UI handler runs on a worker thread, Qt crashes (cross-thread widget access).

**Recommendation.** Either:
- Adopt a strict "events delivered on GUI thread only" rule (use `Qt.QueuedConnection`), OR
- Drop the EventBus entirely in MVP. Use direct Qt signals between known emitter/receiver pairs.

The latter is simpler and equivalent for a plugin this size.

---

### C3 — 🟨 SQLite + WAL + multiple threads needs care

**Finding.** "One `sqlite3.Connection` per thread (use `threading.local`)."

**Impact.** Threading-local connections in `QgsTask` workers can leak when workers die abnormally. WAL files can grow without bound if checkpoints don't run.

**Recommendation.** If you can avoid SQLite for MVP (see `simplification-plan.md`), do so. If not, prefer a single thread for all DB access; queue write operations.

---

## D. Layout & Rendering

### D1 — 🟥 Custom constraint solver ("cassowary-lite") is a project of its own

**Finding.** The Adaptive Layout Engine is described as needing a 2D constraint solver to recompute item geometry on resize/orientation flip.

**Impact.**
- A real constraint solver is ~2,000–5,000 lines and a non-trivial test surface.
- QGIS layouts already have anchoring: `QgsLayoutItem::referencePoint`, `attemptResize()`, `setItemPosition()`, "fit to content" frames, and the `QgsLayoutPageCollection`.
- The proposed adaptive prompt for AI then double-checks the solver — needing AI to validate a solver you wrote suggests neither is trusted.

**Recommendation.**
- **Skip the constraint solver entirely.** Use a small set of declarative anchors in your composition strategy: each item declares `anchor: top-left | top-right | …`, padding from edge, and min size. On paper resize, recompute from anchors.
- **Adaptive layout becomes a Phase 2+ feature**, implemented in ~200 LOC.

---

### D2 — 🟧 Live debounced preview is risky to get right

**Finding.** "Renders preview at ≥ 24 fps when interactively dragging."

**Impact.** Live preview of a `QgsPrintLayout` is expensive. Hitting 24fps on a multi-layer A3 layout, even at low DPI, is *not realistic* on commodity hardware. Promising it sets the team up for cutting corners or failing.

**Recommendation.**
- Drop the fps target.
- Aim for **300ms-debounced re-render**, cancellable, with a clear "rendering…" indicator.
- Cache the previous render image; show it dimmed while the new one renders.
- Don't promise "interactive drag" — promise "responsive feedback after edits".

---

### D3 — 🟨 Smart Legend "feature count in extent" can be expensive

**Finding.** Legend pruning includes "out-of-extent layers — zero features visible".

**Impact.** Counting features per layer with a spatial filter is fast for indexed vectors, *slow* for unindexed and rasters, and *very slow* over network providers (WFS, PostGIS without proper indexes). Doing this for 50 layers can take seconds.

**Recommendation.**
- Use **spatial indexes only**; skip feature-count for raster layers (treat as "in extent if intersects bbox").
- Bound by a timeout (e.g., 50ms per layer); if it exceeds, default to "show in legend".
- Make the "extent pruning" rule **opt-in** (off by default) until tested across provider types.

---

## E. Storage & Persistence

### E1 — 🟥 SQLite schema is 5–10× larger than needed

**Finding.** 15+ tables, including `users`, `settings_audit`, `preset_versions`, `tags`, `preset_tags`, `template_presets`, `recent_projects`, `export_items`, `ai_requests`, `ai_responses`, `ai_budget`, `layer_thumb_cache`.

**Impact.**
- Each table is a migration, a model, a test, and a maintenance liability.
- Most tables describe features that **don't exist yet** (AI, marketplace, multi-user).
- The schema migration framework you'd build to support this is itself a maintenance load.

**Recommendation.**
- **MVP: no SQLite at all.** Use:
  - `QSettings("SLB", "SLB")` for runtime prefs.
  - `~/.qgis/SLB/presets/*.json` for presets.
  - `~/.qgis/SLB/history.jsonl` for export history (append-only, easy to trim).
- **Phase 2: introduce SQLite** only when you have features that need queries (cache eviction by LRU, hit-rate analytics).
- **No multi-user tables.** It's a per-profile desktop plugin.
- **No `settings_audit`.** Settings dialog is trivial; if a user breaks settings, "Reset to defaults" fixes it.

---

### E2 — 🟧 Custom `.slbtmpl` template format reinvents `.qpt`

**Finding.** Custom ZIP format with `manifest.json`, schema-versioned, Ed25519-signable, with `presets/`, `assets/`, `expressions/`, `i18n/` subfolders.

**Impact.**
- QGIS already has `.qpt` (XML layout template). Native support, native importers, no reinvention.
- A new format requires migrations, validators, sandboxed loaders, signing infrastructure, marketplace tooling, IDE/editor support, documentation.

**Recommendation.**
- **MVP: presets only**, stored as a single JSON file per preset (`<name>.slb.json`). Plain text, diff-friendly, no ZIP.
- **Optionally support importing native `.qpt`** — and don't try to compete with it.
- **Defer `.slbtmpl`** to Phase 3+ if/when org distribution becomes a real need.

---

## F. AI Subsystem

### F1 — 🟥 AI is in the architecture before the plugin exists

**Finding.** `ai/providers/`, `ai/prompts/`, sanitizer, cache, budget, schema validators — all designed before there's any layout composing.

**Impact.**
- AI design will leak into core design. Decisions about prompt shape will warp the layout engine's data model.
- "Validated by ConstraintSolver" couples two unbuilt subsystems together.
- 4 provider adapters × testing + maintenance + auth flows × the lifetime of the plugin = significant ongoing cost.

**Recommendation.**
- **Remove AI from the MVP plan entirely.** Don't include `ai/` directories until 1.x.
- After 1.0 ships and adoption is real, design AI as a *plugin to the plugin* — i.e., a separate plugin that depends on SLB's public API. This protects the core from AI's mess.
- If you must keep AI on the roadmap, commit to **one provider** (Anthropic or OpenAI), **one use case** ("Audit composition"), and **one prompt**. Iterate from there.

---

### F2 — 🟨 Vision/screenshot upload is a regulatory minefield

**Finding.** AI tab mentions optional "map screenshot" attachment for vision analysis.

**Impact.** Maps frequently contain regulated data: cadastral, health, defense, indigenous lands. Uploading a screenshot to a foreign cloud provider may violate organizational policy or law (Indonesia's UU PDP, EU GDPR, US ITAR variants).

**Recommendation.** If vision is ever added: opt-in per call (not per setting), with a clear preview of exactly what bytes will leave the machine, with provider region selection, and with org-policy override that can disable it globally.

---

## G. Folder Structure

### G1 — 🟧 Folder structure has too many empty nests

**Finding.** Proposed structure has 14 top-level packages under `slb/`, several with sub-packages that contain 1–2 files (`domain/value_objects/orientation.py`).

**Impact.** Volunteers will get lost. PR diffs span 6 directories per feature.

**Recommendation.** Collapse to ≤ 7 packages. Combine `value_objects` into the same file as the entity that uses them. Keep modules at ~100–500 lines each.

---

### G2 — 🟨 `infrastructure/qgis_adapter/` is misnomered

**Finding.** Calling QGIS an "external infrastructure" implies portability we'll never achieve.

**Impact.** QGIS is the platform, not infrastructure. Naming it as such reinforces the wrong mental model.

**Recommendation.** Drop the adapter framing entirely. Have a `core/qgis.py` helper for thin wrappers when useful.

---

## H. Extensibility & Public API

### H1 — 🟨 `slb.public` API stability promise is premature

**Finding.** Coding standards promise SemVer-stable `slb.public` API across MAJOR versions.

**Impact.** Stability promises *before users exist* lock you into bad early decisions. Almost every successful OSS plugin has rewritten its public API at least once.

**Recommendation.** Mark **everything `@beta`** until 1.0 has been in the wild for 6 months. Promise stability only on demand.

---

### H2 — 🟨 6 plugin extension points before there's one user

**Finding.** Plan exposes registries for composition strategies, AI providers, exporters, template loaders, tokens, panels.

**Impact.** Extension points must be designed for *real* extensions, not hypothetical ones. Each one is a maintenance commitment forever.

**Recommendation.** Ship MVP with **zero public extension points**. When the first real-world use case appears, design the extension point for that one case.

---

## I. Testing

### I1 — 🟥 80% coverage on a multi-OS × multi-QGIS-LTR matrix is unsustainable solo

**Finding.** CI matrix: Linux × Win × macOS × 3 QGIS LTRs × PyQt5/6 ≈ 12+ combinations, all blocking PR merges. 80% coverage. Property-based + mutation + snapshot + golden-PDF tests.

**Impact.**
- CI minutes will exceed GitHub free tier in week 1.
- A maintainer cannot debug 12 different breakages from a small PR.
- Snapshot/golden PDFs are brittle (Cairo version, font metrics, anti-aliasing differences).
- Mutation testing on a 5k LOC project takes hours per run.

**Recommendation.**
- **MVP CI**: Linux only, latest LTR only, PyQt5 only. Add OSes one at a time after 1.0.
- Coverage: **track**, don't gate. Aim for 60% as practical target.
- **No mutation testing.** Worth it at 50k LOC, not 5k.
- **No golden PDFs.** Visual regression is too brittle. Use focused assertions on layout XML (item types, positions ±tolerance).

---

### I2 — 🟨 Property-based + Hypothesis is overkill for current scope

**Finding.** Hypothesis for `ConstraintSolver`, `LegendCurator`, `DynamicTextEngine`, `PDFMerger`.

**Impact.** Hypothesis pays off for algorithms with subtle edge cases. The MVP doesn't have any such algorithm (no constraint solver, no dynamic text engine yet).

**Recommendation.** Defer Hypothesis until a feature legitimately calls for it. Plain unit tests with fixtures cover the MVP.

---

## J. Performance Promises

### J1 — 🟧 "Generate 500 atlas pages in < 10 minutes" is unsubstantiated

**Finding.** No benchmark data; no machine spec.

**Impact.** Setting a target you don't know is achievable means you'll either miss it (bad press) or optimize prematurely (wasted effort).

**Recommendation.** Drop specific page-count targets until you have a 1.0 with measured baselines. Replace with: *"Sequential atlas export is at least as fast as native QGIS, with better progress UX."* That's testable on day 1.

---

### J2 — 🟧 Plugin startup ≤ 100ms is aggressive without measurement

**Finding.** "Plugin import (`__init__.py`) must finish in **< 100 ms**."

**Impact.** Imports of `qgis.PyQt.QtWidgets` alone often exceed 100ms on cold start.

**Recommendation.** Measure with a real baseline. Target "no perceptible delay vs. unloaded QGIS startup". Don't lock yourself to a number without data.

---

## K. Memory Management

### K1 — 🟧 Bounded `maxImageSize` is a partial solution

**Finding.** "Memory-aware: rendering uses `QgsMapRendererSequentialJob` with bounded image size."

**Impact.** The big memory consumers in atlas export are **layer style caches, raster overviews, and label engine state** — not the output image buffer.

**Recommendation.** Profile actual atlas runs before designing memory ceilings. Document the heaviest scenarios (e.g., basemap + 5 raster overlays + 200 features) and benchmark.

---

## L. Cross-Cutting

### L1 — 🟨 Localization to 5 languages before MVP is premature

**Finding.** Plan ships EN + ID for MVP, ES/FR/ZH in Phase 2.

**Impact.** Maintaining translations during heavy churn doubles UI work. Translators get frustrated by string churn.

**Recommendation.**
- MVP: **English only.** Wrap strings in `self.tr(...)` from day 1 (good hygiene) but don't ship non-English `.qm` files yet.
- Add ID (Indonesian) right after MVP if there's a real user request.
- Other locales after 1.x stabilizes.

---

### L2 — 🟨 Telemetry backend before users exist

**Finding.** "Self-hosted Plausible-like backend" mentioned in privacy section.

**Impact.** Hosting infrastructure for a plugin that doesn't exist is the textbook definition of premature.

**Recommendation.** No telemetry for MVP. Post-1.0, use GitHub stars/issues + Plugin Repo install counter (provided free by QGIS).

---

## Severity Roll-Up

| Severity | Count | Notable |
|----------|-------|---------|
| 🟥 Critical | 5 | Hexagonal style, parallel atlas, constraint solver, SQLite bloat, AI scope, CI matrix |
| 🟧 High | 8 | DI container, lifecycle, PyQt shim, event bus threading, .slbtmpl, vision data, folder depth, perf targets |
| 🟨 Medium | 10 | Use-case layer, signal cleanup, smart-legend perf, schema audits, qgis-adapter naming, public API, extension points, hypothesis, startup, memory, i18n, telemetry |
| 🟩 Low | 0 | (Many smaller items were rolled up into Medium or omitted for signal.) |

---

## Architecture Verdict

**The architecture as designed is solid software engineering applied to the wrong context.** It's the kind of design that wins arguments in code review and loses races to shipment.

**Recommended action:** Rewrite `architecture.md` to ≤ 1 page after agreeing on the simplified structure in `simplification-plan.md`. Treat the original `architecture.md` as a *post-2.0 north star*, not a build instruction.

---

*End of architecture-review.md*
