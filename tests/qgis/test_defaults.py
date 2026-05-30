"""Regression net for the bundled-preset installer (``slb.presets.defaults``).

Day 15 (Week 3 Tue): pins the first-run contract of
``ensure_defaults_installed()`` so the Day 16 dropdown can rely on a populated
``<profile>/SLB/presets/`` directory, and so future plugin updates never
clobber a user-edited copy of a bundled preset.

Why isolated temp directories (NOT the real plugin / profile dirs):
  ``ensure_defaults_installed`` reads from a bundled source and writes to the
  user's preset folder; running it untouched would pollute the live profile.
  Two ``mkdtemp`` directories are wired in via monkey-patches —
  ``defaults_mod.bundled_dir`` and ``repository.presets_dir`` — and restored
  in ``finally`` so the user profile remains untouched even on a raised
  exception. A separate scenario also exercises the *real* bundled directory
  to confirm the shipped JSONs are valid against the repository contract.

Running:
  - Live in QGIS via the QGIS MCP / Python console::

        exec(open(r"<repo>/tests/qgis/test_defaults.py", encoding="utf-8").read())
        run()

    (inject ``<repo>`` on ``sys.path`` and purge cached ``slb`` modules first
    so a fresh copy of the code under test is imported).
  - Under ``pytest`` in any Python environment with the package importable
    (no QGIS required — installer only depends on stdlib + ``shutil``).
"""

from __future__ import annotations

import json
import shutil
import tempfile
import traceback
from contextlib import contextmanager
from pathlib import Path

import slb.presets.defaults as defaults_mod
import slb.presets.repository as repomod
from slb.errors import PresetError


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


_BUNDLED_NAMES = ("classic_a4_portrait.json", "classic_a3_landscape.json")


def _sample_preset(name: str = "Sample", paper: str = "A4", orientation: str = "portrait") -> dict:
    """Minimal preset that satisfies ``repository._validate``."""
    return {
        "schema": 1,
        "name": name,
        "paper": paper,
        "orientation": orientation,
        "strategy": "single_column",
        "items": [
            {"role": "title", "anchor": "top", "h_mm": 12},
            {"role": "map", "fill": "center"},
            {"role": "legend", "anchor": "bottom-left", "w_mm": 80, "h_mm": 42},
            {"role": "scale_bar", "anchor": "bottom", "h_mm": 10},
            {"role": "north_arrow", "anchor": "bottom-right", "w_mm": 20, "h_mm": 20},
            {"role": "attribution", "anchor": "bottom", "h_mm": 5},
        ],
    }


def _write_bundled_fixture(src_dir: Path, names: tuple[str, ...] = _BUNDLED_NAMES) -> None:
    """Populate a fake bundled dir with valid preset JSONs."""
    for filename in names:
        stem = Path(filename).stem
        data = _sample_preset(name=stem)
        (src_dir / filename).write_text(json.dumps(data), encoding="utf-8")


