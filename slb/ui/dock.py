"""SLBDock — panel dock utama.

Day 8: tombol "Generate Layout" end-to-end (judul opsional → layout → Designer).
Day 10: selector kertas (A4/A3/Letter) + orientasi (portrait/landscape); pilihan
diteruskan ke ``generate_layout`` yang me-routing ke strategi yang sesuai.
Widget tipis: hanya UI + sinyal; logika ada di core/ export/ presets/.
"""

from __future__ import annotations

import logging

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHBoxLayout,
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
            "Buat layout (peta + judul, legend, skala, panah utara) dari "
            "extent kanvas aktif, lalu buka di Layout Designer."
        )
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Judul peta (kosong = judul project)")
        self._title_edit.setClearButtonEnabled(True)

        # Selector kertas: teks combo = key yang dipakai core (PAPER_MM).
        self._paper_combo = QComboBox()
        self._paper_combo.addItems(["A4", "A3", "Letter"])
        self._paper_combo.setToolTip("Ukuran kertas layout")

        # Selector orientasi: teks Indonesia, data = key core (portrait/landscape).
        self._orientation_combo = QComboBox()
        self._orientation_combo.addItem("Potret", "portrait")
        self._orientation_combo.addItem("Lanskap", "landscape")
        self._orientation_combo.setToolTip(
            "Potret → satu kolom; Lanskap → peta kiri + sidebar"
        )

        self._btn_generate = QPushButton("Generate Layout")
        self._btn_generate.setToolTip("Buat layout dari extent kanvas aktif lalu buka di Designer")
        self._btn_generate.clicked.connect(self._on_generate)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("color: gray;")

        selectors = QHBoxLayout()
        paper_col = QVBoxLayout()
        paper_col.addWidget(QLabel("Kertas"))
        paper_col.addWidget(self._paper_combo)
        orient_col = QVBoxLayout()
        orient_col.addWidget(QLabel("Orientasi"))
        orient_col.addWidget(self._orientation_combo)
        selectors.addLayout(paper_col)
        selectors.addLayout(orient_col)

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(QLabel("Judul"))
        layout.addWidget(self._title_edit)
        layout.addLayout(selectors)
        layout.addWidget(self._btn_generate)
        layout.addWidget(self._status)
        layout.addStretch(1)
        self.setWidget(container)

    def build_layout(
        self,
        title: str | None = None,
        paper: str | None = None,
        orientation: str | None = None,
    ):
        """Headless: buat & kembalikan layout dari extent kanvas. TANPA GUI.

        Dipisah dari pembukaan Designer agar bisa diuji tanpa memblok event loop.
        `title` kosong/None → generate_layout memakai judul project atau "Untitled".
        `paper`/`orientation` None → diambil dari selector dock (override untuk test).
        """
        from qgis.core import QgsProject

        from ..core.layout import generate_layout

        extent = self.iface.mapCanvas().extent()
        return generate_layout(
            QgsProject.instance(),
            paper=paper or self._paper_combo.currentText(),
            orientation=orientation or self._orientation_combo.currentData(),
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
