import os
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QLineEdit, QFileDialog, QGroupBox,
    QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy
)
from qgis.PyQt.QtCore import Qt

try:
    _Checked = Qt.CheckState.Checked      # PyQt6
    _Unchecked = Qt.CheckState.Unchecked
except AttributeError:
    _Checked = Qt.Checked                 # PyQt5
    _Unchecked = Qt.Unchecked

try:
    _ItemIsUserCheckable = Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled  # PyQt6
    _ItemIsEnabled = Qt.ItemFlag.ItemIsEnabled
    _UserRole = Qt.ItemDataRole.UserRole
    _NoSelection = QTableWidget.SelectionMode.NoSelection
    _NoEditTriggers = QTableWidget.EditTrigger.NoEditTriggers
    _ResizeToContents = QHeaderView.ResizeMode.ResizeToContents
    _Stretch = QHeaderView.ResizeMode.Stretch
    _Expanding = QSizePolicy.Policy.Expanding
except AttributeError:
    _ItemIsUserCheckable = Qt.ItemIsUserCheckable | Qt.ItemIsEnabled                    # PyQt5
    _ItemIsEnabled = Qt.ItemIsEnabled
    _UserRole = Qt.UserRole
    _NoSelection = QTableWidget.NoSelection
    _NoEditTriggers = QTableWidget.NoEditTriggers
    _ResizeToContents = QHeaderView.ResizeToContents
    _Stretch = QHeaderView.Stretch
    _Expanding = QSizePolicy.Expanding

from qgis.core import QgsProject, QgsMapLayer, QgsTask, QgsApplication, QgsMessageLog, Qgis, QgsSettings
from .api import export_layers_to_svg_vector

# Keep strong Python references to running tasks so the GC does not collect
# them before finished() is called (the C++ task manager only holds a C++ ref).
_active_tasks = []

_COL_CHECK = 0
_COL_NAME  = 1
_COL_FIELD = 2


