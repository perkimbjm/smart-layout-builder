"""Spike S0.1 — Layout API feasibility.

Tujuan: buktikan kita bisa membangun QgsPrintLayout lengkap
(map + title + legend + scale bar + north arrow + attribution)
secara programmatic dalam < 200 LOC inti, memakai API PyQGIS yang stabil
di QGIS LTR.

Cara pakai (pilih salah satu):

1) QGIS Python Console (cara utama):
     - Buka sebuah project QGIS yang punya >= 1 layer.
     - Panel: Plugins > Python Console.
     - Jalankan:
           exec(open(r"<path>/spikes/spike_layout.py").read())
     - Layout akan dibuat dan dibuka di Layout Designer.

2) Lewat MCP qgis (mcp__qgis__execute_code):
     - Pastikan QGIS + plugin MCP berjalan.
     - Kirim isi fungsi build_layout(...) + pemanggilan run().

Hasil yang dicatat (untuk docs/spikes.md):
    - LOC inti fungsi build_layout()
    - Daftar kelas/method PyQGIS yang dipakai (referensi core/layout.py nanti)
    - Waktu eksekusi (perf_counter)
    - Kendala yang ditemui
    - Keputusan GO / NO-GO
"""

from __future__ import annotations

import time

from qgis.core import (
    QgsProject,
    QgsPrintLayout,
    QgsLayoutItemMap,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemScaleBar,
    QgsLayoutItemPicture,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsLayoutItemPage,
    QgsUnitTypes,
    QgsRectangle,
)
from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtGui import QFont


def _set_font(item, point_size: int) -> None:
    """Set ukuran font label lintas-versi (QGIS 3.34: pakai setFont(QFont))."""
    f = item.font()
    f.setPointSize(point_size)
    item.setFont(f)


# --- konfigurasi kertas (mm) ----------------------------------------------
PAPER_MM = {
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
    "Letter": (215.9, 279.4),
}


def _paper_size_mm(paper: str, orientation: str) -> tuple[float, float]:
    w, h = PAPER_MM[paper]
    if orientation == "landscape":
        return (max(w, h), min(w, h))
    return (min(w, h), max(w, h))


