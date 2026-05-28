# Daily Log — Smart Layout Builder

Format per `plan` (Format Catatan Harian). Ditulis singkat tiap hari kerja.

---

## Day 1 — Spike S0.1: Layout API feasibility

**Plan:** Buktikan bisa membangun `QgsPrintLayout` lengkap (6 elemen) < 200 LOC inti.

**Done:**
- Tulis [`spikes/spike_layout.py`](../spikes/spike_layout.py) — `build_layout()` ~95 baris (≈70 statement) → di bawah target 200 LOC.
- Jalankan live di QGIS **3.34.11-Prizren** via MCP terhadap project riil Banjarmasin (11 layer).
- Hasil: layout 6 elemen terbentuk dalam **~75 ms**; page A3 landscape benar `(420,297,mm)`; legend ter-link + 7 entri; **export PNG sukses** (997 KB, `spikes/s01_proof.png`).
- Keputusan **🟢 GO**. Detail + temuan API di [`docs/spikes.md`](spikes.md).
- Tulis [`docs/spikes.md`](spikes.md) lengkap + scaffold S0.2/S0.3.
- Siapkan [`spikes/spike_extent.py`](../spikes/spike_extent.py) untuk Day 2.

**Notes / surprises:**
- API: `QgsLayoutItemLabel` **tidak punya** `setFontSize` di 3.34 → pakai `setFont(QFont)` (atau `setTextFormat`). Sudah dipatch di spike.
- North arrow: path SVG sistem (Linux) tidak ada di Windows → item Picture **blank**. Produksi WAJIB bundle SVG sendiri (Day 7) + cek `os.path.exists` sebelum `setPicturePath`.
- `qgisMinimumVersion = 3.34` dikonfirmasi untuk `metadata.txt` (Day 4).
- Export pipeline (`QgsLayoutExporter`) sudah terbukti jalan → risiko atlas (R-02) sebagian turun sebelum S0.3.
- Project uji adalah project kerja riil user; disuntik 2 memory layer (`kelurahan_sample`, `titik_kantor`) + layout spike. Cleanup terkirim tapi koneksi MCP putus sebelum terverifikasi. Memory layer non-persisten (hilang bila QGIS ditutup tanpa save).

**Tomorrow's first move (Day 2):**
- Reconnect MCP → jalankan `spikes/spike_extent.py` (`run()`), isi tabel timing S0.2 di `docs/spikes.md`, putuskan extent-mode opt-in vs default. Sekalian verifikasi/cleanup 2 memory layer bila masih ada.

---

## Day 2 — Spike S0.2: Feature-in-extent performance

**Plan:** Ukur waktu cek "ada ≥1 fitur di extent" per layer; putuskan extent-mode opt-in vs default.

**Done:**
- Verifikasi cleanup: project sudah bersih (sample layer & layout spike hilang sejak cleanup pertama; respons "null" tadi cuma efek koneksi drop).
- Jalankan [`spikes/spike_extent.py`](../spikes/spike_extent.py) **3×** di project riil (9 layer).
- Hasil cold-vs-warm tercatat di [`docs/spikes.md`](spikes.md): warm <1 ms semua; cold worst 138 ms (Jaringan_Sungai 336 fitur line).
- Keputusan **🟢 GO**, extent-mode tetap **opt-in**.
- Revisi desain: "timeout 50 ms/layer" diganti **bbox pre-filter + budget kumulatif + fail-open** (tak bisa interrupt panggilan provider dari Python). Diselaraskan ke [`architecture.md`](architecture.md) §9.

**Notes / surprises:**
- Biaya mahal hanya cold-start (QGIS bangun spatial index lazily; butuh ~2 akses untuk layer line kompleks). Jumlah fitur BUKAN prediktor — geometri & index yang menentukan.
- Transform extent project→CRS layer wajib sebelum `setFilterRect` (project EPSG:4326; aman).

**Tomorrow's first move (Day 3):**
- Tulis `spikes/spike_atlas.py` → loop fitur Batas_Administrasi (52 kelurahan) render PDF ke tmp + os.replace; test 5 fitur + cancel; ukur waktu/fitur & memory. Keputusan atlas masuk MVP atau geser 1.1.

---

## Day 3 — Spike S0.3: Sequential atlas safety

**Plan:** Buktikan loop atlas sequential + atomic write + cancel reliable; keputusan atlas MVP vs 1.1.

**Done:**
- Tulis [`spikes/spike_atlas.py`](../spikes/spike_atlas.py); jalankan 2 skenario di coverage riil 52 kelurahan.
- Normal: 5 fitur → 5 PDF (field `NAMOBJ` auto-deteksi), avg 764 ms/fitur, tmp bersih.
- Cancel (batal stlh 2): 2 PDF jadi, tmp bersih, **0 file parsial/0-byte** → atomic write aman.
- Keputusan **🟢 GO** — atlas tetap masuk MVP Week 4–5. Detail di [`docs/spikes.md`](spikes.md).
- Cleanup: artefak PDF/tmp dihapus; project QGIS bersih (tak ada layout sisa).

