"""Regression net for the preset repository (``slb.presets.repository``).

Day 14 (Week 3 Mon): pins the CRUD contract of the JSON-backed preset store —
round-trip equality, minimal validation, safe-filename storage, list
robustness, and PresetError surfacing — so later wiring (defaults installer,
dock dropdown, settings dialog) can lean on a stable foundation.

Why an *isolated* temp directory (not the real ``<profile>/SLB/presets/``):
  Repository functions resolve their path via ``presets_dir()``; running
  against the live QGIS profile would litter the user's directory with test
  fixtures and risk colliding with real presets they later install. The
  fixture monkey-patches ``presets_dir`` to a ``tempfile.mkdtemp`` location
  and restores the original in ``finally`` — guaranteeing the user's data
  stays untouched even if a scenario raises.

Running:
  - Live in QGIS via the QGIS MCP / Python console::

        exec(open(r"<repo>/tests/qgis/test_presets.py", encoding="utf-8").read())
        run()

    (inject ``<repo>`` on ``sys.path`` and purge cached ``slb`` modules first
    so a fresh copy of the code under test is imported).
  - Under ``pytest`` in any Python environment with the package importable
    (no QGIS required — repository only depends on stdlib + ``io.safe_paths``).
"""

from __future__ import annotations

import json
import shutil
import tempfile
import traceback
from contextlib import contextmanager
from pathlib import Path

import slb.presets.repository as repomod
from slb.errors import PresetError


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _sample_preset(
    name: str = "Classic A4 Portrait",
    paper: str = "A4",
    orientation: str = "portrait",
) -> dict:
    """Return a minimally valid preset dict that mirrors database-schema.md §4."""
    return {
        "schema": 1,
        "name": name,
        "paper": paper,
        "orientation": orientation,
        "strategy": "single_column",
        "items": [
            {"role": "title", "anchor": "top", "h_mm": 12, "style": {"font_size_pt": 18}},
            {"role": "map", "fill": "center"},
            {"role": "legend", "anchor": "bottom-left", "w_mm": 80, "h_mm": 50},
            {"role": "scale_bar", "anchor": "bottom", "h_mm": 10},
            {"role": "north_arrow", "anchor": "bottom-right", "w_mm": 20, "h_mm": 20},
            {"role": "attribution", "anchor": "bottom", "h_mm": 5},
        ],
    }


