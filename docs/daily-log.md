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

---

## Day 6 — core/layout.generate_layout() minimal

**Plan:** `generate_layout()` (map extent + title) + tombol debug dock. DoD: layout muncul + bisa dibuka di Designer.

**Done:**
- `slb/core/layout.py` (baru): `generate_layout(project, *, paper, orientation, title, extent, layout_name)` → map (extent kanvas) + title bold 18pt; `PAPER_MM` A4/A3/Letter; `setFont(QFont)` + `QgsUnitTypes.LayoutMillimeters` (S0.1); validasi `ValidationError`.
- `slb/ui/dock.py`: tombol "Generate Layout (debug)" + `build_debug_layout()` (headless) / `_open_in_designer()` (GUI) / `_on_generate_debug()` (handler).
- **Uji headless di QGIS 3.34.11 → PASS** (tanpa GUI): A4 210×297 & A3 420×297, masing-masing 1 map + 1 label + extent set + masuk manager; nama unik; kertas invalid → ValidationError; dock path +1 layout tanpa window.

**Notes / surprises (penting):**
- **Timeout MCP sebelumnya = `iface.openLayoutDesigner()` membuka GUI yang memblok event loop.** Solusi: pisahkan pembukaan Designer dari pembuatan; uji pakai `build_debug_layout()` headless.
- **Bug produksi ditemukan & diperbaiki:** `QgsLayoutManager.addLayout()` GAGAL **dan menghapus objek C++** bila nama duplikat (klik generate 2× dgn judul kosong → "SLB Untitled" tabrakan). Fix: `_unique_layout_name()` (sufiks ` (n)`) + cek return `addLayout` → raise `SLBError` bila gagal.
- Audit GUI: satu-satunya pemanggilan GUI tersisa = `_open_in_designer` (sengaja, jalur user) + `QMessageBox` pada jalur error. Tidak ada GUI di `core/`.

**Tomorrow's first move (Day 7):**
- Tambah item legend, scale bar, north arrow (pakai SVG dari `slb/resources/north_arrows/` — bundle, cek `os.path.exists` sebelum `setPicturePath`, fallback label "N"), attribution ke `generate_layout()`. DoD: 6 elemen terlihat, ukuran wajar.

---

## Day 7 — Legend, scale bar, north arrow, attribution

**Plan:** Lengkapi `generate_layout()` jadi 6 elemen (map + title + legend + scale + north + attribution). DoD: 6 elemen terlihat, ukuran wajar, dalam batas A4.

**Done:**
- `slb/core/layout.py` (+73 baris): legend (ter-link ke map, footer kiri ~42% lebar), scale bar "Single Box" (`applyDefaultSize`, ter-link ke map, tengah footer), north arrow dari SVG bundled (`na_classic.svg`) via `_add_north_arrow()` — cek `os.path.exists` dulu (temuan S0.1: path SVG sistem absen di Windows), fallback label "N ↑" bila SVG hilang; attribution strip 7pt paling bawah. Zona footer (`_FOOTER_H_MM=42`) + attribution (`_ATTRIB_H_MM=5`) dipotong dari tinggi map.
- 5 SVG panah utara dibundel di `slb/resources/north_arrows/` (classic, block, compass_only, modern_circle, modern_simple).
- **Uji headless di QGIS 3.34.11 → PASS:** 6 item, legend & scale ter-link ke map, semua dalam batas A4.
- Commit `4667326`.

**Notes / surprises:**
- North arrow termuat sebagai `QgsLayoutItemPicture` (SVG bundled ada) — fallback label tidak terpakai di mesin uji.

**Tomorrow's first move (Day 8):**
- Jadikan tombol dock "Generate Layout" end-to-end (bukan "debug"): input judul opsional, feedback sukses, buka di Designer. DoD: klik → layout dibuat dari extent kanvas + judul user → terbuka di Designer.

---

## Day 8 — Dock "Generate Layout" end-to-end

**Plan:** Promosikan tombol debug jadi alur "Generate Layout" beneran + buka di Designer. DoD: klik → layout (judul user) dibuat dari extent kanvas → terbuka di Designer.

