# Smart Layout Builder — Coding Standards (MVP Rewrite)

> **Status:** Active. Supersedes the original 17-section enterprise standards.
> **Audience:** 1–2 maintainers and occasional drive-by contributors.
> **Tone:** Pragmatic. Conventions that prevent bugs and keep the code readable. Nothing more.

---

## 1. The Three Rules

1. **Readability over cleverness.** Future-you in 18 months should understand the code without notes.
2. **Less is more.** Every abstraction must justify itself. When in doubt, write the dumb version.
3. **Make errors easy to find.** Fail loudly, recover gracefully, never swallow silently.

If these are followed, everything below is mostly common sense.

---

## 2. Language & Versions

| Tool | Version |
|------|---------|
| Python | matches QGIS LTR (3.9+ today) |
| Type hints | required on public functions; optional inside |
| Style formatter | `black`, line length **100** |
| Linter | `ruff` with a sensible default ruleset |
| Type checker | `mypy` **non-strict** (catches obvious bugs without ceremony) |
| Pre-commit | runs `ruff` + `black` + `mypy` |

We **do not** use `mypy --strict`. That's enterprise-grade with diminishing returns on a 3k-LOC plugin.

---

## 3. Naming

| Kind | Convention | Example |
|------|------------|---------|
| Module | `snake_case` | `core/layout.py` |
| Class | `PascalCase` | `SLBDock`, `AtlasProgressReporter` |
| Function / method | `snake_case` | `generate_layout()`, `prune_legend()` |
| Constant | `SCREAMING_SNAKE_CASE` | `DEFAULT_PAPER = "A4"` |
| Private | `_leading_underscore` | `_validate()` |
| Boolean | `is_…`, `has_…`, `should_…`, `can_…` | `is_cancelled`, `has_legend` |
| Test file | `test_<module>.py` | `tests/unit/test_strategies.py` |

Aim for names that read like sentences. Avoid abbreviations except QGIS standard ones (`crs`, `mbr`, `bbox`, `dpi`).

---

## 4. Module Layout

Each module starts with a one-line docstring explaining its purpose:

```python
"""Atlas export — sequential, cancellable, with progress callbacks."""
from __future__ import annotations

# stdlib imports
import json
from pathlib import Path

# third-party (PyQGIS counts as platform)
from qgis.core import QgsProject, QgsPrintLayout

# in-package
from ..errors import ExportError
from ..io.safe_paths import atomic_write
```

Rules:
- `from __future__ import annotations` at the top of every module that uses type hints.
- Imports grouped: stdlib → PyQt/QGIS → local.
- No wildcard imports (`from x import *`).
- No re-exports from `__init__.py` unless there's a real reason.

---

## 5. Function Style

Functions should:
- Take their dependencies as arguments (not from globals).
- Return values (not mutate inputs) when reasonable.
- Stay under ~50 lines. If longer, split.
- Use keyword-only arguments for anything optional or non-obvious:

```python
def run_atlas(
    request: AtlasRequest,
    *,
    on_progress: ProgressCb | None = None,
    cancel_event: threading.Event | None = None,
) -> AtlasResult: ...
```

This makes call sites self-documenting and signatures additive-safe.

---

## 6. Class Style

Use classes when **state** lives across multiple calls (widgets, reporters, the plugin lifecycle class). Otherwise, prefer functions.

- Classes that only have a constructor + one method → that's a function.
- Avoid inheritance unless there's a real polymorphism story. `Composition over inheritance`.
- ABCs / Protocols only when there are **2+ concrete implementations today**.

---

## 7. Type Hints

Required on:
- Every function defined in `core/`, `export/`, `presets/`, `io/`.
- Every public method of a `QWidget` subclass.

Optional on:
- Inner helper functions.
- Test functions.

Style:
- `from __future__ import annotations` so we can write modern syntax (`list[int]`, `str | None`) on Python 3.9.
- `TypedDict` for dict shapes with known keys.
- Plain `dict[str, Any]` is fine if the structure is genuinely loose.
- **No `Any` in public function signatures.** Use `object` if you really mean "don't care".

---

## 8. Errors

Three rules:

1. **Raise typed.** Use the `SLBError` subclasses from `slb/errors.py`. Don't raise bare `Exception` or `ValueError` for user-facing failures.
2. **Chain causes.** Always `raise X from e` when wrapping.
3. **Provide a hint.** User-facing errors carry `hint=`:

```python
raise ValidationError(
    "Output folder is not writable.",
    hint="Choose a different folder or check permissions.",
)
```

