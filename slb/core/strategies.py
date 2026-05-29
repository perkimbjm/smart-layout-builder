"""core/strategies — penempatan item layout (Day 9).

Dua strategi murni (pure functions), bukan kelas. Masing-masing menerima
dimensi kertas (mm) + margin dan mengembalikan daftar ``ItemSpec`` berisi
peran & posisi. ``generate_layout`` memilih strategi berdasarkan orientasi
lalu me-materialize tiap spec menjadi item QGIS.

Mengikuti architecture.md §10 & api-design.md §5: tanpa solver, tanpa
hirarki kelas, tanpa registry (P7 — abstraksi baru hanya bila ada 2+ kasus
nyata; di sini cukup dua fungsi).
"""

from __future__ import annotations

from typing import TypedDict


class ItemSpec(TypedDict, total=False):
    """Penempatan satu item layout dalam milimeter."""

    role: str  # "title"|"map"|"legend"|"scale_bar"|"north_arrow"|"attribution"
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float


# Geometri bersama (mm). Dimiliki oleh strategi karena merekalah yang
# menentukan tata letak; layout.py hanya me-materialize.
MARGIN_MM = 10.0
TITLE_H_MM = 12.0
ATTRIB_H_MM = 5.0
GAP_MM = 4.0
NORTH_SIZE_MM = 20.0
SCALE_H_MM = 10.0

_FOOTER_H_MM = 42.0  # tinggi zona footer (legend/scale/north) pada single_column
_SIDEBAR_FRAC = 0.30  # lebar sidebar two_column sebagai fraksi area pakai
_LEGEND_FRAC = 0.55  # porsi tinggi sidebar two_column untuk legend


def single_column(
    paper_w_mm: float, paper_h_mm: float, margin_mm: float = MARGIN_MM
) -> list[ItemSpec]:
    """Portrait: judul, peta lebar penuh, lalu footer (legend|scale|north).

    Mereproduksi tata letak portrait Day 8 agar tidak ada regresi.
    """
    usable_w = paper_w_mm - 2 * margin_mm
    attrib_y = paper_h_mm - margin_mm - ATTRIB_H_MM
    footer_top = attrib_y - _FOOTER_H_MM
    map_top = margin_mm + TITLE_H_MM + GAP_MM
    map_h = footer_top - map_top - 2.0
    return [
        {
            "role": "title",
            "x_mm": margin_mm,
            "y_mm": margin_mm,
            "w_mm": usable_w,
            "h_mm": TITLE_H_MM,
        },
        {
            "role": "map",
            "x_mm": margin_mm,
            "y_mm": map_top,
            "w_mm": usable_w,
            "h_mm": map_h,
        },
        {
            "role": "legend",
            "x_mm": margin_mm,
            "y_mm": footer_top,
            "w_mm": paper_w_mm * 0.42,
            "h_mm": _FOOTER_H_MM,
        },
        {
            "role": "scale_bar",
            "x_mm": paper_w_mm * 0.5,
            "y_mm": footer_top + 6.0,
            "w_mm": paper_w_mm * 0.3,
            "h_mm": SCALE_H_MM,
        },
        {
            "role": "north_arrow",
            "x_mm": paper_w_mm - margin_mm - NORTH_SIZE_MM,
            "y_mm": footer_top + 4.0,
            "w_mm": NORTH_SIZE_MM,
            "h_mm": NORTH_SIZE_MM,
        },
        {
            "role": "attribution",
            "x_mm": margin_mm,
            "y_mm": attrib_y,
            "w_mm": usable_w,
            "h_mm": ATTRIB_H_MM,
        },
    ]


def two_column(
    paper_w_mm: float, paper_h_mm: float, margin_mm: float = MARGIN_MM
) -> list[ItemSpec]:
    """Landscape: judul lebar penuh, peta kiri ~2/3, sidebar kanan.

    Sidebar berisi legend di atas, lalu scale bar dan north arrow di bawah.
    """
    usable_w = paper_w_mm - 2 * margin_mm
    attrib_y = paper_h_mm - margin_mm - ATTRIB_H_MM
    content_top = margin_mm + TITLE_H_MM + GAP_MM
    content_bottom = attrib_y - GAP_MM
    content_h = content_bottom - content_top
    sidebar_w = usable_w * _SIDEBAR_FRAC
    map_w = usable_w - sidebar_w - GAP_MM
    sidebar_x = margin_mm + map_w + GAP_MM
    legend_h = content_h * _LEGEND_FRAC
    scale_y = content_top + legend_h + GAP_MM
    return [
        {
            "role": "title",
            "x_mm": margin_mm,
            "y_mm": margin_mm,
            "w_mm": usable_w,
            "h_mm": TITLE_H_MM,
        },
        {
            "role": "map",
            "x_mm": margin_mm,
            "y_mm": content_top,
            "w_mm": map_w,
            "h_mm": content_h,
        },
        {
            "role": "legend",
            "x_mm": sidebar_x,
            "y_mm": content_top,
            "w_mm": sidebar_w,
            "h_mm": legend_h,
        },
        {
            "role": "scale_bar",
            "x_mm": sidebar_x,
            "y_mm": scale_y,
            "w_mm": sidebar_w,
            "h_mm": SCALE_H_MM,
        },
        {
            "role": "north_arrow",
            "x_mm": sidebar_x + sidebar_w - NORTH_SIZE_MM,
            "y_mm": content_bottom - NORTH_SIZE_MM,
            "w_mm": NORTH_SIZE_MM,
            "h_mm": NORTH_SIZE_MM,
        },
        {
            "role": "attribution",
            "x_mm": margin_mm,
            "y_mm": attrib_y,
            "w_mm": usable_w,
            "h_mm": ATTRIB_H_MM,
        },
    ]
