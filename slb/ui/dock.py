"""SLBDock — panel dock utama.

Day 5: placeholder. Week 1-5 akan mengisi tab Compose & Atlas.
Widget tipis: hanya UI + sinyal; logika ada di core/ export/ presets/.
"""

from __future__ import annotations

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QLabel, QVBoxLayout, QWidget

from qgis.PyQt.QtWidgets import QDockWidget

from ..version import __version__


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

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addStretch(1)
        self.setWidget(container)
