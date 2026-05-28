"""SmartLayoutBuilder — siklus hidup plugin (initGui / unload).

Hanya orkestrasi UI + wiring sinyal. Tidak ada logika bisnis di sini.
Lihat api-design.md §13 dan coding-standards.md §13 (signal cleanup).
"""

from __future__ import annotations

import logging
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .utils.logging import configure_logging

MENU_NAME = "Smart Layout Builder"
_ICON = os.path.join(os.path.dirname(__file__), "resources", "icons", "slb_logo.svg")

log = logging.getLogger("slb.plugin")


class SmartLayoutBuilder:
    """Plugin lifecycle. initGui() ringan (< 200 ms): hanya daftar aksi."""

    def __init__(self, iface):
        self.iface = iface
        self._actions: list[QAction] = []
        self._connections: list[tuple] = []   # (signal, slot) untuk cleanup
        self._dock = None

    # -- lifecycle ---------------------------------------------------------
    def initGui(self):  # noqa: N802 (nama wajib dari QGIS)
        configure_logging()
        action = QAction(QIcon(_ICON), MENU_NAME, self.iface.mainWindow())
        action.setToolTip("Tampilkan/sembunyikan panel Smart Layout Builder")
        action.setCheckable(True)
        self._connect(action.triggered, self._toggle_dock)
        self.iface.addToolBarIcon(action)
        self.iface.addPluginToMenu(MENU_NAME, action)
        self._actions.append(action)
        self._toggle_action = action
        log.info("initGui selesai")

    def unload(self):
        for signal, slot in self._connections:
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
        self._connections.clear()

        for action in self._actions:
            self.iface.removePluginMenu(MENU_NAME, action)
            self.iface.removeToolBarIcon(action)
        self._actions.clear()

        if self._dock is not None:
            self.iface.removeDockWidget(self._dock)
            self._dock.setParent(None)   # lepas dari mainWindow seketika
            self._dock.deleteLater()
            self._dock = None

    # -- actions -----------------------------------------------------------
    def _toggle_dock(self, checked: bool = False):
        """Tampilkan/sembunyikan dock. Dibuat lazy saat pertama dipakai."""
        if self._dock is None:
            from .ui.dock import SLBDock

            self._dock = SLBDock(self.iface, self.iface.mainWindow())
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self._dock)
            self._connect(self._dock.visibilityChanged, self._sync_action)
            log.info("dock dibuat")
        self._dock.setVisible(checked)

    def _sync_action(self, visible: bool):
        """Sinkronkan status toggle aksi dengan visibilitas dock."""
        if self._actions:
            self._actions[0].setChecked(visible)

    # -- helpers -----------------------------------------------------------
    def _connect(self, signal, slot):
        """Connect + catat untuk dibersihkan di unload()."""
        signal.connect(slot)
        self._connections.append((signal, slot))