UI catches `SLBError`, shows `str(e)` as the headline and `e.hint` below.

Never `except Exception: pass`. If you really need to swallow, log it at WARNING with a reason.

---

## 9. Logging

```python
import logging
log = logging.getLogger(__name__)

log.info("Atlas started: %d features", count)
log.warning("Layer %s timed out during legend prune; keeping it", layer_id)
log.exception("Unexpected failure during preset save")  # includes traceback
```

Rules:
- One logger per module, named via `__name__`.
- `info` for lifecycle / start-stop events.
- `warning` for recoverable issues.
- `error` / `exception` for failed operations.
- **Never** log secrets, full home paths (replace `~`), or full project content.

---

## 10. Comments

Default to **no comments**. Names should explain.

Write a comment **only when** the *why* is non-obvious:
- A workaround for a specific QGIS bug.
- An invariant that's not enforced by code.
- A constraint imposed from outside (e.g., file format quirk).

**Never** write comments that describe *what* the code does. `# loop over layers` adds nothing.

---

## 11. Immutability (Preferred, Not Required)

Prefer:
- Returning new dicts / lists rather than mutating arguments.
- Using `tuple` / `frozenset` for things that shouldn't change.
- Treating preset dicts as read-only after `load_preset()`.

Don't be religious about it. Mutating a local builder list inside a function is fine.

---

## 12. Qt / PyQGIS Conventions

### 12.1 Imports

Always import from `qgis.PyQt.*`, not directly from `PyQt5` / `PyQt6`:

```python
from qgis.PyQt.QtCore import Qt, QObject, pyqtSignal
from qgis.PyQt.QtWidgets import QDockWidget, QDialog
```

QGIS already abstracts PyQt5/6 for us. Don't build a second abstraction.

### 12.2 Signals

- Define signals at class level: `progress = pyqtSignal(int, str)`.
- Connect with object-style: `obj.signal.connect(self.slot)`. Avoid string-name connections.
- Track all connections in long-lived objects for cleanup (see §13).

### 12.3 No business logic in widgets

Widgets should:
- Build their UI.
- Emit signals on user actions.
- Receive signals to update UI state.
- Call `core/` / `export/` / `presets/` functions for behavior.

Widgets should NOT:
- Read/write JSON files directly (use `presets/`).
- Run long loops (use `QgsTask`).
- Catch generic `Exception` (catch `SLBError` and let unexpected ones bubble).

---

## 13. Signal Cleanup Convention

Plugin- and dock-lifetime classes track every connection so `unload()` / `close()` cleans up exhaustively:

```python
class SLBDock(QDockWidget):
    def __init__(self, iface, plugin):
        super().__init__()
        self._connections: list[tuple] = []
        self._connect(self.btn_generate.clicked, self._on_generate)
        self._connect(self.btn_atlas_start.clicked, self._on_atlas_start)

    def _connect(self, signal, slot):
        signal.connect(slot)
        self._connections.append((signal, slot))

    def closeEvent(self, event):
        for signal, slot in self._connections:
            try: signal.disconnect(slot)
            except (TypeError, RuntimeError): pass
        self._connections.clear()
        super().closeEvent(event)
```

This convention catches ~90% of "Plugin Reloader crashed QGIS" bugs.

---

## 14. Threading

| Rule | Why |
|------|-----|
| Long work in `QgsTask` | QGIS-native; integrates with task manager + progress UX |
| Don't use bare `threading.Thread` for anything touching QGIS | Cross-thread Qt is a foot-gun |
| `threading.Event` is fine for cancellation flags | Simple, no Qt dependency |
| Signal connections crossing threads use `Qt.QueuedConnection` (or rely on `QgsTask` callbacks) | Avoids reentrant UI calls |
| No `QApplication.processEvents()` in worker code | Ever |

---

## 15. Performance

- Don't optimize prematurely. Write the clear version first.
- Profile before micro-optimizing. `cProfile` + `snakeviz`.
- The likely hotspots are: legend pruning (feature counting) and atlas rendering loop. Everywhere else, readability wins.

**Performance budgets** (informational, not gates):

| Operation | Target |
|-----------|--------|
| Plugin import | "no perceptible delay" vs unloaded QGIS startup |
| `initGui()` | < 200 ms |
| `generate_layout` on 10-layer project | < 3 s |
| `prune_legend` (safe mode, 50 layers) | < 200 ms |

If we regress these, we measure and fix. We don't fail CI on them yet.

---

## 16. Testing

