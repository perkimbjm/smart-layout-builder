# Simplification Plan — Smart Layout Builder

> **Companion to:** [`architecture-review.md`](architecture-review.md), [`mvp-recommendation.md`](mvp-recommendation.md).
> **Approach:** For every overengineered system, name a leaner alternative and justify it.

---

## 1. The Simplification Lens

For each subsystem, we ask 4 questions:

1. **Who calls this today?** (Not: who might call it in 2027.)
2. **What's the simplest thing that could work?** (Often: a function in a module.)
3. **What does the simpler version lose?** (Often: nothing real.)
4. **What does it gain?** (Speed of iteration, fewer bugs, easier onboarding.)

---

## 2. Overengineered Systems & Their Replacements

### 2.1 Hexagonal Architecture (Ports + Adapters + Domain + Application)

**Original:**
```
ui/ → application/ → domain/ → ports/ ← infrastructure/
```
9 layers of indirection. The domain forbidden from importing `qgis.*`.

**Simpler alternative:**
```
ui/ → core/ → qgis.*
```
3 packages, direct imports.

**Lost:** The theoretical ability to swap out QGIS for another GIS platform. (Will never happen.)

**Gained:** ~70% less code; new contributors can understand the codebase in a single sitting.

---

### 2.2 Dependency-Injection Container

**Original:**
```python
class Container:
    @cached_property
    def bridge(self) -> IQGISBridge: ...
    @cached_property
    def storage(self) -> ITemplateStorage: ...
    # ~20 more
    @cached_property
    def layout_service(self) -> LayoutService: ...
```

**Simpler alternative:** Plain attributes on the plugin class, lazy-initialized on first use.

```python
class SmartLayoutBuilder:
    def __init__(self, iface):
        self.iface = iface
        self._layout_service = None
        self._export_service = None

    @property
    def layout_service(self):
        if self._layout_service is None:
            self._layout_service = LayoutService(self.iface)
        return self._layout_service
```

**Lost:** Ability to swap mocks via container. (Tests can construct services directly.)

**Gained:** ~200 LOC and one fewer mental model.

---

### 2.3 EventBus

**Original:** Custom `IEventBus` with `subscribe()`/`publish()`/`Unsubscribe`, 11 event types.

**Simpler alternative:** Qt signals between objects that already know each other.

```python
# In LayoutService:
class LayoutService(QObject):
    layoutGenerated = pyqtSignal(str)  # layout_name

# In SLBDock.__init__:
self.layout_service.layoutGenerated.connect(self.on_layout_generated)
```

**Lost:** Loose coupling between *unknown* publishers and subscribers. (None exist.)

**Gained:** Native Qt threading semantics (queued connections), no custom thread rules to remember.

---

### 2.4 Use-Case Layer

**Original:**
```
GenerateLayoutUC(deps).execute(GenerateLayoutCommand(req)) → GenerateLayoutResult
```

**Simpler alternative:**
```python
service.generate_layout(preset_id, paper, orientation) -> str
```

**Lost:** Hypothetical CLI + queue worker reuse. (Native QGIS already has a CLI.)

**Gained:** Half the files; obvious code.

---

### 2.5 Constraint Solver

**Original:** Custom cassowary-lite 2D constraint solver for adaptive layout.

**Simpler alternative:** Anchor-based recomputation.

```python
# Each item declares its anchor:
item = {"role": "legend", "anchor": "top-right", "w_mm": 80, "h_mm": 120, "pad_mm": 5}

# On paper resize, recompute:
def place(item, paper_w, paper_h):
    if item["anchor"] == "top-right":
        item["x_mm"] = paper_w - item["w_mm"] - item["pad_mm"]
        item["y_mm"] = item["pad_mm"]
    # ...
```

