"""core/layout — komposisi layout. Day 6: minimal (map + title).

Memakai temuan Spike S0.1: `setFont(QFont)` (bukan setFontSize) dan
`QgsUnitTypes.LayoutMillimeters` (valid di QGIS 3.34).
"""

from __future__ import annotations

import os

from qgis.core import (
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemMap,
    QgsLayoutItemPicture,
    QgsLayoutItemScaleBar,
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
_FOOTER_H_MM = 42.0          # zona legend/scale/north
_ATTRIB_H_MM = 5.0
_NORTH_SIZE_MM = 20.0
_NORTH_ARROWS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "resources", "north_arrows")
)
_DEFAULT_NORTH_ARROW = "na_classic.svg"


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


def _add_north_arrow(layout, x_mm, y_mm, size_mm, mm, arrow_file=_DEFAULT_NORTH_ARROW):
    """Tambah north arrow dari SVG bundled. Cek os.path.exists dulu (temuan S0.1:
    path SVG sistem tidak ada di Windows). Fallback ke label 'N' bila SVG hilang."""
    svg_path = os.path.join(_NORTH_ARROWS_DIR, arrow_file)
    if os.path.exists(svg_path):
        pic = QgsLayoutItemPicture(layout)
        pic.setPicturePath(svg_path)
        layout.addLayoutItem(pic)
        pic.attemptMove(QgsLayoutPoint(x_mm, y_mm, mm))
        pic.attemptResize(QgsLayoutSize(size_mm, size_mm, mm))
        return pic
    label = QgsLayoutItemLabel(layout)
    label.setText("N ↑")
    font = label.font()
    font.setPointSize(14)
    font.setBold(True)
    label.setFont(font)
    layout.addLayoutItem(label)
    label.attemptMove(QgsLayoutPoint(x_mm, y_mm, mm))
    label.attemptResize(QgsLayoutSize(size_mm, size_mm, mm))
    return label


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

    # Map (menyisakan zona footer untuk legend/scale/north + attribution)
    map_top = _MARGIN_MM + _TITLE_H_MM + 4.0
    map_w = page_w - 2 * _MARGIN_MM
    footer_top = page_h - _MARGIN_MM - _ATTRIB_H_MM - _FOOTER_H_MM
    map_h = footer_top - map_top - 2.0
    map_item = QgsLayoutItemMap(layout)
    map_item.setRect(QRectF(0, 0, map_w, map_h))
    map_item.setExtent(map_extent)
    map_item.setFrameEnabled(True)
    layout.addLayoutItem(map_item)
    map_item.attemptMove(QgsLayoutPoint(_MARGIN_MM, map_top, mm))
    map_item.attemptResize(QgsLayoutSize(map_w, map_h, mm))

    # Legend (kiri footer), ter-link ke map
    legend = QgsLayoutItemLegend(layout)
    legend.setTitle("Legend")
    legend.setLinkedMap(map_item)
    layout.addLayoutItem(legend)
    legend.attemptMove(QgsLayoutPoint(_MARGIN_MM, footer_top, mm))
    legend.attemptResize(QgsLayoutSize(page_w * 0.42, _FOOTER_H_MM, mm))

    # Scale bar (tengah footer), ter-link ke map
    scale = QgsLayoutItemScaleBar(layout)
    scale.setStyle("Single Box")
    scale.setLinkedMap(map_item)
    scale.applyDefaultSize()
    layout.addLayoutItem(scale)
    scale.attemptMove(QgsLayoutPoint(page_w * 0.5, footer_top + 6.0, mm))

    # North arrow (kanan footer) — SVG bundled + fallback
    _add_north_arrow(
        layout,
        page_w - _MARGIN_MM - _NORTH_SIZE_MM,
        footer_top + 4.0,
        _NORTH_SIZE_MM,
        mm,
    )

    # Attribution (strip paling bawah)
    attribution = QgsLayoutItemLabel(layout)
    attribution.setText("Dibuat dengan Smart Layout Builder")
    attr_font = attribution.font()
    attr_font.setPointSize(7)
    attribution.setFont(attr_font)
    layout.addLayoutItem(attribution)
    attribution.attemptMove(QgsLayoutPoint(_MARGIN_MM, page_h - _MARGIN_MM - _ATTRIB_H_MM, mm))
    attribution.attemptResize(QgsLayoutSize(map_w, _ATTRIB_H_MM, mm))

    if not manager.addLayout(layout):
        # Objek C++ sudah dihapus oleh manager saat gagal -> jangan diakses lagi.
        raise SLBError(
            "Gagal menambahkan layout ke project.",
            hint="Coba lagi; bila berulang, tutup beberapa layout yang ada.",
        )
    return layout
