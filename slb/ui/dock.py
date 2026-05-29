"""SLBDock — panel dock utama.

Day 5: placeholder. Week 1-5 akan mengisi tab Compose & Atlas.
Widget tipis: hanya UI + sinyal; logika ada di core/ export/ presets/.
"""

from __future__ import annotations

import logging

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..errors import SLBError
from ..version import __version__

log = logging.getLogger("slb.ui.dock")


class SLBDock(QDockWidget):
    """Dock panel Smart Layout Builder."""

    def __init__(self, iface, parent=None):
        super().__init__("Smart Layout Builder", parent)
        self.iface = iface
        # objectName WAJIB agar QGIS bisa simpan/restore state dock tanpa warning
        self.setObjectName("SmartLayoutBuilderDock")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Smart Layout Builder")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")

        body = QLabel(
            f"Versi {__version__}\n\n"
            "Tab Compose (Auto Layout + Smart Legend) dan Atlas Export "
            "akan ditambahkan pada Week 1-5."
        )
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._btn_generate = QPushButton("Generate Layout (debug)")
        self._btn_generate.setToolTip("Buat layout (map + judul) dari extent kanvas aktif")
        self._btn_generate.clicked.connect(self._on_generate_debug)

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(self._btn_generate)
        layout.addStretch(1)
        self.setWidget(container)

    def build_debug_layout(self):
        """Headless: buat & kembalikan layout dari extent kanvas. TANPA GUI.

        Dipisah dari pembukaan Designer agar bisa diuji tanpa memblok event loop.
        """
        from qgis.core import QgsProject

        from ..core.layout import generate_layout

        extent = self.iface.mapCanvas().extent()
        return generate_layout(
            QgsProject.instance(), paper="A4", orientation="portrait", extent=extent
        )

    def _open_in_designer(self, layout):
        """Buka layout di Layout Designer (GUI). Terpisah agar bisa di-skip saat test."""
        self.iface.openLayoutDesigner(layout)

    def _on_generate_debug(self):
        """Handler tombol (jalur user): buat layout lalu buka di Designer."""
        try:
            layout = self.build_debug_layout()
            self._open_in_designer(layout)
            log.info("layout dibuat: %s", layout.name())
        except SLBError as e:
            QMessageBox.warning(
                self, "Smart Layout Builder",
                f"{e}\n\n{e.hint}" if e.hint else str(e),
            )
        except Exception:  # noqa: BLE001
            log.exception("gagal generate layout")
            QMessageBox.critical(
                self, "Smart Layout Builder",
                "Terjadi kesalahan tak terduga. Lihat log di folder profil QGIS/SLB/logs.",
            )
