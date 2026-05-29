# PROJECT STATE — Smart Layout Builder (SLB)

> **File ini adalah ringkasan status proyek yang selalu diperbarui.**
> Agent/kontributor cukup membaca **file ini dulu**, lalu beberapa file relevan
> yang ditunjuk di bawah. Perbarui file ini di akhir setiap hari kerja
> (lihat [Cara merawat file ini](#cara-merawat-file-ini)).

**Apa ini:** Plugin QGIS untuk auto-layout peta, smart legend, dan batch atlas export.
**Versi:** `1.0.0-beta1` (pre-alpha, MVP dalam pengerjaan)
**QGIS minimum:** 3.34 LTR (dikonfirmasi Spike S0.1 di 3.34.11-Prizren)
**Commit terakhir:** `01bb71d` — Day 9
**Branch:** `main` (sinkron dengan `origin/main`)
**Repo:** https://github.com/perkimbjm/smart-layout-builder

---

## Posisi sekarang

- **Fase:** Phase 1 — MVP (Week 1–6). Phase 0 (spikes) ✅ LULUS.
- **Minggu/Hari:** Week 2 mulai (Day 9 selesai). **Berikutnya: Day 10 = Week 2 Selasa.**
- **Status terakhir:** Day 9 pushed (`01bb71d`); headless test 25 PASS / 0 FAIL.
- **Next task (Day 10):** selector kertas + orientasi di dock; generate routing ke
  strategi yang benar (portrait→single_column, landscape→two_column sudah jalan di core).
  DoD: user pilih kertas/orientasi di dock → layout memakai strategi sesuai pilihan.

---

## Baca ini dulu (urutan untuk onboarding cepat)

1. **`PROJECT_STATE.md`** (file ini) — status & peta proyek.
2. **`AGENTS.md`** — environment & aturan workflow (commit/push/test). **Wajib.**
3. **`docs/daily-log.md`** — catatan harian (rencana, hasil, kejutan, langkah besok).
4. **`docs/development-roadmap.md`** — rencana Week-by-Week MVP.
5. **`docs/spikes.md`** — temuan Phase 0 (keputusan teknis & batasan API).
6. Source yang sedang aktif: `slb/core/layout.py`, `slb/ui/dock.py`, `slb/plugin.py`.

Docs perencanaan lain (arsitektur, fitur, API, dll.) ada di `docs/` — baca sesuai kebutuhan.

---

## Progress MVP (Week 1–6)

| Week | Tema | Status |
|------|------|--------|
| 0 | Validation spikes (S0.1/S0.2/S0.3) | ✅ Selesai — semua GO |
| 1 | Plumbing + first layout | ✅ Selesai (Day 4–8) |
| 2 | Composition strategies + Smart Legend v1 | ⏳ Berikutnya (mulai Day 9) |
| 3 | Presets | ⬜ Belum |
| 4 | Atlas v1 (sequential) | ⬜ Belum |
| 5 | Atlas v2 (progress + cancel + merge) | ⬜ Belum |
| 6 | Polish + docs + package → `1.0.0-beta1` | ⬜ Belum |

---

## Log singkat per hari (+ commit)

| Day | Deliverable | Commit |
|-----|-------------|--------|
| 1–3 | Phase 0 spikes (layout API, legend extent perf, sequential atlas) — semua GO | `e8ff3fc` |
| 4 | Repo bootstrap: skeleton `slb/`, metadata, plugin lifecycle, tooling, CI | `e8ff3fc` |
| 5 | Toolbar + dock asli, logging (RotatingFileHandler), `io/safe_paths.py`; 5× reload tanpa leak | `e8ff3fc` |
| 6 | `core/layout.generate_layout()` minimal (map extent + title); jalur dock headless vs Designer | `bedd4eb` |
| 7 | 6 elemen: legend & scale ter-link ke map, north arrow SVG bundled + fallback, attribution | `4667326` |
| 8 | Dock "Generate Layout" end-to-end: input judul, status sukses, buka Designer | `47154ad` |
| 9 | `core/strategies.py` (single_column/two_column); generate_layout delegasi komposisi via ItemSpec | `01bb71d` |

Detail lengkap tiap hari ada di [`docs/daily-log.md`](docs/daily-log.md).

---

## Peta source (`slb/`)

| File | Fungsi |
|------|--------|
| `__init__.py` | `classFactory` (entry point QGIS) |
| `version.py` | `__version__ = "1.0.0-beta1"` |
| `metadata.txt` | metadata plugin (qgisMinimumVersion=3.34) — author/email/repo masih placeholder |
| `plugin.py` | lifecycle `initGui`/`unload`, toolbar/menu, toggle dock, signal cleanup |
| `errors.py` | hirarki `SLBError` → `ValidationError`/`ExportError`/`ExportCancelled`/`PresetError` |
| `core/layout.py` | `generate_layout()` — pilih strategi by orientasi + materialize ItemSpec → 6 elemen; `PAPER_MM`; nama unik |
| `core/strategies.py` | `ItemSpec` + fungsi murni `single_column()` (portrait) & `two_column()` (landscape) → `list[ItemSpec]` |
| `ui/dock.py` | `SLBDock` — input judul + tombol Generate; `build_layout()` headless vs `_open_in_designer()` GUI |
| `io/safe_paths.py` | `user_dir`/`ensure_dir`/`atomic_write`/`safe_filename` |
| `utils/logging.py` | `configure_logging()` idempoten ke `<profil>/SLB/logs/slb.log` |
| `resources/north_arrows/` | 5 SVG panah utara (classic/block/compass_only/modern_circle/modern_simple) |
| `resources/icons/slb_logo.svg` | ikon toolbar |
| `core/`, `export/`, `presets/` | sebagian masih paket kosong (diisi Week 2–5) |

---

## Cara test (headless, WAJIB sebelum commit)

- Test dijalankan **live di QGIS via QGIS MCP** (`mcp__qgis__execute_code`), bukan pytest lokal.
- **Project uji:** `banjir.qgz` (Digitasi Banjir Kota Banjarmasin, 9 layer, EPSG:4326) — project kerja riil.
  - ⚠️ Project ini berisi **5 layout produksi user (`Peta_Banjarmasin_*`)** — JANGAN dihapus/ditimpa.
  - ⚠️ `banjir.qgz` punya `title()` kosong → judul kosong jatuh ke "Untitled".
- Pola: inject repo ke `sys.path` → buang cache modul `slb` (fresh import) → jalankan → **cleanup layout uji**.
- **Jangan buka GUI saat headless test** (mis. `iface.openLayoutDesigner()` memblok event loop — pisahkan dari builder).

---

## Environment & aturan workflow (ringkas dari `AGENTS.md`)

- Windows 11 · QGIS Desktop · QGIS MCP aktif · Laragon Git · Git Credential Manager.
- **Workflow:** Implement → Headless test → Commit → Push → Report hash.
- **Jangan commit sebelum headless test PASS.**
- **Push HARUS via PowerShell** (`git push`), bukan Bash git. Commit boleh via Bash.
- Atribusi commit dinonaktifkan global (tanpa trailer `Co-Authored-By`).

---

## TODO / placeholder yang belum dibereskan

- [ ] `slb/metadata.txt`: author/email/repository masih `TODO` → isi sebelum submit Plugin Repo (Day 33).
- [ ] `LICENSE`: perlu teks penuh GPL-3.0 sebelum rilis publik.
- [ ] `AGENTS.md` masih untracked di git (keputusan user: commit atau tidak).
- [ ] Belum ada suite pytest lokal; test masih manual via QGIS MCP.

---

## Cara merawat file ini

Perbarui **di akhir setiap hari kerja**, setelah push:
1. Ganti **Commit terakhir** + baris di tabel "Log singkat per hari".
2. Perbarui **Posisi sekarang** (Day selesai + Next task).
3. Centang progress **Week** bila satu minggu tuntas.
4. Coret/ tambah item di **TODO** bila berubah.
5. Tambah file ke **Peta source** bila ada modul baru.

Tujuan: file ini + 3–5 file yang ditunjuk = konteks cukup untuk lanjut kerja tanpa membaca seluruh repo.