@contextmanager
def _isolated_dirs(populate_src: bool = True):
    """Patch both ``defaults_mod.bundled_dir`` and ``repository.presets_dir`` to
    throwaway temp dirs. Restores the originals (and cleans up) on exit."""
    src = Path(tempfile.mkdtemp(prefix="slb_test_defaults_src_"))
    dst = Path(tempfile.mkdtemp(prefix="slb_test_defaults_dst_"))
    original_bundled = defaults_mod.bundled_dir
    original_user = repomod.presets_dir
    defaults_mod.bundled_dir = lambda: src  # type: ignore[assignment]
    repomod.presets_dir = lambda: dst  # type: ignore[assignment]
    try:
        if populate_src:
            _write_bundled_fixture(src)
        yield src, dst
    finally:
        defaults_mod.bundled_dir = original_bundled  # type: ignore[assignment]
        repomod.presets_dir = original_user  # type: ignore[assignment]
        shutil.rmtree(src, ignore_errors=True)
        shutil.rmtree(dst, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Scenarios — isolated bundled / user dirs
# --------------------------------------------------------------------------- #


def test_first_run_copies_all_bundled():
    with _isolated_dirs() as (_src, dst):
        copied = defaults_mod.ensure_defaults_installed()
        assert copied == len(_BUNDLED_NAMES)
        for filename in _BUNDLED_NAMES:
            assert (dst / filename).exists()


def test_second_run_is_noop():
    with _isolated_dirs() as (_src, dst):
        defaults_mod.ensure_defaults_installed()
        # Capture mtimes/contents before the second run.
        snapshot = {p.name: p.read_bytes() for p in dst.iterdir() if p.suffix == ".json"}

        copied = defaults_mod.ensure_defaults_installed()
        assert copied == 0
        for name, blob in snapshot.items():
            assert (dst / name).read_bytes() == blob


def test_does_not_overwrite_user_edited_file():
    """User-edited files keep their content even when a bundled copy is newer."""
    with _isolated_dirs() as (_src, dst):
        # Simulate a user who previously edited the A4 preset.
        edited = _sample_preset(name="My Custom A4", paper="A4")
        edited["items"][0]["style"] = {"font_size_pt": 36}  # user tweak
        (dst / "classic_a4_portrait.json").write_text(json.dumps(edited), encoding="utf-8")

        copied = defaults_mod.ensure_defaults_installed()

        # Only the missing landscape file should have been installed.
        assert copied == 1
        assert (dst / "classic_a3_landscape.json").exists()

        # The user's edit survived intact.
        on_disk = json.loads((dst / "classic_a4_portrait.json").read_text(encoding="utf-8"))
        assert on_disk == edited
        assert on_disk["name"] == "My Custom A4"
        assert on_disk["items"][0]["style"]["font_size_pt"] == 36


def test_partial_overlap_only_copies_missing():
    """1 of 2 bundled already in user dir → only the other is copied."""
    with _isolated_dirs() as (_src, dst):
        shutil.copyfile(_src / "classic_a4_portrait.json", dst / "classic_a4_portrait.json")
        a4_before = (dst / "classic_a4_portrait.json").read_bytes()

        copied = defaults_mod.ensure_defaults_installed()

        assert copied == 1
        assert (dst / "classic_a3_landscape.json").exists()
        # Pre-existing A4 untouched.
        assert (dst / "classic_a4_portrait.json").read_bytes() == a4_before


def test_missing_bundled_dir_returns_zero():
    """Defensive: a packaging mistake (missing dir) must not crash initGui."""
    with _isolated_dirs(populate_src=False) as (src, dst):
        shutil.rmtree(src)  # remove the temp dir we just created
        copied = defaults_mod.ensure_defaults_installed()
        assert copied == 0
        assert list(dst.iterdir()) == []


def test_empty_bundled_dir_returns_zero():
    """Existing but empty bundled dir is fine — defaults are simply absent."""
    with _isolated_dirs(populate_src=False) as (_src, dst):
        copied = defaults_mod.ensure_defaults_installed()
        assert copied == 0
        assert list(dst.iterdir()) == []


def test_skips_non_json_files():
    """Stray ``README.md`` / ``notes.txt`` in the bundled dir must be ignored."""
    with _isolated_dirs() as (src, dst):
        (src / "README.md").write_text("documentation", encoding="utf-8")
        (src / "notes.txt").write_text("stray", encoding="utf-8")

        copied = defaults_mod.ensure_defaults_installed()

        assert copied == len(_BUNDLED_NAMES)
        installed = sorted(p.name for p in dst.iterdir())
        assert installed == sorted(_BUNDLED_NAMES)


def test_copied_files_are_loadable_through_repository():
    """End-to-end: after install, ``load_preset`` succeeds for each bundled stem."""
    with _isolated_dirs() as (_src, _dst):
        defaults_mod.ensure_defaults_installed()
        for filename in _BUNDLED_NAMES:
            stem = Path(filename).stem
            data = repomod.load_preset(stem)
            assert data["name"] == stem  # matches the fixture written by _sample_preset


def test_returns_count_of_files_actually_copied():
    """Return value mirrors the number of writes performed, not bundled count."""
    with _isolated_dirs() as (_src, dst):
        assert defaults_mod.ensure_defaults_installed() == len(_BUNDLED_NAMES)
        # Delete one; next run should copy exactly one.
        (dst / "classic_a4_portrait.json").unlink()
        assert defaults_mod.ensure_defaults_installed() == 1
        assert defaults_mod.ensure_defaults_installed() == 0


def test_isolation_restores_originals_after_context():
    """Smoke check: monkey-patches don't leak past the context manager."""
    real_bundled = defaults_mod.bundled_dir
    real_user = repomod.presets_dir
    with _isolated_dirs():
        assert defaults_mod.bundled_dir is not real_bundled
        assert repomod.presets_dir is not real_user
    assert defaults_mod.bundled_dir is real_bundled
    assert repomod.presets_dir is real_user


# --------------------------------------------------------------------------- #
# Scenarios — the *real* bundled JSONs ship in valid shape
# --------------------------------------------------------------------------- #


def test_real_bundled_dir_exists_and_is_populated():
    """``slb/resources/builtin_presets/`` ships at least the two MVP presets."""
    src = defaults_mod.bundled_dir()  # real path, not patched
    assert src.is_dir(), f"Bundled preset dir missing: {src}"
    names = sorted(p.name for p in src.glob("*.json"))
    for required in _BUNDLED_NAMES:
        assert required in names, f"Missing bundled preset: {required}"


def test_real_bundled_files_pass_repository_validation():
    """Each shipped JSON must satisfy ``repository._validate`` (`load_preset` shape)."""
    src = defaults_mod.bundled_dir()
    for path in sorted(src.glob("*.json")):
        raw = path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"{path.name} is not valid JSON: {exc}") from exc
        # Run the same validator the repository uses — surfaces any drift.
        try:
            repomod._validate(data)  # noqa: SLF001 — intentional cross-module assertion
        except PresetError as exc:
            raise AssertionError(f"{path.name} fails repository validation: {exc}") from exc
        # Sanity: required keys present and well-typed.
        assert data["schema"] == 1
        assert isinstance(data["name"], str) and data["name"]
        assert data["paper"] in {"A4", "A3", "Letter"}
        assert data["orientation"] in {"portrait", "landscape"}
        assert isinstance(data["items"], list) and data["items"]
        # And exactly one ``map`` item per database-schema.md §4.3 (sanity, not
        # enforced by the repo today; we want bundled files to model the rule).
        roles = [item.get("role") for item in data["items"]]
        assert roles.count("map") == 1, f"{path.name} must contain exactly one 'map' item"


