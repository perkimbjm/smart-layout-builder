# Phase 0 — Validation Spikes

> Tujuan Phase 0: validasi 3 asumsi paling berisiko **sebelum** menulis kode produksi.
> Referensi: `docs/development-roadmap.md` §2, `docs/review/risk-analysis.md`.
> Status environment saat penulisan: QGIS belum terhubung via MCP (`mcp__qgis__ping` →
> "Could not connect"). Script spike sudah siap; kolom **Hasil live-run** diisi saat
> dijalankan di QGIS (Console atau MCP).

| Spike | Risiko ditangani | Status |
|-------|------------------|--------|
| S0.1 Layout API feasibility | R-01/feasibility layout engine | 🟢 **GO** (QGIS 3.34.11, ~75 ms, PNG export OK) |
| S0.2 Feature-in-extent performance | R-03 (legend perf) | 🟢 **GO** (warm <1 ms; cold ≤139 ms hanya layer geometri-berat) |
| S0.3 Sequential atlas safety | R-02 (atlas crash/corrupt) | 🟢 **GO** (5→5 PDF, cancel bersih, 0 file parsial) |

---

## S0.1 — Layout API Feasibility

**Pertanyaan:** Bisakah kita membangun `QgsPrintLayout` lengkap (map + title + legend +
scale bar + north arrow + attribution) secara programmatic dalam **< 200 LOC inti**,
memakai API PyQGIS yang stabil?

**Script:** [`spikes/spike_layout.py`](../spikes/spike_layout.py)

### Cara menjalankan

**Opsi A — QGIS Python Console (utama):**
1. Buka project QGIS apa saja yang punya ≥ 1 layer.
2. `Plugins → Python Console`.
3. Jalankan:
   ```python
   exec(open(r"C:/Users/FAQIH/Documents/KOMPETENSI/PLUGIN/EASY-LAYOUT/spikes/spike_layout.py").read())
   ```
4. Layout otomatis dibuat + terbuka di Layout Designer. Ringkasan dicetak ke Console
   (cari baris `SPIKE S0.1 RESULT: {...}`).

**Opsi B — via MCP (`mcp__qgis__execute_code`):**
- Pastikan QGIS + plugin MCP berjalan (`mcp__qgis__ping` harus sukses).
- Kirim isi `spike_layout.py` lalu panggil `run()`.

### API PyQGIS yang dipakai (kandidat untuk `slb/core/layout.py`)

| Kebutuhan | Kelas / Method |
|-----------|----------------|
| Container layout | `QgsPrintLayout(project)` + `initializeDefaults()` |
| Daftar layout | `project.layoutManager().addLayout(layout)` |
| Ukuran kertas | `layout.pageCollection().page(0).setPageSize(QgsLayoutSize(w,h,unit))` |
| Map | `QgsLayoutItemMap` + `setExtent()` + `attemptMove/attemptResize` |
| Title / attribution | `QgsLayoutItemLabel` + `setText/setFontSize` |
| Legend | `QgsLayoutItemLegend` + `setLinkedMap(map)` |
| Scale bar | `QgsLayoutItemScaleBar` + `setStyle()` + `setLinkedMap()` + `applyDefaultSize()` |
| North arrow | `QgsLayoutItemPicture` + `setPicturePath(svg)` |
| Posisi/ukuran | `QgsLayoutPoint`, `QgsLayoutSize`, `QgsUnitTypes.LayoutMillimeters` |

### LOC inti

Fungsi `build_layout()` (blok antara `=== INTI ===` dan `=== AKHIR INTI ===`):
**~95 baris termasuk komentar & blank** → **di bawah target 200 LOC**. ✅
(LOC statement efektif ≈ 70.)

### Risiko API yang HARUS dicek saat live-run

Catat hasilnya di tabel "Hasil live-run" di bawah:

1. **`QgsUnitTypes.LayoutMillimeters`** — di QGIS versi baru kemungkinan pindah ke
   `Qgis.LayoutUnit.Millimeters`. Kalau error, ganti import. → tentukan target API
   untuk `slb/core/layout.py`.
2. **North arrow SVG path** — `spike_layout.py` memakai path Linux
   (`/usr/share/qgis/svg/arrows/NorthArrow_02.svg`). Di **Windows** path-nya beda
   (biasanya `<QGIS install>/apps/qgis/svg/arrows/...`). Solusi produksi: **bundle SVG
   sendiri** di `slb/resources/icons/north-arrow.svg` (sesuai rencana Day 7) supaya
   lintas-OS. Spike sudah fallback ke label "N ↑" bila SVG tak ketemu.