**Done:**
- `slb/ui/dock.py`: tombol "Generate Layout (debug)" → **"Generate Layout"**; tambah `QLineEdit` judul (placeholder; kosong → judul project / "Untitled"); label status sukus ("Layout '…' dibuka di Designer."); `build_debug_layout()` → `build_layout(title)` (tetap headless, tanpa GUI); handler `_on_generate` (build headless + `_open_in_designer` GUI, error → QMessageBox + status dikosongkan).
- Paper/orientation **sengaja tetap** A4/portrait — selector adalah deliverable Week 2 (roadmap), tidak ditarik maju (YAGNI).
- **Uji headless di QGIS 3.34.11 → PASS** (4 skenario, tanpa buka Designer): (1) core judul kustom "Peta Banjir Day8" → A4 210×297, 1 map/1 legend/1 scalebar + picture north + attribution, judul ada; (2) `dock.build_layout("Lewat Dock")` → masuk manager, judul ada; (3) judul kosong → fallback "Untitled"; (4) judul sama 2× → nama unik "SLB Lewat Dock (2)".
- Project bersih: 4 layout uji dihapus; **5 layout riil user (`Peta_Banjarmasin_*`) tidak disentuh**.

**Notes / surprises:**
- `banjir.qgz` punya `title()` kosong → judul kosong jatuh ke "Untitled" (bukan judul project). Sesuai desain.
- Project user sudah berisi 5 layout produksi; pastikan operasi SLB tidak pernah menghapus/menimpa layout di luar yang dibuatnya.

**Tomorrow's first move (Day 9 / Week 2 Mon):**
- `slb/core/strategies.py` — fungsi `two_column()` + `single_column()`; generate_layout mulai mendelegasikan komposisi ke strategi. DoD: dua strategi menghasilkan tata letak berbeda yang masuk akal, teruji headless.

---

## Day 9 — core/strategies.py + delegasi komposisi (Week 2 Mon)

**Plan:** `single_column()` + `two_column()` (fungsi murni → `list[ItemSpec]`); generate_layout pilih strategi by orientasi lalu materialize. DoD: dua strategi hasilkan tata letak berbeda yang masuk akal, teruji headless.

**Done:**
- `slb/core/strategies.py` (baru): `ItemSpec(TypedDict, total=False)` + `single_column(paper_w, paper_h, margin=10)` (portrait) & `two_column(...)` (landscape). Mengikuti architecture.md §10 / api-design.md §5 — dua fungsi murni, tanpa solver/kelas/registry. Geometri (TITLE/ATTRIB/GAP/NORTH/FOOTER + frac sidebar/legend) dipindah ke strategies (pemilik tata letak).
- `single_column` **mereproduksi geometri portrait Day 8 persis** (map = 10,26,190,212 di A4) → tanpa regresi.
- `two_column`: judul lebar penuh, peta kiri (~70%), sidebar kanan = legend atas + scale/north bawah.
- `slb/core/layout.py` (refactor): `_select_strategy(orientation)` + `_materialize(specs)` (peta dibuat dulu agar legend/scale bisa `setLinkedMap`). Helper per-peran `_add_title/_add_map/_add_legend/_add_scale_bar/_add_north_arrow/_add_attribution` + `_place`. Konstanta geometri lama dihapus dari layout.py (kini di strategies). Signature `generate_layout` tetap.
- **Uji headless di QGIS 3.34.11 (banjir.qgz, 9 layer) → 25 PASS / 0 FAIL:** invariant spec (6 peran, tak ada item keluar kertas, placement berbeda: legend single x=10 vs two x=143, map two lebih sempit), portrait & landscape masing-masing 6 item dengan legend+scale ter-link ke map, page size benar (210×297 / 297×210).
- Cleanup: 2 layout uji (`SLB DAY9 *`) dihapus; **5 layout produksi `Peta_Banjarmasin_*` tidak disentuh** (diverifikasi via daftar before/after).
- Commit `01bb71d`, pushed.

**Notes / surprises:**
- Kebetulan map width portrait≈landscape di A4 (190 vs 189–129 tergantung sidebar) → uji "beda layout" diandalkan pada **posisi legend** (kiri-bawah vs sidebar-kanan) & tinggi map, bukan lebar map saja.
- Scale bar pakai `applyDefaultSize()` (auto-size) → hanya di-move ke posisi spec, tidak di-resize; bounds-check sengaja longgar untuk scale bar.

**Tomorrow's first move (Day 10 / Week 2 Tue):**
- Selector kertas (A4/A3/Letter) + orientasi (portrait/landscape) di dock; `build_layout`/`_on_generate` teruskan pilihan ke `generate_layout`. Core sudah routing strategi by orientasi → tinggal kabel UI. DoD: pilihan dock → strategi & ukuran kertas sesuai.

---

## Day 10 — Selector kertas + orientasi di dock (Week 2 Tue)