**Notes / surprises:**
- Waktu/fitur didominasi fetch tile **Google Terrain online** (network-bound). Tanpa basemap jaringan jauh lebih cepat → progress/ETA (Day 24–25) penting; jadikan known-limit.
- Cancel hanya bisa antar-fitur (render PDF = panggilan blocking). Cukup & bersih.
- `psutil` tidak ada di Python QGIS → metrik memory andalkan sifat sequential (1 render/saat) bukan psutil.

**Phase 0 GATE: ✅ LULUS — ketiga spike GO. Lanjut Day 4 (repo bootstrap), scope MVP penuh.**

**Tomorrow's first move (Day 4):**
- Bootstrap repo: `slb/__init__.py` (classFactory), `metadata.txt` (qgisMinimumVersion=3.34), `plugin.py` (initGui/unload + toolbar/menu), `version.py`, `errors.py`, paket kosong (core/export/presets/ui/io/utils), `pyproject.toml`, `.gitignore`, `LICENSE`, `CHANGELOG.md`, `scripts/package.py`, `.github/workflows/ci.yml`. DoD: plugin enable/disable di QGIS bersih tanpa error.

---

## Day 4 — Repo bootstrap (plugin skeleton loadable)

**Plan:** Skeleton plugin yang loadable + scaffolding repo. DoD: enable/disable di QGIS tanpa error.

**Done:**
- Paket `slb/`: `__init__.py` (classFactory), `version.py` (`1.0.0-beta1`), `metadata.txt` (qgisMin=3.34), `plugin.py` (initGui/unload + toolbar/menu + signal-tracking + placeholder dock), `errors.py` (SLBError ×5), paket kosong core/export/presets/ui/io/utils, ikon `resources/icons/slb_logo.svg`.
- Scaffolding: `pyproject.toml` (ruff/black/mypy), `.gitignore`, `CHANGELOG.md`, `LICENSE` (notis GPL-3.0 + TODO teks penuh), `Makefile`, `scripts/package.py`, `.github/workflows/ci.yml`.
- **Uji live di QGIS 3.34.11 → PASS:** classFactory OK; initGui +1 aksi; unload bersih (aksi 0, koneksi 0, dock None); metadata terbaca.
- **Build ZIP OK:** `dist/smart_layout_builder-1.0.0-beta1.zip` (12 files), version.py ↔ metadata.txt cocok.

**Notes / surprises:**
- `metadata.txt` author/email/repository masih placeholder `TODO` → user isi sebelum submit (Day 33).
- `LICENSE` perlu teks penuh GPL-3.0 sebelum rilis (1 perintah curl, dicatat di file).
- `git init` + commit pertama BELUM dijalankan (menunggu konfirmasi user; aturan: commit hanya bila diminta).

**Tomorrow's first move (Day 5):**
- `slb/utils/logging.py` (`configure_logging` RotatingFileHandler), `slb/io/safe_paths.py` (`user_dir/atomic_write/ensure_dir/safe_filename`), `slb/ui/dock.py` (SLBDock placeholder QLabel), ganti `_show_dock` placeholder jadi dock asli. DoD: klik toolbar → dock muncul/sembunyi; reload 5× tanpa leak.

---

## Day 5 — Toolbar + dock asli + logging + safe_paths

**Plan:** Dock asli + logging + helper path. DoD: toggle dock; reload 5× tanpa leak.

**Done:**
- `io/safe_paths.py`: `user_dir()` (pakai folder profil QGIS + fallback), `ensure_dir`, `atomic_write` (tmp+fsync+os.replace), `safe_filename`.
- `utils/logging.py`: `configure_logging()` RotatingFileHandler (1 MB×3) ke `<profil>/SLB/logs/slb.log`; idempoten (aman saat reload).
- `ui/dock.py`: `SLBDock(QDockWidget)` placeholder (objectName diset untuk saveState).
- `plugin.py`: `configure_logging()` di initGui; aksi toolbar **checkable** → `_toggle_dock` (lazy-create + show/hide) + `_sync_action` (sinkron status saat dock ditutup manual).
- **Uji live QGIS 3.34.11 → PASS:** dock show/hide benar; **5× siklus init/unload tanpa error & 0 leak**; unload bersih; log file terbentuk.

**Notes / surprises:**
- Bug ditemukan & diperbaiki: `deleteLater()` saja tidak melepas dock dari mainWindow seketika → `docks_after_unload=1` (leak). Fix: `removeDockWidget` → `setParent(None)` → `deleteLater()`. Setelah fix + processEvents: 0 leak.
- `user_dir()` memakai `QgsApplication.qgisSettingsDirPath()/SLB` (lebih tepat dari `~/.qgis/SLB`); fallback ke home untuk test tanpa QGIS.

**Tomorrow's first move (Day 6):**
- `core/layout.py` `generate_layout()` minimal (map + title) memakai temuan S0.1 (`setFont(QFont)`, `QgsUnitTypes.LayoutMillimeters`). Wire tombol debug di dock. DoD: klik → layout muncul di Layouts list dengan map (canvas extent) + title; bisa dibuka di Designer.