- Use `pytest`.
- One test file per source module (`tests/unit/test_<module>.py`).
- Arrange / Act / Assert layout, with blank lines between.
- Test names describe behavior, not implementation:

```python
def test_prune_legend_removes_hidden_layers(...): ...
def test_run_atlas_writes_one_pdf_per_feature(...): ...
def test_save_preset_rejects_unknown_role(...): ...
```

Coverage is **tracked, not gated**. Aim for 60% by 1.0.

See [`testing-strategy.md`](testing-strategy.md) for the longer version.

---

## 17. File Length Guidelines

Soft targets:
- Functions: < 50 lines.
- Modules: < 500 lines.
- Classes: < 300 lines.

If a file is growing past these, that's a signal — not a hard fail. Split when the split makes the codebase clearer, not when a number says so.

---

## 18. Internationalization

- Wrap user-visible strings in `self.tr(...)` from day 1 (good hygiene; ~zero cost).
- We ship English only at MVP.
- Pluralization: prefer `self.tr("Exported {n} files").format(n=count)`.

---

## 19. Tooling Config

`pyproject.toml`:

```toml
[tool.black]
line-length = 100
target-version = ["py39"]

[tool.ruff]
line-length = 100
target-version = "py39"
select = ["E", "F", "W", "I", "N", "B", "UP", "SIM", "RUF"]
ignore = ["E501"]   # line length is governed by black

[tool.ruff.per-file-ignores]
"tests/**" = ["S101"]    # asserts in tests are fine

[tool.mypy]
python_version = "3.9"
ignore_missing_imports = true   # PyQGIS stubs are incomplete
check_untyped_defs = false      # opt-in strict; not blanket
warn_unused_ignores = true
```

`pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/psf/black
    hooks: [{id: black}]
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks: [{id: ruff, args: [--fix]}]
  - repo: https://github.com/pre-commit/mirrors-mypy
    hooks: [{id: mypy, additional_dependencies: []}]
```

---

## 20. Git Conventions

- **Branches.** `main` is always releasable. Feature branches: `feat/<short>`, fixes: `fix/<issue-or-short>`.
- **Commits.** Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`). Subject ≤ 72 chars.
- **PRs.** Linked to an issue when relevant. CI must be green. One approving review (or self-merge if solo maintainer).
- **Squash merge** is the default.

---

## 21. Definition of Done (per PR)

```
[ ] CI green (ruff + black + mypy + pytest)
[ ] At least one test added or updated for behavioral changes
[ ] CHANGELOG.md updated under "## Unreleased" for user-visible changes
[ ] No new `Any` in public function signatures
[ ] No new `except Exception: pass`
[ ] No new TODO/FIXME without a linked issue
```

---

## 22. Code Review Checklist (Light)

Reviewer asks:

- [ ] Is the name clear?
- [ ] Does the function do one thing?
- [ ] Is the error chain obvious?
- [ ] Could a new contributor read this without help?
- [ ] Is there a test that would catch a regression?

That's it. Five questions.

---

## 23. What We Deliberately Don't Enforce

To set expectations:

- ❌ `mypy --strict`. Too noisy for a small plugin.
- ❌ 100% type hint coverage.
- ❌ Hexagonal / Clean / Onion architecture rules.
- ❌ "Domain may not import qgis.*".
- ❌ Mandatory ADRs for every decision.
- ❌ Performance regression gates (yet).
- ❌ Mutation testing.
- ❌ Property-based testing.
- ❌ Golden-output testing.
- ❌ Multi-OS CI matrix.

These are good practices when project size and bus factor demand them. We're a small plugin. We add what we need, when we need it.

---

## 24. Comparison With Original Plan

| Aspect | Original | Rewrite |
|--------|----------|---------|
| Sections | 17 | 24 (each shorter and more concrete) |
| Architecture rules | Hexagonal, Ports, Adapters, DI | None — flat structure |
| Type checking | `mypy --strict` | `mypy` non-strict |
| Test coverage | ≥ 80% gated | 60% target, tracked not gated |
| Error hierarchy | `SLBError` + ~10 subclasses | `SLBError` + 4 subclasses |
| Performance budgets | CI-enforced | Targets, fix if regressed |
| Logging | Structured JSON | Plain text |
| `Any` policy | Banned | Discouraged in public signatures |

---

## 25. Bottom Line

The standards fit on a few screens because the codebase is small. Once we've shipped 1.0 and the maintainer count grows, we can add rules as friction warrants. Until then, **readability and shipping** beat ceremony.

---

*End of coding-standards.md (lean rewrite).*
