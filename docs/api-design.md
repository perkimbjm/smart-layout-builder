# Smart Layout Builder — Internal API (MVP Rewrite)

> **Status:** Active. Supersedes the original ports/adapters/use-cases API.
> **Scope:** Internal-only. **There is no public Python API** in MVP. Refactor freely.

---

## 1. Philosophy

- Functions over classes. Classes only when state is needed.
- Plain `dict` over `dataclass`. Promote to `dataclass` when invariants justify it.
- Direct PyQGIS calls — no port/adapter layer.
- No registries, no factories, no ABCs for "future providers".
- Signatures should be readable in one line.

---

## 2. Surface Area Summary

```
core/layout.generate_layout(project, options) -> QgsPrintLayout
core/legend.prune_legend(layout, project, mode) -> int
core/strategies.two_column(paper_w, paper_h, margin) -> list[ItemSpec]
core/strategies.single_column(paper_w, paper_h, margin) -> list[ItemSpec]

export/atlas.run_atlas(request, on_progress, cancel_event) -> AtlasResult
export/pdf_merge.merge_available -> bool
export/pdf_merge.merge_pdfs(paths, out_path) -> None

presets/repository.list_presets() -> list[PresetMeta]
presets/repository.load_preset(name) -> dict
presets/repository.save_preset(name, data) -> Path
presets/repository.delete_preset(name) -> None
presets/defaults.ensure_defaults_installed() -> None

io/safe_paths.user_dir() -> Path
io/safe_paths.atomic_write(path, data) -> None
io/safe_paths.safe_filename(s) -> str

errors.SLBError, ValidationError, ExportError, ExportCancelled, PresetError
```

That's it. ~15 functions + ~5 exceptions. A new contributor can read the whole API in 30 minutes.

---

## 3. `core/layout`

```python
# slb/core/layout.py

from qgis.core import QgsProject, QgsPrintLayout

def generate_layout(
    project: QgsProject,
    *,
    paper: str = "A4",                     # "A4" | "A3" | "Letter"
    orientation: str = "portrait",         # "portrait" | "landscape"
    preset: dict | None = None,            # see preset JSON shape in architecture.md §6.3
    title: str | None = None,              # override; default uses project_title()
    prune_legend_mode: str = "safe",       # "safe" | "extent" | "off"
    output_layout_name: str | None = None,
) -> QgsPrintLayout:
    """Compose a balanced QgsPrintLayout from the project's current state.

    The returned layout is already added to project.layoutManager().
    Raises ValidationError if project has no layers or paper/orientation invalid.
    """
```

Implementation outline:
1. Validate inputs.
2. Pick strategy from `preset` or default by orientation.
3. Materialize items into `QgsLayoutItemMap` / `QgsLayoutItemLegend` / etc.
4. Call `prune_legend(layout, project, mode=prune_legend_mode)`.
5. Add to layout manager; return.

**No `LayoutRequest` / `LayoutResult` dataclasses.** Direct keyword arguments; direct `QgsPrintLayout` return.

---

## 4. `core/legend`

```python
# slb/core/legend.py

from qgis.core import QgsPrintLayout, QgsProject

def prune_legend(
    layout: QgsPrintLayout,
    project: QgsProject,
    mode: str = "safe",                    # "safe" | "extent" | "off"
    extent_timeout_ms: int = 50,
) -> int:
    """Remove unwanted legend items from `layout`.

    Returns the number of items pruned.

    Idempotent: running twice produces the same result.

    Modes:
      - "safe": drop LegendExcluded + invisible-in-project layers.
      - "extent": also drop layers with 0 features in current map extent.
      - "off": no-op (returns 0).
    """
```

Implementation notes:
- Finds the `QgsLayoutItemLegend` in `layout.items()`.
- For "extent" mode, uses `QgsFeatureRequest().setFilterRect(extent)` with a per-layer wall-clock timeout. Skips raster layers (treats "intersects bbox" as in-extent).

---

## 5. `core/strategies`

