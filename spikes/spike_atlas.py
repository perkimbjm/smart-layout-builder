"""Spike S0.3 — Sequential atlas safety.

Tujuan: buktikan loop atlas sequential + atomic write + cancel bisa jalan
reliable, dan ukur waktu/fitur + memory. Ini gerbang keputusan apakah Batch
Atlas Export masuk MVP (Week 4-5) atau digeser ke 1.1.

Pola yang divalidasi (akan dipakai slb/export/atlas.py):
  - loop fitur coverage (respect limit)
  - set extent QgsLayoutItemMap ke bbox fitur (transform CRS layer -> CRS map)
  - export PDF via QgsLayoutExporter.exportToPdf ke tmp/<uuid>/part_NNN.pdf
  - os.replace tmp -> output final (atomic)
  - cancel kooperatif antar-fitur -> hapus tmp, file final yang sudah jadi tetap
  - filename dari atribut + sanitize

Cara pakai (via MCP execute_code atau Console):
    exec(open(r"<path>/spikes/spike_atlas.py").read())
    run(limit=5)                 # normal: 5 PDF
    run(limit=5, cancel_after=2) # uji cancel: 2 PDF lalu batal, tmp bersih
"""

from __future__ import annotations

import os
import re
import shutil
import time
import uuid

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsPrintLayout,
    QgsLayoutItemMap,
    QgsLayoutItemLabel,
    QgsLayoutSize,
    QgsLayoutPoint,
    QgsUnitTypes,
    QgsLayoutExporter,
    QgsCoordinateTransform,
)
from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtGui import QFont

OUT_DIR = r"C:/Users/FAQIH/Documents/KOMPETENSI/PLUGIN/EASY-LAYOUT/spikes/atlas_out"
TMP_ROOT = r"C:/Users/FAQIH/Documents/KOMPETENSI/PLUGIN/EASY-LAYOUT/spikes/tmp"
COVERAGE_NAME = "Batas_Administrasi_Kelurahan_2025_AR_75K"
NAME_FIELD_CANDIDATES = ["nama", "NAMOBJ", "NAMA", "kelurahan", "WADMKD", "name"]


def _safe_filename(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]+', "_", str(s)).strip()
    return (s or "unnamed")[:200]


def _find_coverage(project) -> QgsVectorLayer | None:
    for lyr in project.mapLayers().values():
        if isinstance(lyr, QgsVectorLayer) and lyr.name() == COVERAGE_NAME:
            return lyr
    # fallback: vector layer dengan fitur terbanyak
    vecs = [l for l in project.mapLayers().values()
            if isinstance(l, QgsVectorLayer) and l.featureCount() > 0]
    return max(vecs, key=lambda l: l.featureCount()) if vecs else None


def _pick_name_field(layer: QgsVectorLayer) -> str | None:
    names = [f.name() for f in layer.fields()]
    for cand in NAME_FIELD_CANDIDATES:
        for n in names:
            if n.lower() == cand.lower():
                return n
    return names[0] if names else None


def _build_min_layout(project) -> tuple[QgsPrintLayout, QgsLayoutItemMap]:
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(f"SLB Atlas Spike {uuid.uuid4().hex[:6]}")
    mm = QgsUnitTypes.LayoutMillimeters
    page = layout.pageCollection().page(0)
    page.setPageSize(QgsLayoutSize(297, 210, mm))  # A4 landscape

    title = QgsLayoutItemLabel(layout)
    title.setText("Atlas spike")
    f = title.font(); f.setPointSize(16); title.setFont(f)
    layout.addLayoutItem(title)
    title.attemptMove(QgsLayoutPoint(10, 8, mm))
    title.attemptResize(QgsLayoutSize(277, 12, mm))

    m = QgsLayoutItemMap(layout)
    m.setRect(QRectF(0, 0, 277, 180))
    m.setFrameEnabled(True)
    layout.addLayoutItem(m)
    m.attemptMove(QgsLayoutPoint(10, 24, mm))
    m.attemptResize(QgsLayoutSize(277, 176, mm))

    project.layoutManager().addLayout(layout)
    return layout, m


def run(limit: int = 5, cancel_after: int | None = None, dpi: int = 120) -> dict:
    project = QgsProject.instance()
    coverage = _find_coverage(project)
    if coverage is None:
        return {"ok": False, "error": "no coverage layer"}
    name_field = _pick_name_field(coverage)

    layout, map_item = _build_min_layout(project)

    job = uuid.uuid4().hex[:8]
    tmp_dir = os.path.join(TMP_ROOT, job)
    os.makedirs(tmp_dir, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    # CRS transform layer -> project (extent map dalam CRS project)
    need_xform = coverage.crs() != project.crs()
    xform = (QgsCoordinateTransform(coverage.crs(), project.crs(),
                                    project.transformContext())
             if need_xform else None)

    exporter = QgsLayoutExporter(layout)
    pdf_settings = QgsLayoutExporter.PdfExportSettings()
    pdf_settings.dpi = dpi

    per_feature_ms = []
    written = []
    cancelled = False

    feats = coverage.getFeatures()
    idx = 0
    for feat in feats:
        if idx >= limit:
            break
        if cancel_after is not None and idx >= cancel_after:
            cancelled = True
            break

        t0 = time.perf_counter()
        bbox = feat.geometry().boundingBox()
        if xform is not None:
            bbox = xform.transformBoundingBox(bbox)
        bbox.scale(1.15)
        map_item.setExtent(bbox)

        raw = feat[name_field] if name_field else f"feat{idx+1}"
        fname = f"peta_{_safe_filename(raw)}.pdf"
        tmp_path = os.path.join(tmp_dir, f"part_{idx+1:03d}.pdf")
        final_path = os.path.join(OUT_DIR, fname)

        res = exporter.exportToPdf(tmp_path, pdf_settings)
        ok = (res == QgsLayoutExporter.Success) and os.path.exists(tmp_path)
        if ok:
            os.replace(tmp_path, final_path)   # atomic
            written.append(os.path.basename(final_path))
        per_feature_ms.append(round((time.perf_counter() - t0) * 1000, 1))
        idx += 1

    # cleanup tmp bila cancel (file final yang sudah jadi tetap)
    tmp_remaining = []
    if cancelled:
        if os.path.isdir(tmp_dir):
            tmp_remaining = os.listdir(tmp_dir)
            shutil.rmtree(tmp_dir, ignore_errors=True)
    else:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # memory (best-effort)
    try:
        import psutil  # type: ignore
        rss_mb = round(psutil.Process(os.getpid()).memory_info().rss / 1e6, 1)
    except Exception:  # noqa: BLE001
        rss_mb = "n/a (psutil absent)"

    # buang layout spike
    project.layoutManager().removeLayout(layout)

    summary = {
        "ok": True,
        "coverage": coverage.name(),
        "name_field": name_field,
        "limit": limit,
        "cancel_after": cancel_after,
        "cancelled": cancelled,
        "files_written": written,
        "files_count": len(written),
        "per_feature_ms": per_feature_ms,
        "avg_ms": round(sum(per_feature_ms) / len(per_feature_ms), 1) if per_feature_ms else 0,
        "tmp_dir_exists_after": os.path.isdir(tmp_dir),
        "tmp_remaining_at_cancel": tmp_remaining,
        "process_rss_mb": rss_mb,
        "out_dir": OUT_DIR,
    }
    print("SPIKE S0.3 RESULT:", summary)
    return summary


if __name__ == "__main__":
    run()
