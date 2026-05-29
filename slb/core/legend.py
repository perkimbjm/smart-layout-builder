"""core/legend — Smart Legend Cleaner (Day 11–12).

``prune_legend()`` membuang entri legend untuk layer yang tak relevan TANPA
mengubah project. Modul ini hanya menyunting salinan layer-tree milik legend:
selama ``autoUpdateModel`` masih aktif, model legend *berbagi* pohon dengan
project — jadi kita matikan dulu (QGIS lalu meng-clone pohon itu) sebelum
menghapus node, sehingga ``project.layerTreeRoot()`` tak pernah tersentuh.

Mode (api-design.md §4 / architecture.md §9):
  - ``"off"``  : no-op (mengembalikan 0).
  - ``"safe"`` : buang layer yang dikecualikan-dari-legend (flag Private) atau
                 tak-tercentang di layer tree (efektif tak ter-render).
  - ``"extent"``: ``safe`` + buang layer vektor 0 fitur di extent peta.

Desain ``extent`` mengikuti Spike S0.2 (``docs/spikes.md``): bukan "timeout per
layer" (biaya ada di dalam panggilan provider C++ yang tak bisa diinterupsi dari
Python), melainkan kombinasi murah & implementable —
  1. **bbox pre-filter**: transform ``layer.extent()`` ke CRS map; bila tak
     beririsan dengan extent map → pasti 0 fitur → buang tanpa scan;
  2. **cek ada-fitur** via iterator + ``break`` (request ``NoGeometry`` + subset
     atribut kosong), bukan ``featureCount``;
  3. **budget kumulatif lintas-layer + fail-open**: bila total waktu uji melewati
     anggaran → hentikan scan, **simpan** sisa layer (fail-open);
  4. **skip non-vektor** (raster dst.): anggap in-extent (jangan hitung piksel).

Idempoten: pemanggilan kedua tak menemukan node yang cocok → mengembalikan 0,
dan tidak meng-clone ulang (manual edit user terjaga).
"""

from __future__ import annotations

import logging
import time

from qgis.core import (
    QgsCoordinateTransform,
    QgsFeatureRequest,
    QgsLayoutItemLegend,
    QgsMapLayer,
    QgsPrintLayout,
    QgsProject,
    QgsVectorLayer,
)

from ..errors import ValidationError

log = logging.getLogger("slb.core.legend")

# Flag QGIS untuk layer "privat" (disembunyikan dari layer tree & legend).
# getattr: aman bila enum diakses beda antar versi 3.x.
_PRIVATE_FLAG = getattr(QgsMapLayer, "Private", None)

# Anggaran waktu kumulatif (detik) untuk scan fitur mode ``extent`` dalam satu
# pemanggilan ``prune_legend``. Lewat anggaran → fail-open (simpan sisa layer).
_EXTENT_BUDGET_S = 2.0


def _is_legend_excluded(layer) -> bool:
    """Layer ditandai 'sembunyikan dari legend' → flag Private QGIS."""
    if layer is None or _PRIVATE_FLAG is None:
        return False
    try:
        return bool(layer.flags() & _PRIVATE_FLAG)
    except Exception:
        return False


def _is_hidden(node) -> bool:
    """Node layer efektif tak-terlihat: dirinya atau salah satu grup induk
    tak-tercentang. (``itemVisibilityCheckedRecursive`` absen di QGIS 3.34,
    jadi telusuri ke atas pakai ``itemVisibilityChecked``.)"""
    current = node
    while current is not None:
        checked = getattr(current, "itemVisibilityChecked", current.isVisible)
        if not checked():
            return True
        current = current.parent()
    return False


def _should_drop_safe(node) -> bool:
    return _is_hidden(node) or _is_legend_excluded(node.layer())


