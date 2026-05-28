# Executive Review — Smart Layout Builder Planning

> **Reviewer hat:** Senior PyQGIS engineer + long-term OSS plugin maintainer.
> **Subject:** All 13 planning documents under `docs/`.
> **Verdict — TL;DR:** The product idea is **strong and validated**. The planning documents describe **enterprise SaaS architecture grafted onto a QGIS plugin**, which would kill the project before MVP. Cut ~60% of the scope and architecture, ship a focused MVP in 6 weeks, then earn the right to expand.

---

## 1. Verdict Summary

| Dimension | Verdict |
|-----------|---------|
| **Is the problem real?** | ✅ Yes. QGIS layout workflow is genuinely painful, especially for batch atlas. |
| **Will real users adopt this?** | ✅ Likely. Government, NGO, and consultancy GIS teams need this. |
| **Is the proposed scope buildable?** | ❌ No, not on the stated timeline by a small team. |
| **Is the proposed architecture appropriate?** | ❌ No. It's enterprise architecture for a desktop plugin. |
| **Will the planned MVP ship?** | 🟡 Only after aggressive descoping. |
| **Probability of success as planned** | **~15%** |
| **Probability of success with recommended descope** | **~70%** |

---

## 2. The Big Picture

The plan is the equivalent of describing a *team of 8 engineers building a SaaS product* — DI containers, hexagonal architecture, port/adapter pattern, multi-user audit logs, marketplace + index server, cloud sync, Ed25519 signing, multi-provider AI abstraction with vision support, custom constraint solver, custom dynamic-text engine, custom template archive format, 80–90% test coverage with property-based + mutation + snapshot testing on a 3×3 OS×QGIS LTR CI matrix.