**Plan:** Tambah selector kertas (A4/A3/Letter) + orientasi (portrait/landscape) di dock; teruskan pilihan ke `generate_layout`. DoD: pilihan dock → strategi & ukuran kertas sesuai.

**Done:**
- `slb/ui/dock.py`: dua `QComboBox` — kertas (`addItems(["A4","A3","Letter"])`, teks = key core) & orientasi (`addItem("Potret","portrait")` / `addItem("Lanskap","landscape")`, teks Indonesia, `currentData()` = key core). Diletakkan berdampingan via `QHBoxLayout` (dua kolom berlabel).
- `build_layout(title=None, paper=None, orientation=None)`: `paper`/`orientation` kosong → diambil dari combo (`currentText()` / `currentData()`); param eksplisit = override (untuk test). `_on_generate` tidak berubah (paper/orientasi otomatis dari combo). Murni kabel UI — core routing strategi by orientasi sudah ada sejak Day 9.
- **Uji headless di QGIS 3.34.11 (banjir.qgz) → 13 PASS / 0 FAIL:** default combo A4/portrait; (A) combo default → A4 portrait single_column (legend x=10, 6 item); (B) combo A3+landscape → 420×297 two_column (legend di sidebar x>100); (C) combo Letter+portrait → 215.9×279.4 single_column; (D) override paper/orientation menang atas combo (combo A4/portrait, override A3/landscape → 420×297 two_column).
- Cleanup: 4 layout uji (`SLB DAY10 *`) dihapus; project balik ke kondisi awal; **5 layout produksi `Peta_Banjarmasin_*` utuh** (diverifikasi before==after).

**Notes / surprises:**
- Orientasi pakai `userData` (`currentData()`) agar label UI bisa Indonesia ("Potret"/"Lanskap") tanpa mengubah key yang dikirim ke core ("portrait"/"landscape").
- Teks combo kertas sengaja = key `PAPER_MM` (A4/A3/Letter) → tidak perlu mapping; bila kelak butuh label lokal, ikuti pola `userData` orientasi.

**Tomorrow's first move (Day 11 / Week 2 Wed):**
- `core/legend.prune_legend()` — mode `safe` (visibility + LegendExcluded). DoD: legend cleaner buang entri layer tak-terlihat/excluded tanpa mengubah project; teruji headless.

---

## Day 11 — core/legend.prune_legend() mode `safe` (Week 2 Wed)

**Plan:** `prune_legend(layout, project, mode="safe")` membuang entri legend untuk layer tak-terlihat (tak-tercentang) + dikecualikan-dari-legend, TANPA mengubah project. DoD: teruji headless, idempoten.

**Done:**
- `slb/core/legend.py` (baru): `prune_legend(layout, project, mode="safe") -> int`. Mode `off` → no-op; `safe` → buang node layer yang tak-terlihat **atau** ber-flag `QgsMapLayer.Private` (proxy "exclude from legend"); mode lain (mis. `extent`) → `ValidationError` (extent menyusul Day 12). Mengikuti api-design.md §4 / architecture.md §9.
- **Kunci keamanan "tanpa mengubah project":** legend default `autoUpdateModel=True` → modelnya **berbagi** pohon dengan `project.layerTreeRoot()`. `_prune_one` mematikan auto-update dulu (QGIS lalu meng-clone pohon) sehingga hanya salinan milik legend yang disunting; `removeChildNode` tak pernah menyentuh project.
- `_is_hidden` menelusuri ke atas (self + grup induk) via `itemVisibilityChecked()` — sebab **`itemVisibilityCheckedRecursive` absen di QGIS 3.34** (dikonfirmasi via probe). `_is_legend_excluded` cek `layer.flags() & Private`.
- **Uji headless di QGIS 3.34 (banjir.qgz, 9 layer) → semua PASS / 0 FAIL** (6 grup uji): (T1) legend 9→8, layer tak-tercentang `Jaringan_Sungai` dibuang (count=1), `autoUpdateModel` jadi False, **project tree tak berubah**; (T2) idempoten — run kedua = 0, legend identik; (T3) mode `off` = 0, legend & autoUpdate utuh; (T4) set `Private` pada Google Terrain → prune buang 2 (hidden + private), keduanya hilang, predikat excluded False→True→False, flag dipulihkan; (T5) mode `extent`/bogus → `ValidationError`; (T6) layout tanpa legend → 0.
- Cleanup: 3 layout uji (`SLB DAY11 *`) dihapus; **5 layout produksi `Peta_Banjarmasin_*` utuh** (before==after); project tree final == awal; flag Google Terrain dipulihkan.