# === INTI YANG DIUKUR LOC-nya =============================================
def build_layout(
    project: QgsProject,
    extent: QgsRectangle,
    *,
    paper: str = "A4",
    orientation: str = "landscape",
    title: str = "Spike Layout",
    margin: float = 10.0,
) -> QgsPrintLayout:
    """Bangun layout lengkap. Return QgsPrintLayout yang sudah ditambahkan
    ke layoutManager. Inti yang kita ukur kompleksitasnya."""
    pw, ph = _paper_size_mm(paper, orientation)

    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(f"SLB Spike {title}")

    page = layout.pageCollection().page(0)
    page.setPageSize(QgsLayoutSize(pw, ph, QgsUnitTypes.LayoutMillimeters))

    mm = QgsUnitTypes.LayoutMillimeters

    # Title (atas, full width)
    title_h = 12.0
    lbl = QgsLayoutItemLabel(layout)
    lbl.setText(title)
    _set_font(lbl, 18)
    layout.addLayoutItem(lbl)
    lbl.attemptMove(QgsLayoutPoint(margin, margin, mm))
    lbl.attemptResize(QgsLayoutSize(pw - 2 * margin, title_h, mm))

    # Map (kiri ~2/3 untuk landscape; full width sisanya untuk portrait)
    map_top = margin + title_h + 4
    if orientation == "landscape":
        map_w = (pw - 2 * margin) * 0.66
    else:
        map_w = pw - 2 * margin
    map_h = ph - map_top - margin - 8  # sisakan footer
    m = QgsLayoutItemMap(layout)
    m.setRect(QRectF(0, 0, map_w, map_h))
    m.setExtent(extent)
    m.setFrameEnabled(True)
    layout.addLayoutItem(m)
    m.attemptMove(QgsLayoutPoint(margin, map_top, mm))
    m.attemptResize(QgsLayoutSize(map_w, map_h, mm))

    # Sidebar X-position (kanan map untuk landscape)
    sidebar_x = margin + map_w + 4
    sidebar_w = pw - sidebar_x - margin

    # Legend
    legend = QgsLayoutItemLegend(layout)
    legend.setTitle("Legend")
    legend.setLinkedMap(m)
    layout.addLayoutItem(legend)
    if orientation == "landscape":
        legend.attemptMove(QgsLayoutPoint(sidebar_x, map_top, mm))
        legend.attemptResize(QgsLayoutSize(sidebar_w, map_h * 0.6, mm))
    else:
        legend.attemptMove(QgsLayoutPoint(margin, map_top + map_h + 2, mm))

    # Scale bar
    bar = QgsLayoutItemScaleBar(layout)
    bar.setStyle("Single Box")
    bar.setLinkedMap(m)
    bar.applyDefaultSize()
    layout.addLayoutItem(bar)
    if orientation == "landscape":
        bar.attemptMove(QgsLayoutPoint(sidebar_x, map_top + map_h * 0.62, mm))
    else:
        bar.attemptMove(QgsLayoutPoint(margin + 60, map_top + map_h + 2, mm))

    # North arrow (pakai SVG default QGIS bila ada; fallback label "N")
    try:
        arrow = QgsLayoutItemPicture(layout)
        arrow.setPicturePath(
            "/usr/share/qgis/svg/arrows/NorthArrow_02.svg"
        )  # path bisa beda per OS; cek di GO/NO-GO
        layout.addLayoutItem(arrow)
        arrow.attemptResize(QgsLayoutSize(18, 18, mm))
        if orientation == "landscape":
            arrow.attemptMove(QgsLayoutPoint(sidebar_x, map_top + map_h * 0.72, mm))
        else:
            arrow.attemptMove(QgsLayoutPoint(pw - margin - 18, map_top + map_h + 2, mm))
    except Exception:  # noqa: BLE001 (spike only)
        arrow = QgsLayoutItemLabel(layout)
        arrow.setText("N ↑")
        _set_font(arrow, 14)
        layout.addLayoutItem(arrow)

    # Attribution (bawah)
    attr = QgsLayoutItemLabel(layout)
    attr.setText("Dibuat dengan Smart Layout Builder (spike)")
    _set_font(attr, 7)
    layout.addLayoutItem(attr)
    attr.attemptMove(QgsLayoutPoint(margin, ph - margin - 5, mm))
    attr.attemptResize(QgsLayoutSize(pw - 2 * margin, 5, mm))

    project.layoutManager().addLayout(layout)
    return layout
# === AKHIR INTI ============================================================


def _current_extent(project: QgsProject) -> QgsRectangle:
    """Ambil extent dari canvas (bila ada iface) atau gabungan layer."""
    try:
        from qgis.utils import iface  # type: ignore

        if iface is not None and iface.mapCanvas() is not None:
            return iface.mapCanvas().extent()
    except Exception:  # noqa: BLE001
        pass

    rect = QgsRectangle()
    rect.setMinimal()
    for lyr in project.mapLayers().values():
        try:
            rect.combineExtentWith(lyr.extent())
        except Exception:  # noqa: BLE001
            continue
    return rect


def run(paper: str = "A4", orientation: str = "landscape") -> dict:
    """Entry point spike. Return ringkasan untuk dicatat di spikes.md."""
    project = QgsProject.instance()
    n_layers = len(project.mapLayers())
    extent = _current_extent(project)

    t0 = time.perf_counter()
    layout = build_layout(
        project,
        extent,
        paper=paper,
        orientation=orientation,
        title=project.title() or "Untitled",
    )
    elapsed = time.perf_counter() - t0

    item_roles = [type(i).__name__ for i in layout.items() if hasattr(i, "displayName")]

    # Buka di Designer bila GUI tersedia
    try:
        from qgis.utils import iface  # type: ignore

        if iface is not None:
            iface.openLayoutDesigner(layout)
    except Exception:  # noqa: BLE001
        pass

    summary = {
        "ok": True,
        "layers_in_project": n_layers,
        "build_seconds": round(elapsed, 4),
        "item_count": len(layout.items()),
        "item_types": sorted(set(item_roles)),
        "layout_name": layout.name(),
    }
    print("SPIKE S0.1 RESULT:", summary)
    return summary


if __name__ == "__main__":
    run()
