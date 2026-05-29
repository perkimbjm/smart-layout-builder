"""Regression net for the Smart Legend cleaner (``slb.core.legend.prune_legend``).

Day 13 (Week 2 Fri): consolidates the safe/extent/idempotency scenarios that
were run ad-hoc each day into a durable, deterministic suite, and pins the core
safety invariant: **pruning never edits the project layer tree**.

Why an *isolated* project (not ``QgsProject.instance()``):
  Earlier daily checks ran against the live ``banjir.qgz`` and depended on its
  exact layer state (which can drift) while risking the user's 5 production
  layouts. Here every scenario builds a throwaway ``QgsProject`` with synthetic
  memory layers (+ one tiny GeoTIFF), so the suite is reproducible and can never
  touch the user's project. ``test_singleton_project_untouched`` additionally
  asserts that guarantee explicitly.

Running:
  - Live in QGIS via the QGIS MCP / Python console::

        exec(open(r"<repo>/tests/qgis/test_legend.py", encoding="utf-8").read())
        run()

    (inject ``<repo>`` on ``sys.path`` and purge cached ``slb`` modules first so
    a fresh copy of the code under test is imported).
  - Under ``pytest`` inside a QGIS environment (CI ``smoke`` job): the ``test_*``
    functions are collected directly; ``_ensure_qgis_app`` bootstraps a headless
    ``QgsApplication`` when one is not already running.
"""

from __future__ import annotations

import shutil
import tempfile
import traceback
from contextlib import contextmanager
from dataclasses import dataclass

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsGeometry,
    QgsLayoutItemLegend,
    QgsLayoutItemMap,
    QgsLayoutSize,
    QgsMapLayer,
    QgsPointXY,
    QgsPrintLayout,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
    QgsUnitTypes,
    QgsVectorLayer,
)

import slb.core.legend as legmod
from slb.core.legend import prune_legend
from slb.errors import ValidationError

# Map covers lon/lat 0..10 in EPSG:4326; CRS is set explicitly on the layout map
# because an isolated project's map item otherwise reports an empty CRS.
_MAP_EXTENT = (0.0, 0.0, 10.0, 10.0)
_INSIDE = (5.0, 5.0)
_OUTSIDE = (100.0, 100.0)

# Expected outcomes per mode (layer names by role):
#   hidden / excluded -> dropped by `safe`
#   empty / outside   -> additionally dropped by `extent`
#   norm / 3857 / raster -> always kept (3857 exercises the cross-CRS transform;
#                           raster exercises the non-vector skip)
_ALL = ("L_norm", "L_hidden", "L_excl", "L_empty", "L_outside", "L_3857", "L_raster")
_SAFE_KEEP = {"L_norm", "L_empty", "L_outside", "L_3857", "L_raster"}
_EXTENT_KEEP = {"L_norm", "L_3857", "L_raster"}

_qgis_app = None


def _ensure_qgis_app() -> None:
    """Bootstrap a headless QGIS app when none is running (pytest/CI container).

    Inside the user's QGIS (MCP / Desktop) an instance already exists -> no-op.
    """
    global _qgis_app
    if QgsApplication.instance() is None:
        _qgis_app = QgsApplication([], False)
        _qgis_app.initQgis()


@dataclass
class _Fixture:
    project: QgsProject
    crs: QgsCoordinateReferenceSystem
    tmpdir: str


def _make_point_layer(name: str, points, crs: str = "EPSG:4326") -> QgsVectorLayer:
    layer = QgsVectorLayer(f"Point?crs={crs}", name, "memory")
    feats = []
    for x, y in points:
        feat = QgsFeature()
        feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
        feats.append(feat)
    if feats:
        layer.dataProvider().addFeatures(feats)
    layer.updateExtents()
    return layer


def _make_raster_layer(name: str, tmpdir: str) -> QgsRasterLayer:
    """Tiny 4x4 GeoTIFF covering the map extent (EPSG:4326)."""
    import os

    from osgeo import gdal, osr

    path = os.path.join(tmpdir, f"{name}.tif")
    dataset = gdal.GetDriverByName("GTiff").Create(path, 4, 4, 1, gdal.GDT_Byte)
    dataset.SetGeoTransform([0.0, 2.5, 0.0, 10.0, 0.0, -2.5])
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    dataset.SetProjection(srs.ExportToWkt())
    dataset.GetRasterBand(1).Fill(128)
    dataset.FlushCache()
    dataset = None  # noqa: F841 - close the GDAL handle so QGIS can read the file
    return QgsRasterLayer(path, name)