3. **`setStyle("Single Box")`** scale bar — nama style string. Verifikasi masih valid
   di LTR target (alternatif enum `Qgis.ScaleBarSegmentSizeMode` tidak diperlukan untuk
   style).
4. **`page.setPageSize(QgsLayoutSize(...))`** — pastikan halaman benar-benar berganti
   ukuran (cek di Designer, bukan tetap A4 default).
5. **Versi QGIS** — catat `Qgis.QGIS_VERSION` untuk menetapkan `qgisMinimumVersion`
   di `metadata.txt` (dipakai Day 4).

### Hasil live-run ✅ (dijalankan via MCP `execute_code`)

**Environment:** QGIS **3.34.11-Prizren** (LTR), Windows, profile default.
**Project uji:** project riil Banjarmasin (11 layer: batas kelurahan, 5 layer sungai,
digitasi banjir 2025/2026, Google Terrain, jaringan sungai) + 2 sample memory layer.

| Item | Nilai |
|------|-------|
| QGIS version | 3.34.11-Prizren |
| OS | Windows |
| `build_seconds` | **0.0754 s** (~75 ms, jauh di bawah budget) |
| `item_count` | 14 |
| `item_types` | Label, Legend, Map, Page, Picture, ScaleBar (6 tipe) ✅ |
| `QgsUnitTypes.LayoutMillimeters` OK? | **Ya** (unit int = 0; tidak perlu `Qgis.LayoutUnit`) |
| North arrow SVG OK? | **Tidak** — path Linux `exists=False` → item Picture kosong. **Harus bundle SVG sendiri** (Day 7). Fallback label hanya jalan kalau `setPicturePath` raise; ternyata tidak raise, jadi item ada tapi blank. |
| Scale bar OK? | Ya (no error; `setStyle/applyDefaultSize/setLinkedMap`) |
| Page size A3 landscape berubah benar? | **Ya** → `(420.0, 297.0, mm)` |
| Legend ter-link + terisi? | **Ya** → `linkedMap=True`, 7 entri dari layer riil |
| Export `QgsLayoutExporter.exportToImage` → PNG | **Success**, 997 KB ([`spikes/s01_proof.png`](../spikes/s01_proof.png)) — sekaligus de-risk pipeline export untuk S0.3 |

### Temuan API untuk produksi (`slb/core/layout.py`, Day 6)

1. **Font:** `QgsLayoutItemLabel` **tidak punya** `setFontSize` di 3.34. Pakai
   `item.setFont(QFont)` (helper `_set_font`) atau `setTextFormat(QgsTextFormat)`.
   → keputusan produksi: pakai `QFont` (paling simpel & stabil), pertimbangkan
   `QgsTextFormat` bila butuh styling lanjutan.
2. **North arrow:** WAJIB bundle SVG sendiri di `slb/resources/icons/north-arrow.svg`
   dan resolusi path relatif terhadap plugin dir (jangan andalkan path sistem). Sudah
   sesuai rencana Day 7. Tambahan: cek `os.path.exists(path)` sebelum `setPicturePath`,
   baru fallback ke label bila perlu.
3. **Unit:** `QgsUnitTypes.LayoutMillimeters` valid di 3.34 — aman dipakai.
4. **Page resize:** `page.setPageSize(QgsLayoutSize(w,h,mm))` bekerja sempurna.
5. **Legend:** `setLinkedMap(map)` + `legend.refresh()` cukup untuk mengisi otomatis.
6. **Export:** `QgsLayoutExporter(layout).exportToImage(path, ImageExportSettings)` →
   `Success`. Pola sama (`exportToPdf`) akan dipakai S0.3 / `export/atlas.py`.
7. **`qgisMinimumVersion = 3.34`** dikonfirmasi untuk `metadata.txt` (Day 4).

### Keputusan

**Status: 🟢 GO.**

Script menghasilkan layout valid dengan 6 elemen kartografi dalam ~75 ms, page A3
ter-resize benar, legend terisi otomatis, dan pipeline export PNG sukses. Dua penyesuaian
ditemukan (font API + bundle north-arrow SVG) — keduanya kecil dan sudah masuk rencana.
→ Lanjut desain `slb/core/layout.py` (Day 6) memakai temuan API di atas.

---

## S0.2 — Feature-in-extent Performance (Day 2)

**Pertanyaan:** Apakah hitung feature dengan filter spatial cukup cepat (< 50 ms/layer)
untuk mode `extent` di Smart Legend Cleaner?

**Script:** [`spikes/spike_extent.py`](../spikes/spike_extent.py)