**Lost:** Truly novel layouts. (Users don't ask for these.)

**Gained:** 200 LOC instead of 2,000. No solver to debug.

---

### 2.6 SQLite Database

**Original:** 15 tables, migrator, WAL mode, triggers, views, retention policy, multi-user.

**Simpler alternative:**

| Concern | New Storage |
|---------|-------------|
| User prefs | `QSettings("SLB","SLB")` |
| Presets | `~/.qgis/SLB/presets/<name>.json` (one file per preset) |
| Export history | `~/.qgis/SLB/history.jsonl` (append-only, line-delimited JSON; trim with `tail` of last 200 lines on write) |
| AI cache (future) | `~/.qgis/SLB/cache/ai/<hash>.json` with mtime-based TTL |
| Layer thumb cache | Stored as files; LRU evicted by `os.walk` mtime sort |

**Lost:** Query power (rare for this product); transactions across tables (we don't have that).

**Gained:**
- No migrations.
- Trivially inspectable / editable by users.
- Easy backup (zip the folder).
- No locked-DB errors.
- Removable: if the user deletes the folder, the plugin still works (defaults).

When SQLite becomes warranted (5+ tables actually needed; analytics queries), introduce it then.

---

### 2.7 Custom `.slbtmpl` Template Format

**Original:** ZIP archive with `manifest.json`, `presets/`, `assets/`, `expressions/`, `i18n/`, schema-versioned, Ed25519-signable.

**Simpler alternative:** One JSON file per preset.

```json
{
  "schema": 1,
  "name": "Classic A4",
  "paper": "A4",
  "orientation": "portrait",
  "items": [
    {"role":"title","anchor":"top","h_mm":12,"style":{"font_size_pt":18}},
    {"role":"map","fill":"center"},
    {"role":"legend","anchor":"bottom-left","w_mm":80,"h_mm":50},
    {"role":"scale_bar","anchor":"bottom","h_mm":10},
    {"role":"north_arrow","anchor":"bottom-right","w_mm":20,"h_mm":20},
    {"role":"attribution","anchor":"bottom","h_mm":5}
  ]
}
```

**Lost:** Bundled assets (logos, custom SVGs). (Users can reference paths.) Locking. Signing.

**Gained:**
- Diff-friendly in Git.
- Shareable by email / Slack / pastebin.
- No ZIP-slip vulnerability.
- No schema migration framework.

Later, if assets become important, sidecar them: `<preset>.json` + `<preset>.assets/`. Don't preemptively ZIP.

---

### 2.8 AI Provider Abstraction

**Original:** `IAIProvider` Protocol + OpenAI + Anthropic + Azure-OpenAI + Ollama adapters, prompt library, JSON schema validation, response cache, budget tracker, sanitizer.

**Simpler alternative for if/when AI is built:** One file, one provider.

```python
# slb/ai.py  (single file)
def ai_audit_layout(prompt: str, layout_summary: dict) -> dict:
    """Sends a single prompt to the configured provider, returns parsed JSON."""
    api_key = keyring.get_password("slb", "ai.api_key")
    if not api_key:
        raise SLBError("AI not configured")
    # ... 50 lines of HTTP call
    # ... 20 lines of JSON Schema validation
    return parsed
```

**Lost:** Multi-provider portability. (Add it when a user asks.)

**Gained:** ~70 lines instead of ~700.

---

### 2.9 Localization (5 Languages × Translation Pipeline)

**Original:** EN + ID at MVP; ES + FR + ZH in Phase 2. CI sync from Transifex. `pylupdate5` + `lrelease` pipeline. Per-locale `metadata.txt` blocks. Localized `description[id]=...`.

**Simpler alternative:**
- English only at MVP.
- Wrap strings in `self.tr(...)` from day 1 (good hygiene, zero cost).
- Add `.ts` / `.qm` plumbing the *first* time a translator volunteers.

**Lost:** Indonesian-speaking users get English. (They can read English; many GIS terms are already English.)

**Gained:** Skip an entire weekend of build pipeline setup.

---

### 2.10 Public API + Extension Registries

**Original:** 6 registries (composition, AI, exporters, templates, tokens, panels), `slb.public`, stability tiers.

**Simpler alternative:** **Skip entirely for MVP.** Don't promise a public API until someone asks for one with a concrete use case.

**Lost:** Third-party plugins extending SLB. (No such plugins exist yet.)

**Gained:** Freedom to refactor internals during 1.x without breaking promises.

---

### 2.11 Telemetry

**Original:** Opt-in telemetry sending events to a self-hosted backend.

**Simpler alternative:** Don't ship any telemetry. Use Plugin Repo's free install counter; use GitHub for issue volume.

**Lost:** Detailed usage analytics. (Probably nobody would opt in anyway.)

**Gained:** No backend to host; no privacy policy to write; no opt-in UI to maintain.

---

### 2.12 Reproducible Builds + Signed Releases

**Original:** Deterministic ZIP, Ed25519 signatures, public key registry, `make verify-build`.

**Simpler alternative:** Ship via QGIS Plugin Repo (which is the trusted distribution). Tag releases in GitHub. Done.

**Lost:** Supply-chain attack resistance against a determined adversary. (For a layout plugin, this is firmly out of the threat model.)

**Gained:** Hours of release engineering.

---

### 2.13 CI Matrix

**Original:** 3 OSes × 3 QGIS LTRs × 2 PyQts = up to 12 combinations on every PR.

**Simpler alternative:**
- PR CI: Linux + latest QGIS LTR + PyQt5.
- Release CI: Add Windows + macOS on tags.
- Drop PyQt6 until QGIS deprecates PyQt5.

**Lost:** Same-PR confidence on Windows/macOS bugs. (Most plugin bugs are platform-agnostic.)

**Gained:** ~80% less CI minutes; faster PRs.

---

### 2.14 Test Suite Scale

**Original:** Property-based (Hypothesis), mutation testing (mutmut), snapshot testing, golden-PDF tests, performance benchmarks with regression budgets.

**Simpler alternative:**
- Plain `pytest` unit tests.
- A small handful of integration tests with a real `QgsProject` fixture.
- One or two atlas tests on a 5-feature `.qgz`.
- Coverage tracked, not gated.

**Lost:** Coverage of every conceivable edge case. (We'd rather find them via users.)

**Gained:** Test suite that runs in 30s on a laptop and 60s in CI.

---

## 3. Folder Structure — Before & After

### Before (excerpted)

```
slb/
├── application/
├── domain/
│   ├── entities/
│   ├── value_objects/
│   ├── engine/
│   │   └── strategies/
│   ├── policies/
│   └── errors.py
├── ports/
├── infrastructure/
│   ├── qgis_adapter/
│   ├── storage/
│   │   └── migrations/
│   ├── filesystem/
│   ├── http/
│   ├── secrets/
│   ├── event_bus/
│   ├── logging/
│   └── i18n/
├── ui/
│   ├── docks/
│   ├── dialogs/
│   ├── wizards/
│   │   └── pages/
│   ├── widgets/
│   ├── designer/
│   └── theme/
├── io/
│   ├── exporters/
│   ├── templates/
│   │   └── migrations/
│   ├── presets/
│   └── history/
├── ai/
│   ├── providers/
│   ├── prompts/
│   ├── schemas/
│   ├── cache/
│   └── …
├── services/
├── i18n/
├── resources/
└── utils/
```

~30 directories, ~10 levels of nesting in places.

### After

```
slb/
├── __init__.py
├── metadata.txt
├── plugin.py
├── core/
│   ├── layout.py
│   ├── legend.py
│   └── strategies.py
├── export/
│   ├── atlas.py
│   ├── pdf_merge.py
│   └── progress.py
├── ui/
│   ├── dock.py
│   ├── settings_dialog.py
│   └── designer/        # .ui files
├── presets/
│   ├── repository.py
│   └── defaults.py
├── io/
│   └── safe_paths.py
├── resources/
│   ├── icons/
│   └── builtin_presets/
└── utils/
    ├── logging.py
    └── qgis_compat.py
```

7 directories. Every file purpose obvious.

---

## 4. The Maintainability Win

| Metric | Original Plan | Simplified |
|--------|---------------|------------|
| Top-level packages | 14 | 7 |
| LOC estimate | 10,000–15,000 | 2,500–4,000 |
| External runtime deps | ~5 | 0–1 (`pypdf` optional) |
| SQL tables | 15 | 0 |
| Custom file formats | 1 (`.slbtmpl`) | 0 |
| AI providers | 4 | 0 |
| Architectural layers | 5 | 2 (ui / core) |
| Onboarding time for a new contributor | days | hours |
| Time to MVP | 13 weeks (per plan) | 6–8 weeks |
| Bus factor | requires architecture initiation | any QGIS plugin dev |

---

## 5. The "Resist These Temptations" List

During implementation, the team will be tempted to:

1. **"Let's just add a tiny EventBus, it'll be useful later."** — No. Use Qt signals.
2. **"We need a Container so testing is easier."** — No. Tests construct objects directly.
3. **"Let's add SQLite for export history."** — No. JSONL file.
4. **"Let's vendor `pypdf` so it always works."** — No. Optional dependency with feature degradation.
5. **"Adding AI before launch would be a wow factor."** — No. Wow nobody if it crashes.
6. **"Let's design a `BaseExporter` ABC so we can add SVG/PNG later."** — No. Add it when you add the second format.
7. **"We should support PyQt6 from day one."** — No. Wait for QGIS to deprecate PyQt5.
8. **"A wizard would be more friendly."** — Defer. Tooltips on the dock.
9. **"Let's add a 'compose with AI' toggle behind a feature flag."** — No. Toggles you don't ship are dead weight.
10. **"Constraint-solving layout is more elegant."** — Yes, and irrelevant. Ship anchor-based.

Print this list. Stick it on the wall.

---

## 6. The Compounding Benefit

Each simplification cascades:

- No DI → no fakes needed → fewer test files.
- No SQLite → no migrations → no migration tests → no schema docs.
- No custom format → no validators → no migrators → no docs.
- No AI → no sanitizer → no schemas → no providers → no privacy policy.
- No marketplace → no signing → no index server → no key management.

The simplifications **multiply**. Together they're the difference between shipping in 6 weeks and not shipping.

---

## 7. When to Re-Introduce Complexity

Add a layer of architecture **only when**:

- A real user has asked for the feature (twice).
- The current code is the bottleneck (measured, not imagined).
- The new abstraction has at least 2 concrete current implementations (not "we might add X later").

If none of those are true, the abstraction is premature.

---

*End of simplification-plan.md*