@contextmanager
def _isolated_presets_dir():
    """Redirect ``repomod.presets_dir`` to a throwaway temp dir; clean up after."""
    tmpdir = Path(tempfile.mkdtemp(prefix="slb_test_presets_"))
    original = repomod.presets_dir
    repomod.presets_dir = lambda: tmpdir  # type: ignore[assignment]
    try:
        yield tmpdir
    finally:
        repomod.presets_dir = original  # type: ignore[assignment]
        shutil.rmtree(tmpdir, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Scenarios
# --------------------------------------------------------------------------- #


def test_save_then_load_roundtrip():
    with _isolated_presets_dir():
        data = _sample_preset()
        path = repomod.save_preset("classic_a4_portrait", data)
        assert path.exists()
        assert path.suffix == ".json"
        loaded = repomod.load_preset("classic_a4_portrait")
        assert loaded == data


def test_save_returns_path_inside_presets_dir():
    with _isolated_presets_dir() as tmpdir:
        path = repomod.save_preset("classic_a4_portrait", _sample_preset())
        assert path == tmpdir / "classic_a4_portrait.json"
        # On-disk JSON parses back to the same dict.
        assert json.loads(path.read_text(encoding="utf-8")) == _sample_preset()


def test_save_atomic_leaves_no_tmp_file():
    """``atomic_write`` uses a sibling ``.tmp`` then ``os.replace`` — verify cleanup."""
    with _isolated_presets_dir() as tmpdir:
        repomod.save_preset("classic_a4_portrait", _sample_preset())
        leftovers = [p.name for p in tmpdir.iterdir() if p.name.endswith(".tmp")]
        assert leftovers == []


def test_list_presets_returns_sorted_metadata():
    with _isolated_presets_dir() as tmpdir:
        repomod.save_preset("classic_a4_portrait", _sample_preset())
        repomod.save_preset(
            "bold_a3_landscape",
            _sample_preset(name="Bold A3", paper="A3", orientation="landscape"),
        )

        metas = repomod.list_presets()
        assert [m["name"] for m in metas] == ["bold_a3_landscape", "classic_a4_portrait"]
        assert metas[0]["paper"] == "A3"
        assert metas[0]["orientation"] == "landscape"
        assert metas[0]["path"] == tmpdir / "bold_a3_landscape.json"
        assert metas[1]["paper"] == "A4"
        assert metas[1]["orientation"] == "portrait"


def test_list_empty_dir_returns_empty_list():
    with _isolated_presets_dir():
        assert repomod.list_presets() == []


def test_list_skips_corrupt_files_silently():
    """One good + one corrupt + one missing-keys -> list keeps only the good one."""
    with _isolated_presets_dir() as tmpdir:
        repomod.save_preset("good", _sample_preset())
        (tmpdir / "garbage.json").write_text("{not valid json", encoding="utf-8")
        (tmpdir / "incomplete.json").write_text(
            json.dumps({"schema": 1, "name": "x"}), encoding="utf-8"
        )

        metas = repomod.list_presets()
        assert [m["name"] for m in metas] == ["good"]


def test_load_missing_raises_preset_error():
    with _isolated_presets_dir():
        try:
            repomod.load_preset("nope")
        except PresetError as exc:
            assert "nope" in str(exc)
        else:
            raise AssertionError("load_preset(missing) harus PresetError")


def test_load_invalid_json_raises_preset_error():
    with _isolated_presets_dir() as tmpdir:
        (tmpdir / "garbage.json").write_text("{not valid json", encoding="utf-8")
        try:
            repomod.load_preset("garbage")
        except PresetError as exc:
            assert "garbage" in str(exc)
            assert exc.hint  # hint carries the JSON parser detail
        else:
            raise AssertionError("load_preset(garbage) harus PresetError")


def test_load_missing_required_key_raises_preset_error():
    with _isolated_presets_dir() as tmpdir:
        data = _sample_preset()
        data.pop("items")
        (tmpdir / "no_items.json").write_text(json.dumps(data), encoding="utf-8")
        try:
            repomod.load_preset("no_items")
        except PresetError as exc:
            assert "items" in str(exc)
        else:
            raise AssertionError("load_preset tanpa key wajib harus PresetError")


def test_load_unsupported_schema_raises_preset_error():
    with _isolated_presets_dir() as tmpdir:
        data = _sample_preset()
        data["schema"] = 2
        (tmpdir / "bad_schema.json").write_text(json.dumps(data), encoding="utf-8")
        try:
            repomod.load_preset("bad_schema")
        except PresetError as exc:
            assert "2" in str(exc) or "schema" in str(exc).lower()
        else:
            raise AssertionError("schema != 1 harus PresetError")


def test_save_rejects_missing_required_key_and_writes_no_file():
    with _isolated_presets_dir() as tmpdir:
        bad = _sample_preset()
        bad.pop("paper")
        try:
            repomod.save_preset("bad", bad)
        except PresetError as exc:
            assert "paper" in str(exc)
        else:
            raise AssertionError("save_preset tanpa key wajib harus PresetError")
        # Validation runs *before* the write — no file should be on disk.
        assert list(tmpdir.glob("*.json")) == []


def test_save_rejects_non_dict_payload():
    with _isolated_presets_dir() as tmpdir:
        try:
            repomod.save_preset("listy", ["not", "a", "dict"])  # type: ignore[arg-type]
        except PresetError:
            pass
        else:
            raise AssertionError("save_preset(non-dict) harus PresetError")
        assert list(tmpdir.glob("*.json")) == []


def test_save_rejects_unsupported_schema():
    with _isolated_presets_dir() as tmpdir:
        data = _sample_preset()
        data["schema"] = 99
        try:
            repomod.save_preset("future", data)
        except PresetError:
            pass
        else:
            raise AssertionError("save_preset(schema != 1) harus PresetError")
        assert list(tmpdir.glob("*.json")) == []


def test_save_accepts_dict_without_schema_key():
    """schema is optional; absent treated as 1 (api-design.md §9)."""
    with _isolated_presets_dir():
        data = _sample_preset()
        data.pop("schema")
        path = repomod.save_preset("no_schema", data)
        assert path.exists()
        # Round-trip preserves the absence (we never mutate caller data).
        assert "schema" not in repomod.load_preset("no_schema")


def test_delete_removes_file():
    with _isolated_presets_dir() as tmpdir:
        repomod.save_preset("temp", _sample_preset())
        assert (tmpdir / "temp.json").exists()
        repomod.delete_preset("temp")
        assert not (tmpdir / "temp.json").exists()
        assert repomod.list_presets() == []
        # Subsequent load must surface a PresetError, not a stale read.
        try:
            repomod.load_preset("temp")
        except PresetError:
            pass
        else:
            raise AssertionError("load_preset setelah delete harus PresetError")


def test_delete_missing_raises_preset_error():
    with _isolated_presets_dir():
        try:
            repomod.delete_preset("nope")
        except PresetError as exc:
            assert "nope" in str(exc)
        else:
            raise AssertionError("delete_preset(missing) harus PresetError")


def test_safe_filename_used_for_storage():
    """Forbidden filesystem chars in the key are sanitized but the entry is still
    reachable by the *same* key (safe_filename is deterministic)."""
    with _isolated_presets_dir() as tmpdir:
        risky = 'bad/name:with*chars?"<>|'
        path = repomod.save_preset(risky, _sample_preset())
        # File on disk has no forbidden chars (safe_filename replaced them).
        forbidden = set('/\\:*?"<>|')
        assert not (forbidden & set(path.name))
        assert path.parent == tmpdir
        # Load via the same key reaches the same file.
        loaded = repomod.load_preset(risky)
        assert loaded == _sample_preset()
        # And delete cleans it up.
        repomod.delete_preset(risky)
        assert list(tmpdir.glob("*.json")) == []


def test_presets_dir_isolation_does_not_leak_real_user_dir():
    """Smoke check: scenarios touch only the temp dir, not the real profile."""
    real = repomod.presets_dir
    with _isolated_presets_dir() as tmpdir:
        assert repomod.presets_dir() == tmpdir
        repomod.save_preset("scoped", _sample_preset())
        assert (tmpdir / "scoped.json").exists()
    # After the context, the real resolver is restored.
    assert repomod.presets_dir is real


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
    print(f"SLB presets regression: {passed} PASS / {failed} FAIL")
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