**Metode:** Untuk pruning legend kita hanya butuh tahu "ada ≥ 1 fitur di extent?",
bukan count penuh → iterator + ambil 1 fitur + `break`. Request dioptimalkan
(`NoGeometry` + subset atribut kosong). Extent canvas (CRS project) ditransform ke CRS
tiap layer sebelum `setFilterRect`. Raster di-skip. Dijalankan 3× untuk membedakan
cold-start vs biaya menetap.

### Hasil live-run ✅ (QGIS 3.34.11, project riil Banjarmasin, extent canvas EPSG:4326)

| Layer | Provider | Fitur | Di extent | Run 1 (cold) | Run 2 | Run 3 (warm) |
|-------|----------|-------|-----------|--------------|-------|--------------|
| Batas_Administrasi_Kelurahan | ogr | 52 | ✅ | 15.19 ms | 0.92 ms | 0.67 ms |
| Digitasi_Banjir 2025/2026 | ogr | 209 | ✅ | 0.84 ms | 3.05 ms | 0.69 ms |
| Jaringan_Sungai 2025 | ogr | 336 | ✅ | **138.73 ms** | **115.0 ms** | 0.90 ms |
| Sungai_* (×5, memory kosong) | memory | 0 | ❌ | ~0.05 ms | ~0.05 ms | ~0.05 ms |
| Google Terrain | raster | — | skip | 0 ms | 0 ms | 0 ms |

### Temuan kunci

1. **Biaya hanya di cold-start.** Layer line kompleks (Jaringan_Sungai, 336 segmen)
   butuh ~2 akses untuk QGIS membangun spatial index lazily; sesudahnya **< 1 ms**.
   Layer lain warm dalam 1 akses.
2. **Jumlah fitur bukan prediktor.** 209 fitur = 0.84 ms, tapi 336 fitur = 138 ms.
   Penentu = kompleksitas geometri + ada/tidaknya spatial index, bukan count.
3. **"Timeout 50 ms/layer" (rencana awal) tidak bisa diimplementasi sebagai interrupt
   keras** — biaya berada di dalam satu panggilan provider C++ yang tak bisa dipotong
   dari Python. Perlu strategi pengganti (lihat di bawah).

### Desain produksi untuk `slb/core/legend.py` mode `extent` (Day 11–12)

Ganti "timeout per layer" dengan kombinasi berikut (semua murah & implementable):

1. **Opt-in, off by default.** Worst-case cold (138 ms) × banyak layer kompleks bisa
   jadi beberapa detik di generate pertama. Aman sebagai pilihan, bukan default.
2. **Pre-filter bbox murah:** transform `layer.extent()` → bila TIDAK irisan dengan map
   extent → pasti 0 fitur → prune, tanpa scan fitur. Ini menyingkirkan mayoritas kasus
   "jelas di luar extent" nyaris gratis.
3. **Budget kumulatif lintas-layer + fail-open:** akumulasi `perf_counter` antar layer;
   bila total melewati anggaran (mis. 2 s), hentikan pengujian sisa layer dan **keep**
   (fail-open). Ini bisa di-cek di Python (antar panggilan), beda dengan interrupt
   di tengah panggilan.
4. **Skip raster** (treat intersect bbox = in-extent) — sudah terbukti benar.
5. Catatan: setelah generate pertama, index hangat → generate berikutnya cepat. Boleh
   pertimbangkan jadikan default di rilis lanjutan setelah feedback nyata.

### Keputusan

**Status: 🟢 GO (dengan revisi desain).**

Performa nyata sangat baik untuk mayoritas layer (≤ 15 ms cold, < 1 ms warm). Hanya
layer geometri-berat yang mahal saat cold, dan itu dapat ditangani via pre-filter bbox +
budget kumulatif + opt-in. Mode `extent` **layak**, tetap **opt-in** di 1.0, dengan desain
di atas menggantikan ide "timeout per layer".

---

## S0.3 — Sequential Atlas Safety (Day 3)

**Pertanyaan:** Apakah loop atlas sequential + atomic write + cancel bisa reliable?

**Script:** [`spikes/spike_atlas.py`](../spikes/spike_atlas.py)

**Metode:** Bangun layout minimal (map+title) → loop fitur coverage
`Batas_Administrasi_Kelurahan` (52 kelurahan) → set extent map ke bbox fitur (transform
CRS layer→project) → `QgsLayoutExporter.exportToPdf()` ke `tmp/<job>/part_NNN.pdf` →
`os.replace` ke output final. Field nama auto-deteksi. Dua run: normal (5 fitur) + cancel
(batal setelah 2).