**Notes / surprises:**
- `QgsMapLayer.Private` adalah proxy terbaik untuk "exclude from legend" di core API; **setting Private TIDAK menghapus node dari project layer tree** (dikonfirmasi probe: count 9→9, node tetap) → aman dipakai sebagai sinyal prune tanpa restrukturisasi project.
- Legend `autoUpdate` **menampilkan** layer tak-tercentang (checkbox panel mengatur render, bukan inklusi legend) — itulah mengapa pembersihan ini berguna.
- `extent_timeout_ms` di signature api-design.md sengaja **tidak** dibawa: Spike S0.2 membatalkan strategi timeout-per-layer (ganti bbox pre-filter + budget kumulatif), jadi parameter itu menyesatkan; ditangani saat implement `extent` (Day 12).

**Tomorrow's first move (Day 12 / Week 2 Thu):**
- Tambah mode `extent` (opt-in checkbox di dock): buang juga layer 0 fitur di map extent. Pakai temuan S0.2 — transform extent project→CRS layer, bbox pre-filter, cek "ada ≥1 fitur" via iterator `break` (request `NoGeometry` + subset atribut kosong), budget kumulatif + fail-open; skip raster (anggap in-extent). DoD: extent mode teruji headless, tak mengubah project.

---

## Day 12 — Smart Legend mode `extent` + opt-in checkbox (Week 2 Thu)

**Plan:** Tambah mode `extent` ke `prune_legend` (opt-in checkbox dock): buang juga layer vektor 0 fitur di map extent, pakai temuan S0.2. DoD: extent mode teruji headless, tak mengubah project.

**Done:**
- `slb/core/legend.py`: mode `extent` = `safe` + buang layer vektor 0 fitur di extent peta. Implementasi mengikuti Spike S0.2 (bukan "timeout per layer"): (1) **bbox pre-filter** — transform `layer.extent()`→CRS map; tak beririsan dengan extent map → buang tanpa scan; (2) **cek ada-fitur** via iterator `break` (request `NoGeometry` + subset atribut kosong), bukan `featureCount`; (3) **budget kumulatif lintas-layer + fail-open** (`_EXTENT_BUDGET_S=2.0`) — lewat anggaran → `continue` (bukan break, agar safe-check node lain tetap jalan), simpan sisa layer; (4) **skip non-vektor** (raster dianggap in-extent). Sumber extent = `legend.linkedMap().extent()` + `.crs()`; bila tak ter-link → degrade ke safe-only. `mode` validasi diperluas (`safe`/`extent`/`off`); `extent_timeout_ms` tetap **tidak** dibawa (S0.2 membatalkannya).
- `slb/core/layout.py`: `generate_layout(..., prune_legend_mode="safe")` kini memanggil `prune_legend` setelah materialize (api-design §3 langkah 4) — wiring agar checkbox berfungsi end-to-end. Safe-prune **on by default** (architecture.md §9).
- `slb/ui/dock.py`: `QCheckBox` "Buang layer di luar extent peta" (unchecked default → `safe`; checked → `extent`); `build_layout(..., prune_legend_mode=None)` menurunkan mode dari checkbox (param eksplisit = override untuk test).
- **Uji headless di QGIS 3.34 (banjir.qgz, 9 layer) → 16/16 PASS / 0 FAIL** + 1 supplemental PASS: (T0) `off` keeps 9 entri & autoUpdate utuh; (T1) `safe` 9→8 (buang `Jaringan_Sungai` tak-tercentang, simpan 5 `Sungai_*` kosong); (T2) `extent` 9→3 (buang hidden + 5 `Sungai_*` 0-fitur, **simpan** raster Google Terrain + Digitasi_Banjir + Batas_Administrasi); (T3) idempoten (run ke-2 = 0, nama stabil); (T4) budget=0 → fail-open (extent scan dilewati, hanya safe-drop=1); (T5) extent tanpa linked-map → safe-only (drop=1); (T6) `off`=0 & mode bogus → `ValidationError`; (T7) **project tree tak berubah**. Supplemental: extent jauh dari data (atas laut) → semua vektor non-kosong ikut dibuang, hanya raster tersisa (membuktikan scan in-extent benar untuk layer non-kosong, bukan cuma layer kosong).
- Cleanup: semua layout uji (`DAY12 *`) dihapus; **5 layout produksi `Peta_Banjarmasin_*` utuh** (before==after); project tree final == awal.