```python
# slb/core/strategies.py

from typing import TypedDict

class ItemSpec(TypedDict, total=False):
    role: str       # "title" | "map" | "legend" | "scale_bar" | "north_arrow" | "attribution"
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float
    style: dict     # role-specific styling hints
    binding: str    # optional QGIS expression for text items


def two_column(paper_w_mm: float, paper_h_mm: float, margin_mm: float = 10.0) -> list[ItemSpec]:
    """Landscape-friendly: title across top, map left ~2/3, sidebar right."""

def single_column(paper_w_mm: float, paper_h_mm: float, margin_mm: float = 10.0) -> list[ItemSpec]:
    """Portrait-friendly: title, map, then footer row with legend+scale+arrow."""
```

Pure functions. Trivially testable. No solver, no class hierarchy, no strategy registry.

---

## 6. `export/atlas`

```python
# slb/export/atlas.py

from pathlib import Path
from typing import Callable, TypedDict
import threading

from qgis.core import QgsProject, QgsPrintLayout, QgsVectorLayer

class AtlasRequest(TypedDict, total=False):
    layout: QgsPrintLayout
    coverage: QgsVectorLayer
    filter_expression: str | None
    output_dir: Path
    filename_template: str         # e.g. "peta_[%kelurahan%].pdf"
    fmt: str                       # "pdf" only in MVP
    dpi: int                       # default 300
    merge_into_single_pdf: bool    # only if pdf_merge.merge_available

class AtlasResult(TypedDict):
    output_paths: list[Path]
    failed: list[dict]             # [{"feature_id": ..., "error": "..."}]
    duration_seconds: float
    cancelled: bool

ProgressCb = Callable[[int, str], None]   # (percent_0_100, current_label)

def run_atlas(
    request: AtlasRequest,
    on_progress: ProgressCb | None = None,
    cancel_event: threading.Event | None = None,
) -> AtlasResult:
    """Sequentially export one file per coverage feature.

    - Atomic writes (tmp/ subfolder + os.replace).
    - Cooperative cancel between features.
    - Optional PDF merge at end if requested and merge_available.

    Raises ValidationError for bad inputs.
    Raises ExportError for non-recoverable mid-export errors.
    Returns AtlasResult with `cancelled=True` if cancelled mid-flight.
    """
```

The function is **synchronous**. It runs inside a `QgsTask` — the task wraps it; the function itself doesn't know about tasks. This makes it directly testable without QGIS UI machinery.

---

## 7. `export/progress`

```python
# slb/export/progress.py

from qgis.PyQt.QtCore import QObject, pyqtSignal

class AtlasProgressReporter(QObject):
    """Bridges sync worker callbacks → Qt signals for UI consumption."""

    progress = pyqtSignal(int, str)        # percent_0_100, label
    finished = pyqtSignal(dict)            # AtlasResult
    failed   = pyqtSignal(str, str)        # error_class_name, message
```

The dock owns one reporter, passes its `progress.emit` as `on_progress` to `run_atlas`, and connects to the signals for UI updates.

---

## 8. `export/pdf_merge`

```python
# slb/export/pdf_merge.py

from pathlib import Path

try:
    import pypdf
    merge_available = True
except ImportError:
    try:
        import PyPDF2 as pypdf       # noqa: F811
        merge_available = True
    except ImportError:
        merge_available = False

def merge_pdfs(paths: list[Path], out_path: Path) -> None:
    """Merge `paths` into a single PDF at `out_path`.
    Raises ExportError if merge_available is False.
    Atomic: writes to a temp file, then os.replace.
    """
```

This file degrades gracefully when neither `pypdf` nor `PyPDF2` is available. The dock hides the merge checkbox in that case.

---

## 9. `presets/repository`

```python
# slb/presets/repository.py

from pathlib import Path
from typing import TypedDict

class PresetMeta(TypedDict):
    name: str
    path: Path
    paper: str
    orientation: str

def list_presets() -> list[PresetMeta]:
    """List preset metadata for all JSON files in ~/.qgis/SLB/presets/."""

def load_preset(name: str) -> dict:
    """Load and return the preset's raw dict. Raises PresetError if missing or invalid."""

def save_preset(name: str, data: dict) -> Path:
    """Atomic-write the preset JSON. Raises PresetError on invalid data."""

def delete_preset(name: str) -> None:
    """Delete the named preset. Raises PresetError if missing."""
```

Validation is minimal: must have `name`, `paper`, `orientation`, `items` keys. If `schema != 1`, raise `PresetError` (no migrator yet).

---

## 10. `presets/defaults`

