"""core/layout — komposisi layout. Day 6: minimal (map + title).

Memakai temuan Spike S0.1: `setFont(QFont)` (bukan setFontSize) dan
`QgsUnitTypes.LayoutMillimeters` (valid di QGIS 3.34).
"""

from __future__ import annotations

from qgis.core import (
    QgsLayoutItemLabel,
    QgsLayoutItemMap,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsPrintLayout,
    QgsProject,
    QgsRectangle,
    QgsUnitTypes,
)
from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtGui import QFont

from ..errors import SLBError, ValidationError

PAPER_MM = {
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
    "Letter": (215.9, 279.4),
}
_MARGIN_MM = 10.0
_TITLE_H_MM = 12.0


def _paper_size_mm(paper: str, orientation: str) -> tuple[float, float]:
    if paper not in PAPER_MM:
        raise ValidationError(
            f"Ukuran kertas tidak didukung: {paper}",
            hint="Gunakan A4, A3, atau Letter.",
        )
    if orientation not in ("portrait", "landscape"):
        raise ValidationError(
            f"Orientasi tidak valid: {orientation}",
            hint="Gunakan 'portrait' atau 'landscape'.",
        )
    w, h = PAPER_MM[paper]
    if orientation == "landscape":
        return (max(w, h), min(w, h))
    return (min(w, h), max(w, h))


def _unique_layout_name(manager, base: str) -> str:
    """Hindari tabrakan nama: QgsLayoutManager.addLayout() GAGAL + menghapus objek
    C++ bila nama duplikat. Tambah sufiks ' (n)' sampai unik."""
    existing = {layout.name() for layout in manager.layouts()}
    if base not in existing:
        return base
    i = 2
    while f"{base} ({i})" in existing:
        i += 1
    return f"{base} ({i})"


def _resolve_extent(project: QgsProject, extent: QgsRectangle | None) -> QgsRectangle:
    if extent is not None and not extent.isEmpty():
        return extent
    rect = QgsRectangle()
    rect.setMinimal()
    for layer in project.mapLayers().values():
        try:
            rect.combineExtentWith(layer.extent())
        except Exception:  # noqa: BLE001 - layer tanpa extent valid
            continue
    if rect.isEmpty():
        raise ValidationError(
            "Tidak ada area peta yang bisa dipakai.",
            hint="Buka project dengan minimal satu layer, atau zoom ke suatu area.",
        )
    return rect


def generate_layout(
    project: QgsProject,
    *,
    paper: str = "A4",
    orientation: str = "portrait",
    title: str | None = None,
    extent: QgsRectangle | None = None,
    layout_name: str | None = None,
) -> QgsPrintLayout:
    """Buat QgsPrintLayout minimal (map + title) dan tambahkan ke project.

    `extent` opsional: bila None, dipakai gabungan extent semua layer.
    Mengembalikan layout yang sudah ada di project.layoutManager().
    """
    page_w, page_h = _paper_size_mm(paper, orientation)
    map_extent = _resolve_extent(project, extent)
    title_text = title if title is not None else (project.title() or "Untitled")
    mm = QgsUnitTypes.LayoutMillimeters

    manager = project.layoutManager()
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(_unique_layout_name(manager, layout_name or f"SLB {title_text}"))
    layout.pageCollection().page(0).setPageSize(QgsLayoutSize(page_w, page_h, mm))

    # Title
    label = QgsLayoutItemLabel(layout)
    label.setText(title_text)
    font = label.font()
    font.setPointSize(18)
    font.setBold(True)
    label.setFont(font)
    layout.addLayoutItem(label)
    label.attemptMove(QgsLayoutPoint(_MARGIN_MM, _MARGIN_MM, mm))
    label.attemptResize(QgsLayoutSize(page_w - 2 * _MARGIN_MM, _TITLE_H_MM, mm))

    # Map (mengisi sisa halaman)
    map_top = _MARGIN_MM + _TITLE_H_MM + 4.0
    map_w = page_w - 2 * _MARGIN_MM
    map_h = page_h - map_top - _MARGIN_MM
    map_item = QgsLayoutItemMap(layout)
    map_item.setRect(QRectF(0, 0, map_w, map_h))
    map_item.setExtent(map_extent)
    map_item.setFrameEnabled(True)
    layout.addLayoutItem(map_item)
    map_item.attemptMove(QgsLayoutPoint(_MARGIN_MM, map_top, mm))
    map_item.attemptResize(QgsLayoutSize(map_w, map_h, mm))

    if not manager.addLayout(layout):
        # Objek C++ sudah dihapus oleh manager saat gagal -> jangan diakses lagi.
        raise SLBError(
            "Gagal menambahkan layout ke project.",
            hint="Coba lagi; bila berulang, tutup beberapa layout yang ada.",
        )
    return layout