The reality is that **successful QGIS plugins are typically 2,000–15,000 lines maintained by 1–3 people in their spare time** ([qgis2web](https://github.com/tomchadwin/qgis2web), [QuickMapServices](https://github.com/nextgis/quickmapservices), [DataPlotly](https://github.com/ghtmtt/DataPlotly), [Profile Tool](https://github.com/PANOimagen/profiletool) — all in this range). Any plugin trying to mimic FAANG-style infrastructure either dies of complexity or never ships.

The good news: **the core product idea — "Auto Layout + Smart Legend + Batch Atlas" — is shipably small.** It's the supporting infrastructure that's bloated.

---

## 3. Biggest Strengths

1. **The problem statement is real and well-articulated.** Atlas export pain is exactly what GIS teams suffer through monthly. Smart legend pruning is genuinely valuable. These are not invented pain points.

2. **The persona work is grounded.** Rina (BPBD analyst), Marcus (consultant), Aulia (planner) — these are recognizable real users. The 8–12 minutes-per-PDF and 56-sub-district scenarios are credible.

3. **The feature inventory is well-decomposed.** F01–F14 with priorities, dependencies, and effort estimates is solid product hygiene.

4. **The UX direction is right.** Dock panel + wizard + tabs + live preview is the correct interaction model for QGIS. UX principles (UX1–UX9) are sensible.

5. **The cartographic discipline shows.** Sections about scale-bar units matching CRS, north-arrow rotation for projected CRSs, audience-driven density — this is the work of someone who understands cartography, not just software.

6. **The documentation quality is professional.** Mermaid diagrams, ADRs planned, ERDs, coding standards — these will help collaborators.

---

## 4. Biggest Risks (Top 7)

| # | Risk | Why It's Critical |
|---|------|-------------------|
| 1 | **Architecture overengineering** | Hexagonal + ports + adapters + DI for a QGIS plugin will burn ≥40% of dev time on infrastructure that delivers zero user value. |
| 2 | **Parallel atlas export design is dangerous** | Running N `QgsProject.read()` workers in `QgsTask` threads is a memory-intensive, race-prone reinvention of something QGIS deliberately keeps single-threaded. High crash risk. |
| 3 | **Custom constraint solver for "adaptive layout"** | Cassowary-lite is a multi-month project on its own. QGIS already has `attemptResize`, `referencePoint`, and layout item anchoring. Reinventing is unjustified. |
| 4 | **AI in Phase 3 with 4 providers + vision + cache + budget + sanitizer** | Premature. Validate the core layout product first; AI is a 6-month rabbit hole that will eclipse everything else. |
| 5 | **Marketplace + Cloud Sync + signing + index server** | Vapor scope. None of this is feasible until the plugin has thousands of users — which requires shipping first. |
| 6 | **Roadmap timeline is fiction** | 12 months from zero to 2.0 with marketplace and cloud sync implies ~3–4 engineers full-time. A solo maintainer should plan 18+ months *to MVP*. |
| 7 | **SQLite schema bloat (15+ tables)** | Multi-user tables, audit logs, AI cache, thumbnail cache, version history — most of this can be JSON files or QSettings. Adds maintenance + migration burden. |

---

## 5. What the Plan Got Wrong

### 5.1 Confusing "good engineering" with "appropriate engineering"

The architecture document is technically excellent if you're building a 100k-LOC enterprise system. For a QGIS plugin, **most of it is wrong by being right**: each abstraction is sensible in isolation; the total is suffocating.

Concrete examples:
- The domain layer "must not import `qgis.*`" — but the entire purpose of the domain is to manipulate `QgsPrintLayout`. Decoupling here forces a pointless translation layer.
- `IQGISBridge` Protocol with 12 methods — would-be-clever in a polyglot enterprise app, totally redundant when there's exactly one implementation.
- `Container` DI with `cached_property` singletons — Python modules already are singletons. This adds 200 LOC of plumbing for zero benefit.
- PyQt5/PyQt6 abstraction module — QGIS already provides `qgis.PyQt` which does exactly this.

### 5.2 Confusing future features with MVP features

Things labeled "MVP" that should not be:
- Layout Presets with version history, locking, source-tracking (`shipped`/`user`/`org`/`marketplace`).
- Template Manager with `.slbtmpl` ZIP format, manifests, schema migration, checksum signing.
- Onboarding Wizard with 4 pages + tooltip tour.
- Export History persistent log.
- 4 built-in templates + governance.

A real MVP is: *one button, get a layout. One button, get an atlas PDF.* Everything else is post-launch.

### 5.3 Speculative requirements treated as hard requirements

- "≥ 10,000 plugin installs in 12 months" — no validation; this is wish.
- "Generate 500 atlas pages in < 10 minutes" — possibly impossible for raster-heavy maps; no benchmark data.
- "≥ 80% line coverage" — fine as aspiration, lethal as gate on a 1-person project.

### 5.4 Treating a desktop plugin like a SaaS

- Telemetry backend ("self-hosted Plausible-like").
- Multi-user `users` table in a per-profile SQLite DB.
- `settings_audit` table.
- Reproducible builds + Ed25519 signatures + verified-author tier.

None of this is wrong in principle; all of it is wrong *now*.

### 5.5 Missing the most important question

Nowhere in the planning does the team ask: **what existing QGIS plugins overlap with this, and how do we differentiate?** Relevant prior art that the plan ignores:

- The native QGIS Atlas (works, just clunky UI).
- [Layout Manager](https://github.com/akbargumbira/qgis_layout_manager) (similar template idea).
- [QGIS Reports](https://docs.qgis.org/latest/en/docs/user_manual/print_composer/create_reports.html) (multi-section deliverables, native).
- [auto-print-composer / mapBuilder](https://plugins.qgis.org/plugins/?q=layout) plugins.

A planning doc that doesn't survey the prior art is planning blind.

---

## 6. Probability Analysis

### 6.1 As planned (full 12-month roadmap, full architecture)

**~15% probability of reaching 1.0 with all listed features.**

Failure modes (in order of likelihood):
1. Architecture phase eats 6+ weeks; team loses momentum; project goes dormant.
2. MVP ships but is buggy because of overengineering tax; community sours; plugin stagnates.
3. AI features delivered but layout core remains thin; users adopt for the wrong reasons.
4. Maintainer burnout at month 9.

### 6.2 With recommended descope (see `mvp-recommendation.md`)

**~70% probability of a shipped, adopted 1.0 in 8–10 weeks.**

Failure modes:
1. Atlas parallelism still risky — must mitigate with conservative defaults + single-threaded fallback.
2. Adoption depends on outreach (forum, blog, OSGeoLive inclusion) — not just code.

---

## 7. Recommended Direction

1. **Cut 60% of the plan.** Specifics in `mvp-recommendation.md` and `simplification-plan.md`.
2. **Replace hexagonal architecture with a flat, pragmatic structure.** ~6 top-level modules: `ui/`, `core/`, `export/`, `presets/`, `io/`, `utils/`. No ports. No DI. No "domain layer".
3. **Drop the entire AI subsystem from MVP.** Revisit only after 1.0 ships and gets feedback.
4. **Drop the constraint solver.** Use QGIS's native layout-item resizing.
5. **Drop the custom `.slbtmpl` format.** Use JSON for presets; consider native `.qpt` for whole-layout templates.
6. **Drop the marketplace, cloud sync, signing, telemetry backend.** All post-2.0 at earliest.
7. **Reduce SQLite to one table** — `presets`. Move everything else to QSettings + JSON files in `~/.qgis/SLB/`. Migrate to SQLite only when there's data justifying it.
8. **Ship to QGIS Plugin Repo at the end of week 6, not week 13.** "Beta" tag is fine.
9. **Replace the 12-month roadmap with a 3-month MVP + iterate plan.** See `revised-roadmap.md`.
10. **Validate atlas parallelism with a 200-line spike before committing to the design.** It may not be safely possible — better to know early.

---

## 8. What I'd Do If This Were My Project

If I inherited this planning, week 1 morning, I would:

1. Archive `docs/` as `docs/initial-vision/` and reference it.
2. Write a new 200-line `MVP.md` covering exactly 3 features: Auto Layout, Smart Legend Cleaner, Batch Atlas Export.
3. Spike the atlas parallelism in 2 days. If unsafe, fall back to sequential atlas with progress.
4. Build the dock panel + Auto Layout in week 2.
5. Build Smart Legend in week 3.
6. Build Atlas Export in weeks 4–5.
7. Polish + docs + Plugin Repo submission in week 6.
8. Tag `1.0.0-beta`, post to the QGIS forum, ask for feedback.
9. Iterate based on real users for 4 weeks before *thinking* about Phase 2.

That's it. Templates, AI, marketplace, cloud — they live in a backlog until users ask. Don't build for hypothetical users.

---

## 9. One-Sentence Bottom Line

> **The product is right. The architecture is wrong. Cut hard, ship in 6 weeks, then earn the right to be ambitious.**

---

*End of executive-review.md*