```python
# slb/presets/defaults.py

def ensure_defaults_installed() -> None:
    """On first run (or when a bundled preset is missing from user dir),
    copy slb/resources/builtin_presets/*.json → ~/.qgis/SLB/presets/.

    Existing user presets with the same name are NOT overwritten.
    """
```

Called once from `plugin.initGui()` (cheap; ~5 ms).

---

## 11. `io/safe_paths`

```python
# slb/io/safe_paths.py

from pathlib import Path

def user_dir() -> Path:
    """Returns ~/.qgis/SLB/ (creating it if missing).
    Honors QGIS user-profile dir on all platforms.
    """

def atomic_write(path: Path, data: bytes | str) -> None:
    """Write to `path.tmp`, then os.replace to `path`."""

def safe_filename(s: str) -> str:
    """Sanitize a string for use as a filename. Removes \\/:*?<>| etc.
    Truncates to 200 chars. Returns 'unnamed' if input is empty after sanitization.
    """

def ensure_dir(path: Path) -> Path:
    """mkdir(parents=True, exist_ok=True); return the path."""
```

---

## 12. `errors`

```python
# slb/errors.py

class SLBError(Exception):
    """Base for all user-facing SLB errors."""
    def __init__(self, message: str, *, hint: str = ""):
        super().__init__(message)
        self.hint = hint

class ValidationError(SLBError):
    """Bad input. The user can fix this."""

class ExportError(SLBError):
    """An export failed. May or may not be recoverable."""

class ExportCancelled(ExportError):
    """The user cancelled the export. Not a real failure."""

class PresetError(SLBError):
    """Preset file is missing, invalid, or could not be saved."""
```

Five classes, one file, ~20 LOC.

---

## 13. Plugin Lifecycle Skeleton

```python
# slb/plugin.py

from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from .utils.logging import configure_logging
from .presets.defaults import ensure_defaults_installed

class SmartLayoutBuilder:
    def __init__(self, iface):
        self.iface = iface
        self._dock = None
        self._actions: list[QAction] = []
        self._connections: list = []          # (signal, slot) for cleanup

    def initGui(self):
        configure_logging()
        ensure_defaults_installed()

        action = QAction(QIcon(":/slb/logo.svg"), "Smart Layout Builder", self.iface.mainWindow())
        action.triggered.connect(self._show_dock)
        self.iface.addPluginToMenu("Smart Layout Builder", action)
        self.iface.addToolBarIcon(action)
        self._actions.append(action)

    def unload(self):
        for signal, slot in self._connections:
            try: signal.disconnect(slot)
            except (TypeError, RuntimeError): pass
        self._connections.clear()

        for a in self._actions:
            self.iface.removePluginMenu("Smart Layout Builder", a)
            self.iface.removeToolBarIcon(a)
        self._actions.clear()

        if self._dock is not None:
            self.iface.removeDockWidget(self._dock)
            self._dock.deleteLater()
            self._dock = None

    def _show_dock(self):
        if self._dock is None:
            from .ui.dock import SLBDock
            self._dock = SLBDock(self.iface, self)
            self.iface.addDockWidget(2, self._dock)   # Qt.RightDockWidgetArea
        self._dock.show()
        self._dock.raise_()
```

That's the lifecycle. No DI container. No event bus. No service locator. ~40 LOC.

---

## 14. Dock Wiring Skeleton

```python
# slb/ui/dock.py  (sketch only — no implementation in this rewrite)

from qgis.PyQt.QtCore import Qt, QThread
from qgis.PyQt.QtWidgets import QDockWidget, QTabWidget, QWidget, QVBoxLayout
from qgis.core import QgsApplication
from ..core.layout import generate_layout
from ..core.legend import prune_legend
from ..export.atlas import run_atlas
from ..export.progress import AtlasProgressReporter
from ..presets import repository as presets_repo
from ..errors import SLBError

class SLBDock(QDockWidget):
    def __init__(self, iface, plugin):
        super().__init__("Smart Layout Builder")
        self.iface = iface
        self.plugin = plugin
        self._build_ui()                              # builds compose + atlas tabs
        self._wire_signals()                          # connects button.clicked → self._on_*

    def _on_generate_clicked(self):
        try:
            preset = presets_repo.load_preset(self._current_preset_name())
            layout = generate_layout(
                QgsProject.instance(),
                paper=self._current_paper(),
                orientation=self._current_orientation(),
                preset=preset,
            )
            self.iface.openLayoutDesigner(layout)
        except SLBError as e:
            self._show_error(e)

    def _on_atlas_start_clicked(self):
        # Build AtlasRequest from form, wrap run_atlas in a QgsTask, connect progress.
        ...
```