class SVGExportTask(QgsTask):
    def __init__(self, layers_fields, output_path, width, iface):
        names = ", ".join(l.name() for l, _ in layers_fields)
        super().__init__(f"SVG Export: {names}", QgsTask.CanCancel)
        self.layers_fields = layers_fields
        self.output_path = output_path
        self.width = width
        self.iface = iface
        self.error = None

    def run(self):
        names = ", ".join(l.name() for l, _ in self.layers_fields)
        QgsMessageLog.logMessage(
            f"Starting export of '{names}' to {self.output_path}",
            "SVG Export", Qgis.Info,
        )
        try:
            export_layers_to_svg_vector(
                layers_fields=self.layers_fields,
                output_path=self.output_path,
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
        names = ", ".join(l.name() for l, _ in self.layers_fields)
        if self.isCanceled():
            QgsMessageLog.logMessage(
                f"Export of '{names}' was cancelled.", "SVG Export", Qgis.Warning,
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
        self.setMinimumWidth(520)
        self._build_ui()

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _load_settings(self):
        s = QgsSettings()
        self.width_spin.setValue(int(s.value("svgexport/width", 1200)))
        # Per-layer field preferences are restored inside _populate_table.

    def _save_settings(self):
        s = QgsSettings()
        s.setValue("svgexport/width", self.width_spin.value())
        checked_names = []
        for row in range(self.layer_table.rowCount()):
            layer = self._layer_at(row)
            combo = self.layer_table.cellWidget(row, _COL_FIELD)
            if not layer:
                continue
            if combo and combo.currentText():
                s.setValue(f"svgexport/id_field/{layer.name()}", combo.currentText())
            if self._is_checked(row):
                checked_names.append(layer.name())
        s.setValue("svgexport/checked_layers", checked_names)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Layer table
        layer_group = QGroupBox("Layers")
        layer_layout = QVBoxLayout(layer_group)

        self.layer_table = QTableWidget(0, 3)
        self.layer_table.setHorizontalHeaderLabels(["", "Layer", "ID Field"])
        self.layer_table.verticalHeader().setVisible(False)
        self.layer_table.setSelectionMode(_NoSelection)
        self.layer_table.setEditTriggers(_NoEditTriggers)
        self.layer_table.setSizePolicy(_Expanding, _Expanding)

        hdr = self.layer_table.horizontalHeader()
        hdr.setSectionResizeMode(_COL_CHECK, _ResizeToContents)
        hdr.setSectionResizeMode(_COL_NAME,  _Stretch)
        hdr.setSectionResizeMode(_COL_FIELD, _ResizeToContents)

        self.layer_table.itemChanged.connect(self._on_check_changed)
        layer_layout.addWidget(self.layer_table)
        layout.addWidget(layer_group)

        # Export options
        options_group = QGroupBox("Options")
        options_layout = QHBoxLayout(options_group)
        options_layout.addWidget(QLabel("Width (px):"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(100, 10000)
        self.width_spin.setValue(1200)
        options_layout.addWidget(self.width_spin)
        options_layout.addStretch()
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

        self._populate_table()
        self._load_settings()

    def _populate_table(self):
        s = QgsSettings()
        checked_names = set(s.value("svgexport/checked_layers", []) or [])
        self.layer_table.setRowCount(0)
        self.layer_table.blockSignals(True)

        ordered_ids = [
            tl.layerId()
            for tl in QgsProject.instance().layerTreeRoot().findLayers()
        ]
        layers_map = QgsProject.instance().mapLayers()

        for layer_id in ordered_ids:
            layer = layers_map.get(layer_id)
            if not layer or layer.type() != QgsMapLayer.VectorLayer:
                continue

            row = self.layer_table.rowCount()
            self.layer_table.insertRow(row)

            # Checkbox column
            check_item = QTableWidgetItem()
            check_item.setFlags(_ItemIsUserCheckable)
            check_item.setCheckState(_Checked if layer.name() in checked_names else _Unchecked)
            check_item.setData(_UserRole, layer_id)
            self.layer_table.setItem(row, _COL_CHECK, check_item)

            # Layer name column
            name_item = QTableWidgetItem(layer.name())
            name_item.setFlags(_ItemIsEnabled)
            self.layer_table.setItem(row, _COL_NAME, name_item)

            # ID field dropdown
            combo = QComboBox()
            combo.setEnabled(layer.name() in checked_names)
            unique_fields = self._unique_fields(layer)
            for fname in unique_fields:
                combo.addItem(fname)
            # Restore last used field for this layer
            last_field = s.value(f"svgexport/id_field/{layer.name()}", "")
            if last_field:
                idx = combo.findText(last_field)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.currentIndexChanged.connect(self._update_export_btn)
            self.layer_table.setCellWidget(row, _COL_FIELD, combo)

        self.layer_table.blockSignals(False)
        self._update_export_btn()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _unique_fields(self, layer):
        count = layer.featureCount()
        result = []
        for field in layer.fields():
            name = field.name()
            values = [f[name] for f in layer.getFeatures()]
            if len(set(values)) == count:
                result.append(name)
        return result

    def _layer_at(self, row):
        item = self.layer_table.item(row, _COL_CHECK)
        if not item:
            return None
        layer_id = item.data(_UserRole)
        return QgsProject.instance().mapLayer(layer_id)

    def _is_checked(self, row):
        item = self.layer_table.item(row, _COL_CHECK)
        return item and item.checkState() == _Checked

    def _checked_layers_fields(self):
        """Return (layer, id_field) pairs in bottom-to-top draw order."""
        result = []
        for row in range(self.layer_table.rowCount()):
            if not self._is_checked(row):
                continue
            layer = self._layer_at(row)
            combo = self.layer_table.cellWidget(row, _COL_FIELD)
            if layer and combo and combo.currentText():
                result.append((layer, combo.currentText()))
        # Table is in top-to-bottom legend order; reverse for draw order.
        return list(reversed(result))

    def _on_check_changed(self, item):
        if item.column() != _COL_CHECK:
            return
        row = item.row()
        checked = item.checkState() == _Checked
        combo = self.layer_table.cellWidget(row, _COL_FIELD)
        if combo:
            combo.setEnabled(checked)
        self._update_export_btn()

    def _update_export_btn(self):
        pairs = self._checked_layers_fields()
        self.export_btn.setEnabled(
            bool(self.output_path.text().strip()) and len(pairs) > 0
        )

    # ------------------------------------------------------------------
    # Browse / Export
    # ------------------------------------------------------------------

    def _browse_output(self):
        pairs = self._checked_layers_fields()
        s = QgsSettings()
        last_dir = s.value("svgexport/last_dir", "")
        if len(pairs) == 1:
            suggestion_name = pairs[0][0].name() + ".svg"
        elif len(pairs) > 1:
            suggestion_name = "export.svg"
        else:
            suggestion_name = ""
        suggestion = os.path.join(last_dir, suggestion_name) if suggestion_name else last_dir
        path, _ = QFileDialog.getSaveFileName(
            self, "Save SVG File", suggestion, "SVG Files (*.svg)"
        )
        if path:
            if not path.lower().endswith(".svg"):
                path += ".svg"
            s.setValue("svgexport/last_dir", os.path.dirname(path))
            self.output_path.setText(path)

    def _export(self):
        output = self.output_path.text().strip()
        layers_fields = self._checked_layers_fields()

        self._save_settings()
        task = SVGExportTask(layers_fields, output, self.width_spin.value(), self.iface)
        _active_tasks.append(task)

        def _cleanup():
            if task in _active_tasks:
                _active_tasks.remove(task)

        task.taskCompleted.connect(_cleanup)
        task.taskTerminated.connect(_cleanup)

        QgsApplication.taskManager().addTask(task)
        self.close()