def test_real_bundled_install_into_isolated_user_dir():
    """Use the *real* bundled dir but patch only the user dir → install, verify, load."""
    real_bundled = defaults_mod.bundled_dir
    original_user = repomod.presets_dir
    tmp_user = Path(tempfile.mkdtemp(prefix="slb_test_defaults_real_user_"))
    repomod.presets_dir = lambda: tmp_user  # type: ignore[assignment]
    try:
        # Ensure no accidental patching of the bundled side leaked in.
        assert defaults_mod.bundled_dir is real_bundled
        copied = defaults_mod.ensure_defaults_installed()
        # Bundled dir ships ≥ 2 presets today; copy count must equal what's there.
        bundled_count = len(list(defaults_mod.bundled_dir().glob("*.json")))
        assert copied == bundled_count
        # Every installed file must round-trip through ``load_preset`` cleanly.
        for path in sorted(tmp_user.glob("*.json")):
            data = repomod.load_preset(path.stem)
            assert data["paper"] in {"A4", "A3", "Letter"}
            assert data["orientation"] in {"portrait", "landscape"}
    finally:
        repomod.presets_dir = original_user  # type: ignore[assignment]
        shutil.rmtree(tmp_user, ignore_errors=True)


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
    print(f"SLB defaults regression: {passed} PASS / {failed} FAIL")
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
