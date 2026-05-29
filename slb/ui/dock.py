"""SLBDock — panel dock utama.

Day 8: tombol "Generate Layout" end-to-end (judul opsional → layout → Designer).
Widget tipis: hanya UI + sinyal; logika ada di core/ export/ presets/.
"""

from __future__ import annotations

import logging

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QLabel,
    QLineEdit,
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
            "Buat layout (peta A4 + judul, legend, skala, panah utara) dari "
            "extent kanvas aktif, lalu buka di Layout Designer."
        )
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Judul peta (kosong = judul project)")
        self._title_edit.setClearButtonEnabled(True)

        self._btn_generate = QPushButton("Generate Layout")
        self._btn_generate.setToolTip("Buat layout dari extent kanvas aktif lalu buka di Designer")
        self._btn_generate.clicked.connect(self._on_generate)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("color: gray;")

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(QLabel("Judul"))
        layout.addWidget(self._title_edit)
        layout.addWidget(self._btn_generate)
        layout.addWidget(self._status)
        layout.addStretch(1)
        self.setWidget(container)

    def build_layout(self, title: str | None = None):
        """Headless: buat & kembalikan layout dari extent kanvas. TANPA GUI.

        Dipisah dari pembukaan Designer agar bisa diuji tanpa memblok event loop.
        `title` kosong/None → generate_layout memakai judul project atau "Untitled".
        """
        from qgis.core import QgsProject

        from ..core.layout import generate_layout

        extent = self.iface.mapCanvas().extent()
        return generate_layout(
            QgsProject.instance(),
            paper="A4",
            orientation="portrait",
            title=title or None,
            extent=extent,
        )

    def _open_in_designer(self, layout):
        """Buka layout di Layout Designer (GUI). Terpisah agar bisa di-skip saat test."""
        self.iface.openLayoutDesigner(layout)

    def _on_generate(self):
        """Handler tombol (jalur user): buat layout lalu buka di Designer."""
        try:
            layout = self.build_layout(self._title_edit.text().strip())
            self._open_in_designer(layout)
            self._status.setText(f"Layout “{layout.name()}” dibuka di Designer.")
            log.info("layout dibuat: %s", layout.name())
        except SLBError as e:
            self._status.setText("")
            QMessageBox.warning(
                self, "Smart Layout Builder",
                f"{e}\n\n{e.hint}" if e.hint else str(e),
            )
        except Exception:  # noqa: BLE001
            self._status.setText("")
            log.exception("gagal generate layout")
            QMessageBox.critical(
                self, "Smart Layout Builder",
                "Terjadi kesalahan tak terduga. Lihat log di folder profil QGIS/SLB/logs.",
            )
