import os
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QLineEdit, QFileDialog, QMessageBox, QGroupBox,
    QSpinBox
)
from qgis.core import QgsProject, QgsMapLayer, QgsTask, QgsApplication, QgsMessageLog, Qgis, QgsSettings
from .api import export_layer_to_svg_vector

# Keep strong Python references to running tasks so the GC does not collect
# them before finished() is called (the C++ task manager only holds a C++ ref).
_active_tasks = []


class SVGExportTask(QgsTask):
    def __init__(self, layer, output_path, id_field, width, iface):
        super().__init__(f"SVG Export: {layer.name()}", QgsTask.CanCancel)
        self.layer = layer
        self.output_path = output_path
        self.id_field = id_field
        self.width = width
        self.iface = iface
        self.error = None

    def run(self):
        QgsMessageLog.logMessage(
            f"Starting export of '{self.layer.name()}' to {self.output_path}",
            "SVG Export", Qgis.Info,
        )
        try:
            export_layer_to_svg_vector(
                layer=self.layer,
                output_path=self.output_path,
                id_field=self.id_field,
                width=self.width,
                progress_callback=self.setProgress,
                should_stop=self.isCanceled,
            )
        except Exception as e:
            self.error = str(e)
            QgsMessageLog.logMessage(
                f"Export failed: {self.error}", "SVG Export", Qgis.Critical,
            )
            return False
        return not self.isCanceled()

    def finished(self, result):
        if self.isCanceled():
            QgsMessageLog.logMessage(
                f"Export of '{self.layer.name()}' was cancelled.", "SVG Export", Qgis.Warning,
            )
            return
        if result:
            QgsMessageLog.logMessage(
                f"Export complete: {self.output_path}", "SVG Export", Qgis.Success,
            )
            self.iface.messageBar().pushSuccess(
                "SVG Export", f"Exported to: {self.output_path}"
            )
        else:
            self.iface.messageBar().pushCritical(
                "SVG Export", self.error or "Export failed."
            )


class SVGExportDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self.setWindowTitle("Export to SVG")
        self.setMinimumWidth(420)
        self._build_ui()

    def _settings(self):
        return QgsSettings()

    def _load_settings(self):
        s = self._settings()
        self.width_spin.setValue(int(s.value("svgexport/width", 1200)))
        last_field = s.value("svgexport/id_field", "")
        if last_field:
            idx = self.id_field_combo.findText(last_field)
            if idx >= 0:
                self.id_field_combo.setCurrentIndex(idx)

    def _save_settings(self):
        s = self._settings()
        s.setValue("svgexport/width", self.width_spin.value())
        s.setValue("svgexport/id_field", self.id_field_combo.currentText())

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
        self.export_btn = QPushButton("Export")
        self.export_btn.clicked.connect(self._export)
        self.export_btn.setDefault(True)
        self.export_btn.setEnabled(False)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addStretch()
        btn_layout.addWidget(self.export_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.output_path.textChanged.connect(self._update_export_btn)
        self.id_field_combo.currentIndexChanged.connect(self._update_export_btn)

        self._load_settings()

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
        feature_count = layer.featureCount()
        for field in layer.fields():
            name = field.name()
            values = [f[name] for f in layer.getFeatures()]
            if len(set(values)) == feature_count:
                self.id_field_combo.addItem(name)

    def _current_layer(self):
        layer_id = self.layer_combo.currentData()
        if not layer_id:
            return None
        return QgsProject.instance().mapLayer(layer_id)

    def _update_export_btn(self):
        self.export_btn.setEnabled(
            bool(self.output_path.text().strip()) and self.id_field_combo.count() > 0
        )

    def _browse_output(self):
        layer = self._current_layer()
        settings = QgsSettings()
        last_dir = settings.value("svgexport/last_dir", "")
        layer_name = layer.name() if layer else ""
        suggestion = os.path.join(last_dir, layer_name + ".svg") if layer_name else last_dir
        path, _ = QFileDialog.getSaveFileName(
            self, "Save SVG File", suggestion, "SVG Files (*.svg)"
        )
        if path:
            if not path.lower().endswith(".svg"):
                path += ".svg"
            settings.setValue("svgexport/last_dir", os.path.dirname(path))
            self.output_path.setText(path)

    def _export(self):
        output = self.output_path.text().strip()
        layer = self._current_layer()
        id_field = self.id_field_combo.currentText()

        self._save_settings()
        task = SVGExportTask(layer, output, id_field, self.width_spin.value(), self.iface)
        _active_tasks.append(task)

        def _cleanup():
            if task in _active_tasks:
                _active_tasks.remove(task)

        task.taskCompleted.connect(_cleanup)
        task.taskTerminated.connect(_cleanup)

        QgsApplication.taskManager().addTask(task)
        self.close()
