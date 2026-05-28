"""Smart Layout Builder — QGIS plugin entry point.

QGIS memanggil classFactory(iface) saat plugin di-load. Jaga modul ini
tetap minimal: jangan import berat di top-level (lihat coding-standards §4).
"""

from __future__ import annotations


def classFactory(iface):  # noqa: N802 (nama wajib dari QGIS)
    """Dipanggil QGIS dengan objek iface. Kembalikan instance plugin."""
    from .plugin import SmartLayoutBuilder

    return SmartLayoutBuilder(iface)
