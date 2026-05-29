"""core/layout — komposisi layout.

Day 6: minimal (map + title). Day 7: 6 elemen. Day 9: penempatan item
didelegasikan ke ``core/strategies`` (single_column / two_column); modul ini
hanya memilih strategi berdasarkan orientasi lalu me-materialize ItemSpec
menjadi item QGIS.

Memakai temuan Spike S0.1: ``setFont(QFont)`` (bukan setFontSize) dan
``QgsUnitTypes.LayoutMillimeters`` (valid di QGIS 3.34).
"""

from __future__ import annotations

import logging
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
from . import strategies
from .legend import prune_legend
from .strategies import ItemSpec

log = logging.getLogger("slb.core.layout")

PAPER_MM = {
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
    "Letter": (215.9, 279.4),
}

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


def _select_strategy(orientation: str):
    """Pilih strategi komposisi berdasarkan orientasi (architecture.md §10)."""
    if orientation == "landscape":
        return strategies.two_column
    return strategies.single_column


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


def _place(item, spec: ItemSpec, mm) -> None:
    item.attemptMove(QgsLayoutPoint(spec["x_mm"], spec["y_mm"], mm))
    item.attemptResize(QgsLayoutSize(spec["w_mm"], spec["h_mm"], mm))


def _add_title(layout, spec: ItemSpec, title_text: str, mm):
    label = QgsLayoutItemLabel(layout)
    label.setText(title_text)
    font = label.font()
    font.setPointSize(18)
    font.setBold(True)
    label.setFont(font)
    layout.addLayoutItem(label)
    _place(label, spec, mm)
    return label


def _add_map(layout, spec: ItemSpec, extent: QgsRectangle, mm):
    map_item = QgsLayoutItemMap(layout)
    map_item.setRect(QRectF(0, 0, spec["w_mm"], spec["h_mm"]))
    map_item.setExtent(extent)
    map_item.setFrameEnabled(True)
    layout.addLayoutItem(map_item)
    _place(map_item, spec, mm)
    return map_item


def _add_legend(layout, spec: ItemSpec, map_item, mm):
    legend = QgsLayoutItemLegend(layout)
    legend.setTitle("Legend")
    if map_item is not None:
        legend.setLinkedMap(map_item)
    layout.addLayoutItem(legend)
    _place(legend, spec, mm)
    return legend


def _add_scale_bar(layout, spec: ItemSpec, map_item, mm):
    scale = QgsLayoutItemScaleBar(layout)
    scale.setStyle("Single Box")
    if map_item is not None:
        scale.setLinkedMap(map_item)
    scale.applyDefaultSize()  # scale bar menentukan ukurannya sendiri
    layout.addLayoutItem(scale)
    scale.attemptMove(QgsLayoutPoint(spec["x_mm"], spec["y_mm"], mm))
    return scale


def _add_north_arrow(layout, spec: ItemSpec, mm, arrow_file=_DEFAULT_NORTH_ARROW):
    """North arrow dari SVG bundled. Cek os.path.exists dulu (temuan S0.1:
    path SVG sistem tidak ada di Windows). Fallback ke label 'N' bila SVG hilang."""
    svg_path = os.path.join(_NORTH_ARROWS_DIR, arrow_file)
    if os.path.exists(svg_path):
        pic = QgsLayoutItemPicture(layout)
        pic.setPicturePath(svg_path)
        layout.addLayoutItem(pic)
        _place(pic, spec, mm)
        return pic
    label = QgsLayoutItemLabel(layout)
    label.setText("N ↑")
    font = label.font()
    font.setPointSize(14)
    font.setBold(True)
    label.setFont(font)
    layout.addLayoutItem(label)
    _place(label, spec, mm)
    return label


def _add_attribution(layout, spec: ItemSpec, mm):
    attribution = QgsLayoutItemLabel(layout)
    attribution.setText("Dibuat dengan Smart Layout Builder")
    font = attribution.font()
    font.setPointSize(7)
    attribution.setFont(font)
    layout.addLayoutItem(attribution)
    _place(attribution, spec, mm)
    return attribution


def _materialize(
    layout, specs: list[ItemSpec], *, map_extent: QgsRectangle, title_text: str, mm
) -> None:
    """Ubah ItemSpec dari strategi menjadi item QGIS.

    Peta dibuat lebih dulu karena legend & scale bar harus ter-link padanya.
    """
    map_item = None
    for spec in specs:
        if spec.get("role") == "map":
            map_item = _add_map(layout, spec, map_extent, mm)
            break

    for spec in specs:
        role = spec.get("role")
        if role == "map":
            continue
        elif role == "title":
            _add_title(layout, spec, title_text, mm)
        elif role == "legend":
            _add_legend(layout, spec, map_item, mm)
        elif role == "scale_bar":
            _add_scale_bar(layout, spec, map_item, mm)
        elif role == "north_arrow":
            _add_north_arrow(layout, spec, mm)
        elif role == "attribution":
            _add_attribution(layout, spec, mm)
        else:
            log.warning("peran ItemSpec tidak dikenal, dilewati: %s", role)


def generate_layout(
    project: QgsProject,
    *,
    paper: str = "A4",
    orientation: str = "portrait",
    title: str | None = None,
    extent: QgsRectangle | None = None,
    layout_name: str | None = None,
    prune_legend_mode: str = "safe",
) -> QgsPrintLayout:
    """Buat QgsPrintLayout dan tambahkan ke project.

    Strategi penempatan dipilih dari ``orientation`` (portrait → single_column,
    landscape → two_column). `extent` opsional: bila None, dipakai gabungan
    extent semua layer. ``prune_legend_mode`` (``safe``/``extent``/``off``)
    membersihkan entri legend setelah materialize (lihat ``core/legend``).
    Mengembalikan layout yang sudah ada di layoutManager().
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

    strategy = _select_strategy(orientation)
    specs = strategy(page_w, page_h)
    _materialize(layout, specs, map_extent=map_extent, title_text=title_text, mm=mm)

    # Bersihkan legend (mengikuti api-design §3 langkah 4); tak mengubah project.
    prune_legend(layout, project, mode=prune_legend_mode)

    if not manager.addLayout(layout):
        # Objek C++ sudah dihapus oleh manager saat gagal -> jangan diakses lagi.
        raise SLBError(
            "Gagal menambahkan layout ke project.",
            hint="Coba lagi; bila berulang, tutup beberapa layout yang ada.",
        )
    return layout