@contextmanager
def _legend_fixture():
    """Build an isolated project with the 7 synthetic layers; clean up after."""
    _ensure_qgis_app()
    tmpdir = tempfile.mkdtemp(prefix="slb_test_legend_")
    project = QgsProject()
    crs_4326 = QgsCoordinateReferenceSystem("EPSG:4326")
    crs_3857 = QgsCoordinateReferenceSystem("EPSG:3857")
    project.setCrs(crs_4326)
    try:
        to_3857 = QgsCoordinateTransform(crs_4326, crs_3857, project.transformContext())
        inside_3857 = to_3857.transform(QgsPointXY(*_INSIDE))

        layers = [
            _make_point_layer("L_norm", [_INSIDE]),
            _make_point_layer("L_hidden", [_INSIDE]),
            _make_point_layer("L_excl", [_INSIDE]),
            _make_point_layer("L_empty", []),
            _make_point_layer("L_outside", [_OUTSIDE]),
            _make_point_layer("L_3857", [(inside_3857.x(), inside_3857.y())], crs="EPSG:3857"),
            _make_raster_layer("L_raster", tmpdir),
        ]
        for layer in layers:
            assert layer.isValid(), f"layer {layer.name()} tidak valid"
            project.addMapLayer(layer)

        # hidden: uncheck the layer-tree node (effectively not rendered)
        hidden_node = project.layerTreeRoot().findLayer(layers[1].id())
        hidden_node.setItemVisibilityChecked(False)
        # excluded-from-legend: set after adding (Private keeps the project node,
        # confirmed Day 11) so the legend's excluded check is what drops it.
        layers[2].setFlags(layers[2].flags() | QgsMapLayer.Private)

        yield _Fixture(project=project, crs=crs_4326, tmpdir=tmpdir)
    finally:
        project.clear()
        shutil.rmtree(tmpdir, ignore_errors=True)


def _make_layout(fx: _Fixture, *, linked: bool = True):
    mm = QgsUnitTypes.LayoutMillimeters
    layout = QgsPrintLayout(fx.project)
    layout.initializeDefaults()
    layout.setName("SLB DAY13 TEST")
    layout.pageCollection().page(0).setPageSize(QgsLayoutSize(210, 297, mm))

    map_item = QgsLayoutItemMap(layout)
    map_item.setRect(0, 0, 100, 100)
    map_item.setCrs(fx.crs)
    map_item.setExtent(QgsRectangle(*_MAP_EXTENT))
    layout.addLayoutItem(map_item)

    legend = QgsLayoutItemLegend(layout)
    if linked:
        legend.setLinkedMap(map_item)
    layout.addLayoutItem(legend)
    return layout, legend, map_item


def _legend_names(legend: QgsLayoutItemLegend) -> set:
    return {node.layer().name() for node in legend.model().rootGroup().findLayers()}


def _project_tree(project: QgsProject) -> list:
    return [node.layer().name() for node in project.layerTreeRoot().findLayers()]


# --------------------------------------------------------------------------- #
# Scenarios
# --------------------------------------------------------------------------- #


def test_off_mode_is_noop_and_keeps_autoupdate():
    with _legend_fixture() as fx:
        layout, legend, _ = _make_layout(fx)
        assert _legend_names(legend) == set(_ALL)
        assert prune_legend(layout, fx.project, mode="off") == 0
        assert _legend_names(legend) == set(_ALL)
        # off returns before touching legends, so the shared model stays live
        assert legend.autoUpdateModel() is True


def test_safe_drops_hidden_and_excluded_only():
    with _legend_fixture() as fx:
        layout, legend, _ = _make_layout(fx)
        dropped = prune_legend(layout, fx.project, mode="safe")
        assert dropped == 2
        assert _legend_names(legend) == _SAFE_KEEP
        # pruning clones the tree, so auto-update is switched off
        assert legend.autoUpdateModel() is False


def test_extent_additionally_drops_empty_and_outside():
    with _legend_fixture() as fx:
        layout, legend, _ = _make_layout(fx)
        dropped = prune_legend(layout, fx.project, mode="extent")
        assert dropped == 4
        # cross-CRS in-extent layer and raster survive; empty/outside removed
        assert _legend_names(legend) == _EXTENT_KEEP


def test_safe_is_idempotent():
    with _legend_fixture() as fx:
        layout, legend, _ = _make_layout(fx)
        assert prune_legend(layout, fx.project, mode="safe") == 2
        first = _legend_names(legend)
        assert prune_legend(layout, fx.project, mode="safe") == 0
        assert _legend_names(legend) == first == _SAFE_KEEP