**Notes / surprises:**
- Layer memory kosong (`Sungai_*`, fc=0) punya `extent()` null → bbox pre-filter mengembalikan "tak beririsan" → dibuang tanpa scan provider (gratis). Andai pre-filter lolos pun, iterator menemukan 0 fitur → tetap dibuang. Dua jalur konvergen → robust.
- Wiring `prune_legend` ke `generate_layout` mengubah perilaku default: legend kini ter-prune `safe` (buang hidden/excluded) secara default. Ini **memang** desain produk (architecture.md §9: safe = on by default) dan tidak menambah/mengurangi jumlah **item layout** (6) — hanya entri di dalam legend.
- Raster (Google Terrain, EPSG:3857) lolos transform CRS tanpa masalah; tetap di-skip (dianggap in-extent) sesuai S0.2.

**Tomorrow's first move (Day 13 / Week 2 Fri):**
- Idempotency + safety tests untuk legend cleaner (roadmap Week 2 Fri). Konsolidasikan/formalkan skenario uji (safe & extent) + tegaskan invarian "project tak berubah" sebagai jaring pengaman regresi sebelum masuk Week 3 (Presets).

---

## Day 13 — Legend cleaner regression suite (Week 2 Fri)

**Plan:** Konsolidasikan skenario uji legend cleaner (safe/extent/idempotency) jadi satu suite regresi yang permanen + tegaskan invarian "project tak berubah". DoD: suite teruji headless PASS, deterministik, tak menyentuh project user.

**Done:**
- `tests/qgis/test_legend.py` (baru): jaring regresi `prune_legend`, 11 skenario `test_*` + `run()` (laporan PASS/FAIL untuk QGIS MCP/console). Lokasi sesuai `testpaths=["tests"]` (pyproject) & testing-strategy §2.4; CI `smoke` (`qgis/qgis:release-3_34` + `pytest tests`) kini aktif (best-effort, `|| true`).
- **Kunci desain — project terisolasi:** tiap skenario membangun `QgsProject()` baru (BUKAN singleton) berisi 7 layer sintetis: 5 memory point (normal, hidden/tak-tercentang, excluded/Private, empty/0-fitur, outside/luar-extent), 1 memory point EPSG:3857 (menguji jalur transform lintas-CRS), 1 GeoTIFF 4×4 mungil (menguji skip non-vektor). Deterministik & tak mungkin menyentuh `banjir.qgz` atau 5 layout produksi.
- Skenario: `off` no-op + autoUpdate utuh; `safe` buang 2 (hidden+excluded), simpan 5; `extent` buang 4 (+empty+outside), simpan 3 (normal+3857+raster); idempoten safe & extent (run ke-2 = 0, nama stabil); budget=0 → fail-open ke safe-only (patch `_EXTENT_BUDGET_S`); extent tanpa linked-map → safe-only; mode bogus → `ValidationError`; layout tanpa legend → 0; **invarian project tree tak berubah** (before==after); **singleton untouched** (layer & layout produksi sama before/after).
- **Uji headless di QGIS 3.34.11 → 11/11 PASS / 0 FAIL.** Verifikasi pasca-uji: singleton tetap 9 layer + 5 layout `Peta_Banjarmasin_*`; **0 temp dir tersisa** (`slb_test_legend_*`/`slb_probe_*`).
- Commit `ef1974a`.

**Notes / surprises:**
- Map item di project terisolasi melaporkan **CRS kosong** (`crs().authid() == ''`) → wajib `map_item.setCrs()` eksplisit + `project.setCrs()` agar logika same-CRS/transform mode `extent` terdefinisi. (Di QGIS Desktop CRS map item mengikuti project; di project lepas tidak.)
- Layer 0-fitur → `extent().isNull()` True → bbox pre-filter langsung membuang tanpa scan provider (mengonfirmasi catatan Day 12). Layer EPSG:3857 in-extent lolos transform & scan → tetap disimpan; raster di-skip → disimpan.
- ruff/black tak terpasang di env lokal manapun; CI lint hanya menyasar `slb/`, jadi headless PASS adalah gate otoritatif (sesuai AGENTS.md). File ditulis manual mengikuti konvensi black/ruff (line-length 100, import tersortir, hindari nama ambigu `l`).
- **Week 2 tuntas** (Day 9–13): strategies, selector kertas/orientasi, Smart Legend safe+extent, dan jaring regresi. Siap masuk Week 3 (Presets).

**Tomorrow's first move (Day 14 / Week 3 Mon):**
- `presets/repository.py` — list/load/save/delete preset via file JSON (architecture.md / api-design.md). DoD: CRUD preset teruji (round-trip JSON), nama aman (`safe_filename`), error → `PresetError`/`ValidationError`.
