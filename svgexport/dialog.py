import os
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QLineEdit, QFileDialog, QMessageBox, QGroupBox,
    QDoubleSpinBox, QCheckBox
)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProject, QgsMapLayer
from .api import export_layer_to_svg


class SVGExportDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self.setWindowTitle("Export to SVG")
        self.setMinimumWidth(420)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Layer selection
        layer_group = QGroupBox("Layer")
        layer_layout = QVBoxLayout(layer_group)
        self.layer_combo = QComboBox()
        self._populate_layers()
        layer_layout.addWidget(QLabel("Select layer to export:"))
        layer_layout.addWidget(self.layer_combo)
        layout.addWidget(layer_group)

        # Export options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel("Width (px):"))
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(100, 10000)
        self.width_spin.setValue(800)
        self.width_spin.setDecimals(0)
        width_layout.addWidget(self.width_spin)
        options_layout.addLayout(width_layout)

        height_layout = QHBoxLayout()
        height_layout.addWidget(QLabel("Height (px):"))
        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(100, 10000)
        self.height_spin.setValue(600)
        self.height_spin.setDecimals(0)
        height_layout.addWidget(self.height_spin)
        options_layout.addLayout(height_layout)

        self.use_canvas_extent = QCheckBox("Use current map canvas extent")
        self.use_canvas_extent.setChecked(True)
        options_layout.addWidget(self.use_canvas_extent)

        layout.addWidget(options_group)

        # Output path
        output_group = QGroupBox("Output")
        output_layout = QHBoxLayout(output_group)
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Select output SVG file...")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_output)
        output_layout.addWidget(self.output_path)
        output_layout.addWidget(browse_btn)
        layout.addWidget(output_group)

        # Buttons
        btn_layout = QHBoxLayout()
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._export)
        export_btn.setDefault(True)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addStretch()
        btn_layout.addWidget(export_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _populate_layers(self):
        self.layer_combo.clear()
        self.layer_combo.addItem("-- All visible layers --", None)
        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() in (QgsMapLayer.VectorLayer, QgsMapLayer.RasterLayer):
                self.layer_combo.addItem(layer.name(), layer.id())

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save SVG File", "", "SVG Files (*.svg)"
        )
        if path:
            if not path.lower().endswith(".svg"):
                path += ".svg"
            self.output_path.setText(path)

    def _export(self):
        output = self.output_path.text().strip()
        if not output:
            QMessageBox.warning(self, "Missing Output", "Please select an output file path.")
            return

        width = int(self.width_spin.value())
        height = int(self.height_spin.value())

        canvas = self.iface.mapCanvas()
        layer_id = self.layer_combo.currentData()

        if layer_id:
            layer = QgsProject.instance().mapLayer(layer_id)
            extent = canvas.extent() if self.use_canvas_extent.isChecked() else layer.extent()
            crs = canvas.mapSettings().destinationCrs()
        else:
            layer = None
            extent = canvas.extent()
            crs = canvas.mapSettings().destinationCrs()

        export_layer_to_svg(
            layer=layer,
            output_path=output,
            width=width,
            height=height,
            extent=extent,
            crs=crs,
            background_color=canvas.canvasColor(),
        )

        QMessageBox.information(self, "Export Complete", f"SVG exported to:\n{output}")
