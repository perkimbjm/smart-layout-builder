"""core/legend — Smart Legend Cleaner (Day 11).

``prune_legend()`` membuang entri legend untuk layer yang tak relevan TANPA
mengubah project. Modul ini hanya menyunting salinan layer-tree milik legend:
selama ``autoUpdateModel`` masih aktif, model legend *berbagi* pohon dengan
project — jadi kita matikan dulu (QGIS lalu meng-clone pohon itu) sebelum
menghapus node, sehingga ``project.layerTreeRoot()`` tak pernah tersentuh.

Mode (api-design.md §4 / architecture.md §9):
  - ``"off"``  : no-op (mengembalikan 0).
  - ``"safe"`` : buang layer yang dikecualikan-dari-legend (flag Private) atau
                 tak-tercentang di layer tree (efektif tak ter-render).
  - ``"extent"``: tambahan buang layer 0 fitur di extent — menyusul Day 12.

Idempoten: pemanggilan kedua tak menemukan node yang cocok → mengembalikan 0,
dan tidak meng-clone ulang (manual edit user terjaga).
"""

from __future__ import annotations

import logging

from qgis.core import QgsLayoutItemLegend, QgsMapLayer, QgsPrintLayout, QgsProject

from ..errors import ValidationError

log = logging.getLogger("slb.core.legend")

# Flag QGIS untuk layer "privat" (disembunyikan dari layer tree & legend).
# getattr: aman bila enum diakses beda antar versi 3.x.
_PRIVATE_FLAG = getattr(QgsMapLayer, "Private", None)


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


def _prune_one(legend: QgsLayoutItemLegend) -> int:
    # Saat auto-update aktif, model legend = pohon project (shared). Matikan agar
    # QGIS meng-clone pohon; sejak itu hanya clone milik legend yang kita sunting.
    if legend.autoUpdateModel():
        legend.setAutoUpdateModel(False)

    root = legend.model().rootGroup()
    doomed = [node for node in root.findLayers() if _should_drop_safe(node)]
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
    if mode != "safe":
        raise ValidationError(
            f"Mode legend tidak didukung: {mode!r}",
            hint="Saat ini tersedia 'safe' atau 'off'.",
        )

    legends = [item for item in layout.items() if isinstance(item, QgsLayoutItemLegend)]
    if not legends:
        log.info("prune_legend: tidak ada item legend di layout.")
        return 0

    pruned = sum(_prune_one(legend) for legend in legends)
    log.info("prune_legend(mode=%s): %d entri dibuang.", mode, pruned)
    return pruned