### Hasil live-run ✅ (QGIS 3.34.11, coverage riil 52 kelurahan)

| Metrik | Nilai |
|--------|-------|
| 5 fitur → 5 PDF? | **Ya** (peta_Alalak Selatan.pdf, …Tengah, …Utara, Antasan Besar, Antasan Kecil Timur) |
| Field nama auto-deteksi | `NAMOBJ` ✅ (dari kandidat list) |
| Waktu/fitur (normal) | [812, 1423, 549, 452, 585] ms → **avg 764 ms** |
| Cancel: file tertulis | 2 (sesuai `cancel_after=2`) ✅ |
| Cancel: tmp bersih? | **Ya** — `tmp_dir_exists_after=False`, `tmp_remaining=[]`, TMP_ROOT kosong |
| File parsial / 0-byte? | **Tidak ada** ✅ |
| Atomic write (tmp+os.replace) | Terbukti aman, termasuk saat cancel |
| Memory peak | n/a — `psutil` tidak ada di Python QGIS (lihat temuan #4) |

### Temuan kunci untuk `slb/export/atlas.py` (Week 4–5)

1. **Pipeline terbukti:** `QgsLayoutExporter.exportToPdf(path, PdfExportSettings)` →
   `Success`. Atomic write (tmp + `os.replace`) menjamin **tidak ada file parsial** bahkan
   saat dibatalkan / proses mati.
2. **Cancel kooperatif antar-fitur** = cukup & bersih. Render satu PDF adalah panggilan
   blocking yang tak bisa diinterupsi di tengah — jadi cek `cancel_event` **di antara**
   fitur (persis seperti `architecture.md` §7–8).
3. **Auto-deteksi field nama** berhasil (`NAMOBJ`). Produksi: sediakan daftar kandidat +
   biarkan user override via template filename.
4. **Memory:** `psutil` tidak tersedia di Python QGIS → metrik "memory peak < 4 GB"
   (rencana Day 28) tidak bisa via psutil. Alternatif: observasi Task Manager manual saat
   stress test, atau cukup andalkan sifat **sequential** (satu render pada satu waktu)
   yang inheren membatasi memory. Sequential = aman by design.
5. **Basemap online mendominasi waktu:** ~450–1400 ms/fitur sebagian besar = fetch tile
   Google Terrain per render. Tanpa basemap jaringan jauh lebih cepat. **Implikasi:**
   atlas dengan XYZ basemap = network-bound → progress UX + ETA (Day 24–25) penting;
   dokumentasikan sebagai known-limit; pertimbangkan saran "cache/lower-zoom basemap"
   untuk atlas besar.

### Keputusan

**Status: 🟢 GO.** Atlas sequential aman, atomic, cancellable. **Atlas tetap masuk MVP
(Week 4–5)** — tidak perlu digeser ke 1.1. 52 kelurahan ≈ ~40 dtk dengan basemap online
(dapat diterima untuk sequential + progress bar).

---

## Ringkasan Keputusan Phase 0

> Diisi setelah ketiga spike selesai. Ini gerbang masuk ke Week 1 (Day 4).

| Spike | Keputusan | Implikasi |
|-------|-----------|-----------|
| S0.1 | 🟢 GO | API layout terbukti; temuan font + bundle SVG masuk ke `core/layout.py` (Day 6–7); `qgisMinimumVersion=3.34` |
| S0.2 | 🟢 GO | extent-mode **opt-in**; ganti "timeout/layer" → bbox pre-filter + budget kumulatif + fail-open (Day 11–12) |
| S0.3 | 🟢 GO | atlas sequential aman → **tetap masuk MVP Week 4–5** |

**Gate Phase 0: ✅ LULUS.** Ketiga spike GO. Boleh lanjut **Day 4 (repo bootstrap)** dengan
ruang lingkup MVP penuh (Auto Layout + Smart Legend + Atlas). Tidak ada pemotongan scope.

**Bekal konkret untuk Week 1 dst.:**
- `qgisMinimumVersion = 3.34` (S0.1).
- `core/layout.py`: `setFont(QFont)` bukan `setFontSize`; bundle north-arrow SVG sendiri.
- `core/legend.py` extent-mode: bbox pre-filter + budget kumulatif + fail-open (bukan
  timeout per-layer).
- `export/atlas.py`: pola `exportToPdf` + tmp/`os.replace` + cancel antar-fitur; auto-deteksi
  field nama; basemap online = network-bound (butuh progress/ETA + known-limit).