def _has_feature_in_extent(layer, map_extent, map_crs, transform_ctx) -> bool:
    """True bila ``layer`` punya ≥ 1 fitur di ``map_extent`` (CRS = ``map_crs``).

    Non-vektor (raster dst.) dianggap selalu in-extent (S0.2: jangan hitung
    piksel). Jalankan bbox pre-filter dulu; lalu cek ada-fitur via iterator +
    ``break``. Kegagalan transform → fail-open (kembalikan True, simpan layer).
    """
    if not isinstance(layer, QgsVectorLayer):
        return True

    layer_crs = layer.crs()
    same_crs = layer_crs == map_crs

    # 1) bbox pre-filter di ruang CRS map: bila extent layer tak beririsan dengan
    #    extent map → pasti 0 fitur → buang tanpa scan provider.
    try:
        if same_crs:
            layer_bbox_in_map = layer.extent()
        else:
            to_map = QgsCoordinateTransform(layer_crs, map_crs, transform_ctx)
            layer_bbox_in_map = to_map.transformBoundingBox(layer.extent())
        if not layer_bbox_in_map.intersects(map_extent):
            return False
    except Exception:  # noqa: BLE001 - transform pre-filter gagal → lanjut ke scan
        pass

    # 2) extent map → CRS layer untuk setFilterRect (tak bisa transform → fail-open).
    try:
        if same_crs:
            rect = map_extent
        else:
            from_map = QgsCoordinateTransform(map_crs, layer_crs, transform_ctx)
            rect = from_map.transformBoundingBox(map_extent)
    except Exception:  # noqa: BLE001
        return True

    req = (
        QgsFeatureRequest()
        .setFilterRect(rect)
        .setFlags(QgsFeatureRequest.NoGeometry)
        .setSubsetOfAttributes([])
    )
    for _feat in layer.getFeatures(req):
        return True
    return False


def _prune_one(legend: QgsLayoutItemLegend, mode, transform_ctx, deadline) -> int:
    # Saat auto-update aktif, model legend = pohon project (shared). Matikan agar
    # QGIS meng-clone pohon; sejak itu hanya clone milik legend yang kita sunting.
    if legend.autoUpdateModel():
        legend.setAutoUpdateModel(False)

    # Sumber extent untuk mode `extent` = peta yang ter-link ke legend ini.
    map_extent = None
    map_crs = None
    if mode == "extent":
        linked = legend.linkedMap()
        if linked is not None:
            ext = linked.extent()
            if ext is not None and not ext.isEmpty():
                map_extent = ext
                map_crs = linked.crs()

    root = legend.model().rootGroup()
    doomed = []
    over_budget = False
    for node in root.findLayers():
        if _should_drop_safe(node):
            doomed.append(node)
            continue
        # `map_extent is None` mencakup mode non-extent & extent tanpa peta ter-link.
        if map_extent is None:
            continue
        layer = node.layer()
        if layer is None:
            continue
        # Budget kumulatif: lewat anggaran → berhenti scan, simpan sisa (fail-open).
        # Tetap pakai `continue` (bukan break) agar safe-check node lain tetap jalan.
        if deadline is not None and time.perf_counter() > deadline:
            if not over_budget:
                log.info(
                    "prune_legend(extent): budget waktu terlampaui; "
                    "sisa layer di-keep (fail-open)."
                )
                over_budget = True
            continue
        try:
            present = _has_feature_in_extent(layer, map_extent, map_crs, transform_ctx)
        except Exception:  # noqa: BLE001 - scan gagal → simpan layer (fail-open)
            present = True
        if not present:
            doomed.append(node)

    for node in doomed:
        parent = node.parent()
        if parent is not None:
            parent.removeChildNode(node)

    if doomed:
        legend.adjustBoxSize()
        legend.invalidateCache()
    return len(doomed)


def prune_legend(
    layout: QgsPrintLayout,
    project: QgsProject,
    mode: str = "safe",
) -> int:
    """Buang entri legend tak relevan dari semua legend di ``layout``.

    Mengembalikan jumlah entri layer yang dibuang. Tidak pernah mengubah
    ``project``. Lihat docstring modul untuk perilaku tiap mode.
    """
    if mode == "off":
        return 0
    if mode not in ("safe", "extent"):
        raise ValidationError(
            f"Mode legend tidak didukung: {mode!r}",
            hint="Saat ini tersedia 'safe', 'extent', atau 'off'.",
        )

    legends = [item for item in layout.items() if isinstance(item, QgsLayoutItemLegend)]
    if not legends:
        log.info("prune_legend: tidak ada item legend di layout.")
        return 0

    # Konteks transform & deadline kumulatif hanya relevan untuk mode `extent`.
    transform_ctx = project.transformContext() if mode == "extent" else None
    deadline = (time.perf_counter() + _EXTENT_BUDGET_S) if mode == "extent" else None

    pruned = sum(
        _prune_one(legend, mode, transform_ctx, deadline) for legend in legends
    )
    log.info("prune_legend(mode=%s): %d entri dibuang.", mode, pruned)
    return pruned
