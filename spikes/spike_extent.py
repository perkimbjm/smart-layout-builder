"""Spike S0.2 — Feature-in-extent performance.

Tujuan: ukur apakah cek "apakah layer punya >= 1 fitur di extent saat ini"
cukup cepat (< 50 ms/layer) untuk dipakai di Smart Legend Cleaner mode `extent`.

Kunci desain produksi yang divalidasi di sini:
- Untuk pruning legend kita TIDAK butuh count penuh; cukup tahu ada >= 1 fitur.
  → pakai iterator + ambil 1 fitur + break (jauh lebih murah dari featureCount).
- Extent canvas ada di CRS project; tiap layer bisa beda CRS → harus transform
  extent ke CRS layer sebelum setFilterRect. Ini juga concern di slb/core/legend.py.
- Request dioptimalkan: NoGeometry + subset atribut kosong.
- Raster: skip (treat "intersect bbox" = in-extent).

Cara pakai:
    exec(open(r"<path>/spikes/spike_extent.py").read())
atau via MCP execute_code: exec isi file lalu panggil run().
"""

from __future__ import annotations

import time

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsFeatureRequest,
    QgsRectangle,
    QgsCoordinateTransform,
)


THRESHOLD_MS = 50.0


def _canvas_extent_and_crs(project):
    """Return (extent, crs) dari canvas bila ada iface, else gabungan layer."""
    try:
        from qgis.utils import iface  # type: ignore

        if iface is not None and iface.mapCanvas() is not None:
            c = iface.mapCanvas()
            return c.extent(), c.mapSettings().destinationCrs()
    except Exception:  # noqa: BLE001
        pass
    # fallback: gabungan extent semua layer dalam CRS project
    ext = QgsRectangle()
    ext.setMinimal()
    for lyr in project.mapLayers().values():
        try:
            ext.combineExtentWith(lyr.extent())
        except Exception:  # noqa: BLE001
            continue
    return ext, project.crs()


def has_feature_in_extent(layer: QgsVectorLayer, extent_proj: QgsRectangle,
                          proj_crs, transform_ctx) -> tuple[bool, float]:
    """Kembalikan (ada_fitur, elapsed_ms). Hanya butuh 1 fitur → break cepat."""
    t0 = time.perf_counter()

    # transform extent project -> CRS layer
    if layer.crs() != proj_crs:
        xform = QgsCoordinateTransform(proj_crs, layer.crs(), transform_ctx)
        rect = xform.transformBoundingBox(extent_proj)
    else:
        rect = extent_proj

    req = (
        QgsFeatureRequest()
        .setFilterRect(rect)
        .setFlags(QgsFeatureRequest.NoGeometry)
        .setSubsetOfAttributes([])
    )
    found = False
    for _f in layer.getFeatures(req):
        found = True
        break

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return found, elapsed_ms


def run() -> dict:
    project = QgsProject.instance()
    extent_proj, proj_crs = _canvas_extent_and_crs(project)
    ctx = project.transformContext()

    rows = []
    over_threshold = []
    for lyr in project.mapLayers().values():
        if isinstance(lyr, QgsRasterLayer):
            rows.append({
                "name": lyr.name(), "type": "raster",
                "in_extent": "skip (bbox intersect)", "ms": 0.0,
            })
            continue
        if not isinstance(lyr, QgsVectorLayer):
            rows.append({"name": lyr.name(), "type": "other", "in_extent": "?", "ms": 0.0})
            continue
        try:
            found, ms = has_feature_in_extent(lyr, extent_proj, proj_crs, ctx)
        except Exception as e:  # noqa: BLE001
            rows.append({"name": lyr.name(), "type": "vector",
                         "in_extent": f"ERROR {e!r}", "ms": -1})
            continue
        rows.append({
            "name": lyr.name(),
            "type": f"vector/{lyr.providerType()}",
            "feature_count_total": lyr.featureCount(),
            "in_extent": found,
            "ms": round(ms, 2),
        })
        if ms > THRESHOLD_MS:
            over_threshold.append((lyr.name(), round(ms, 2)))

    summary = {
        "extent": extent_proj.toString(2),
        "proj_crs": proj_crs.authid(),
        "layers_measured": len(rows),
        "over_threshold_50ms": over_threshold,
        "rows": rows,
    }
    print("SPIKE S0.2 RESULT:")
    for r in rows:
        print("  ", r)
    print("  OVER 50ms:", over_threshold)
    return summary


if __name__ == "__main__":
    run()
