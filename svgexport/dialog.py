import os
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QLineEdit, QFileDialog, QMessageBox, QGroupBox,
    QSpinBox, QCheckBox
)
from qgis.core import QgsProject, QgsMapLayer
from .api import export_layer_to_svg_vector


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
        layer_layout.addWidget(QLabel("Select vector layer to export:"))
        layer_layout.addWidget(self.layer_combo)

        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("ID field:"))
        self.id_field_combo = QComboBox()
        id_layout.addWidget(self.id_field_combo)
        layer_layout.addLayout(id_layout)

        self._populate_layers()
        self.layer_combo.currentIndexChanged.connect(self._on_layer_changed)
        layout.addWidget(layer_group)

        # Export options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel("Width (px):"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(100, 10000)
        self.width_spin.setValue(1200)
        width_layout.addWidget(self.width_spin)
        options_layout.addLayout(width_layout)

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
        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() == QgsMapLayer.VectorLayer:
                self.layer_combo.addItem(layer.name(), layer.id())
        self._refresh_id_fields()

    def _on_layer_changed(self):
        self._refresh_id_fields()

    def _refresh_id_fields(self):
        self.id_field_combo.clear()
        layer = self._current_layer()
        if layer is None:
            return
        for field in layer.fields():
            self.id_field_combo.addItem(field.name())

    def _current_layer(self):
        layer_id = self.layer_combo.currentData()
        if not layer_id:
            return None
        return QgsProject.instance().mapLayer(layer_id)

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

        layer = self._current_layer()
        if layer is None:
            QMessageBox.warning(self, "No Layer", "Please select a vector layer.")
            return

        id_field = self.id_field_combo.currentText()
        if not id_field:
            QMessageBox.warning(self, "No ID Field", "Please select an ID field.")
            return

        canvas = self.iface.mapCanvas()
        extent = canvas.extent() if self.use_canvas_extent.isChecked() else None
        crs = canvas.mapSettings().destinationCrs()

        export_layer_to_svg_vector(
            layer=layer,
            output_path=output,
            id_field=id_field,
            width=self.width_spin.value(),
            extent=extent,
            crs=crs,
        )

        QMessageBox.information(self, "Export Complete", f"SVG exported to:\n{output}")