---

## 15. Convention: Signal Connection Tracking

Every `signal.connect(slot)` in long-lived objects (plugin class, dock) appends a tuple to a list, so cleanup is exhaustive:

```python
def _connect(self, signal, slot):
    signal.connect(slot)
    self.plugin._connections.append((signal, slot))

# usage
self._connect(self.btn_generate.clicked, self._on_generate_clicked)
```

This is a tiny convention and prevents 90% of "plugin reloader crashed QGIS" bugs.

---

## 16. Convention: All Long Work in `QgsTask`

```python
class AtlasTask(QgsTask):
    def __init__(self, request, reporter, cancel_event):
        super().__init__("SLB Atlas Export", QgsTask.CanCancel)
        self.request = request
        self.reporter = reporter
        self.cancel_event = cancel_event
        self.result = None

    def run(self) -> bool:
        self.result = run_atlas(
            self.request,
            on_progress=lambda pct, msg: self.reporter.progress.emit(pct, msg),
            cancel_event=self.cancel_event,
        )
        return not self.result["cancelled"]

    def cancel(self):
        self.cancel_event.set()
        super().cancel()
```

The worker function (`run_atlas`) stays sync and testable; the task is a thin shim.

---

## 17. Testing Surface

Each public function gets at least one test:

| Function | Test goals |
|----------|-----------|
| `generate_layout` | Returns `QgsPrintLayout` with expected item roles; respects paper/orientation |
| `prune_legend` | `safe` mode removes hidden+excluded; `extent` mode removes empty-extent layers; idempotent |
| `two_column` / `single_column` | Items don't overlap; items don't escape paper |
| `run_atlas` | 5-feature fixture → 5 PDFs; cancel mid-flight leaves no half-writes; filenames sanitized |
| `merge_pdfs` | Produces N-page PDF from N inputs |
| `save_preset` / `load_preset` | Roundtrip equals input; invalid schema rejected; atomic write |
| `safe_filename` | Forbidden chars removed; empty becomes "unnamed" |

---

## 18. What's Deliberately NOT in the API

To make the absence explicit:

- ❌ No `IQGISBridge` Protocol. Direct PyQGIS imports.
- ❌ No `LayoutEngine`/`SceneBuilder`/`Composer`/`ConstraintSolver` chain. One function + two strategy functions.
- ❌ No `IAIProvider` / AI subsystem.
- ❌ No `Exporter` ABC. One `run_atlas` function.
- ❌ No `EventBus`. Qt signals where useful; direct calls otherwise.
- ❌ No `Container` / DI. Plain object construction.
- ❌ No `Command`/`Result`/`UseCase` triplets. Direct function calls with kwargs.
- ❌ No `CompositionRegistry`/`TokenRegistry`/`PanelRegistry`. No public API at all.
- ❌ No `CancellationToken` class. `threading.Event` works fine.
- ❌ No `@public`/`@beta`/`@internal` stability decorators. Everything is internal.

---

## 19. Forward Compatibility (Cheap)

To make future expansion cheap *without* designing for it now:

1. Functions take **keyword-only arguments** for non-essential params. Adds without breaking signatures.
2. JSON files carry `"schema": 1` so we can write a `migrate(data)` function later if needed.
3. `metadata.txt` `version=` follows SemVer strictly.
4. Internal types are `TypedDict`s (or plain `dict`) — easy to add optional keys.

That's all the future-proofing we need.

---

## 20. Bottom Line

| Original Plan | Rewrite |
|---------------|---------|
| ~40 public functions across ports/adapters/services | ~15 internal functions |
| Pydantic-style dataclass forests | Plain `dict` + `TypedDict` |
| 6 extension registries | 0 |
| Cancellation token class | `threading.Event` |
| Provider abstractions | None |
| Stability tiers | All internal |

The whole API fits on one screen. That's the goal.

---

*End of api-design.md (lean rewrite).*