def test_extent_is_idempotent():
    with _legend_fixture() as fx:
        layout, legend, _ = _make_layout(fx)
        assert prune_legend(layout, fx.project, mode="extent") == 4
        first = _legend_names(legend)
        assert prune_legend(layout, fx.project, mode="extent") == 0
        assert _legend_names(legend) == first == _EXTENT_KEEP


def test_extent_budget_exhausted_falls_open_to_safe_only():
    """Zero budget -> feature scans are skipped (fail-open); only safe drops."""
    with _legend_fixture() as fx:
        layout, legend, _ = _make_layout(fx)
        original = legmod._EXTENT_BUDGET_S
        legmod._EXTENT_BUDGET_S = 0.0
        try:
            dropped = prune_legend(layout, fx.project, mode="extent")
        finally:
            legmod._EXTENT_BUDGET_S = original
        assert dropped == 2
        assert _legend_names(legend) == _SAFE_KEEP


def test_extent_without_linked_map_is_safe_only():
    with _legend_fixture() as fx:
        layout, legend, _ = _make_layout(fx, linked=False)
        dropped = prune_legend(layout, fx.project, mode="extent")
        assert dropped == 2
        assert _legend_names(legend) == _SAFE_KEEP


def test_invalid_mode_raises_validation_error():
    with _legend_fixture() as fx:
        layout, _, _ = _make_layout(fx)
        try:
            prune_legend(layout, fx.project, mode="bogus")
        except ValidationError:
            pass
        else:
            raise AssertionError("mode tidak valid harus memunculkan ValidationError")


def test_layout_without_legend_returns_zero():
    with _legend_fixture() as fx:
        mm = QgsUnitTypes.LayoutMillimeters
        layout = QgsPrintLayout(fx.project)
        layout.initializeDefaults()
        layout.setName("SLB DAY13 NOLEGEND")
        layout.pageCollection().page(0).setPageSize(QgsLayoutSize(210, 297, mm))
        map_item = QgsLayoutItemMap(layout)
        map_item.setRect(0, 0, 100, 100)
        layout.addLayoutItem(map_item)
        assert prune_legend(layout, fx.project, mode="extent") == 0


def test_project_tree_unchanged_after_prune():
    """The core invariant: prune edits only the legend's cloned model."""
    with _legend_fixture() as fx:
        before = _project_tree(fx.project)
        assert set(before) == set(_ALL)
        layout_safe, _, _ = _make_layout(fx)
        prune_legend(layout_safe, fx.project, mode="safe")
        layout_ext, _, _ = _make_layout(fx)
        prune_legend(layout_ext, fx.project, mode="extent")
        # same layers, same order, same count — prune touched only the legend clone
        assert _project_tree(fx.project) == before


def test_singleton_project_untouched():
    """Defends the production-layout safety rule: never mutate banjir.qgz."""
    _ensure_qgis_app()
    instance = QgsProject.instance()
    layers_before = set(instance.mapLayers().keys())
    layouts_before = {lyt.name() for lyt in instance.layoutManager().layouts()}
    with _legend_fixture() as fx:
        layout, _, _ = _make_layout(fx)
        prune_legend(layout, fx.project, mode="extent")
    assert set(instance.mapLayers().keys()) == layers_before
    assert {lyt.name() for lyt in instance.layoutManager().layouts()} == layouts_before


# --------------------------------------------------------------------------- #
# Standalone runner (QGIS MCP / console)
# --------------------------------------------------------------------------- #


def _scenarios():
    return sorted(
        (name, fn)
        for name, fn in globals().items()
        if name.startswith("test_") and callable(fn)
    )


def run() -> dict:
    """Run every scenario, print a PASS/FAIL report, return a summary dict."""
    results = []
    for name, fn in _scenarios():
        try:
            fn()
            results.append((name, True, ""))
        except Exception:  # noqa: BLE001 - aggregate; detail captured for the report
            results.append((name, False, traceback.format_exc().strip().splitlines()[-1]))

    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    print(f"SLB legend regression: {passed} PASS / {failed} FAIL")
    for name, ok, detail in results:
        suffix = f"  -> {detail}" if detail else ""
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}{suffix}")
    return {
        "passed": passed,
        "failed": failed,
        "failures": [(name, detail) for name, ok, detail in results if not ok],
    }


if __name__ == "__main__":
    run()
