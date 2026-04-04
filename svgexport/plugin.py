import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProject


class SVGExportPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        self.dialog = None

    def initGui(self):
        icon = QIcon(os.path.join(self.plugin_dir, "icon.png"))
        self.action = QAction(icon, "Export to SVG", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.action.setEnabled(True)

        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("SVG Export", self.action)

    def unload(self):
        self.iface.removePluginMenu("SVG Export", self.action)
        self.iface.removeToolBarIcon(self.action)
        del self.action

    def run(self):
        if self.dialog is None:
            from .dialog import SVGExportDialog
            self.dialog = SVGExportDialog(self.iface)

        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
