# Changelog

Format mengikuti [Keep a Changelog](https://keepachangelog.com/) dan
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Phase 0 validation spikes (S0.1 layout API, S0.2 legend extent perf, S0.3
  sequential atlas) — semua **GO**. Lihat `docs/spikes.md`.
- Repo bootstrap: skeleton paket `slb/` (classFactory, metadata, lifecycle
  initGui/unload + toolbar/menu, error hierarchy), tooling (ruff/black/mypy),
  CI, dan script packaging.
- Dock panel placeholder (`ui/dock.py`) dengan toggle dari toolbar, logging
  terpusat (`utils/logging.py`, RotatingFileHandler), dan helper filesystem
  (`io/safe_paths.py`: user_dir/atomic_write/ensure_dir/safe_filename).
  Cleanup dock diperbaiki (`setParent(None)`) — terverifikasi 5× reload tanpa leak.
- `core/layout.generate_layout()` minimal (map dengan extent + judul), memakai
  `setFont(QFont)` + `QgsUnitTypes.LayoutMillimeters` (temuan Spike S0.1).
  Nama layout dijamin unik (`addLayout` menghapus objek C++ bila nama duplikat).
  Tombol "Generate Layout (debug)" di dock; pembukaan Designer dipisah dari
  pembuatan layout (`build_debug_layout` headless vs `_open_in_designer` GUI)
  agar bisa diuji tanpa membuka GUI.
- `generate_layout()` lengkap 6 elemen (Day 7): legend & scale bar ter-link ke
  map, north arrow dari SVG bundled (`slb/resources/north_arrows/`, cek
  `os.path.exists` + fallback label), dan attribution strip.
- Dock "Generate Layout" end-to-end (Day 8): input judul opsional (kosong →
  judul project / "Untitled"), label status sukses, dan buka layout di Layout
  Designer. `build_debug_layout` → `build_layout(title)` (tetap headless).
  Paper/orientation tetap A4/portrait (selector dijadwalkan Week 2).

### Notes
- Target QGIS minimum: **3.34 LTR** (dikonfirmasi via Spike S0.1 di 3.34.11).
- `metadata.txt` masih memakai placeholder author/email/repository — ganti
  sebelum submit ke Plugin Repo (Day 33).
- `LICENSE` perlu diisi teks penuh GPL-3.0 sebelum rilis publik.
