import os
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QPushButton, QLineEdit, QFileDialog, QGroupBox,
    QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy, QCheckBox
)
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices

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
    def __init__(self, layers_fields, output_path, width, iface,
                 create_html=False, search_layer=None, search_field=None):
        names = ", ".join(l.name() for l, _ in layers_fields)
        super().__init__(f"SVG Export: {names}", QgsTask.CanCancel)
        self.layers_fields = layers_fields
        self.output_path = output_path
        self.width = width
        self.iface = iface
        self.create_html = create_html
        self.search_layer = search_layer
        self.search_field = search_field
        self.html_path = None
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
            if self.create_html and not self.isCanceled():
                from .html import generate_html_companion
                multi = len(self.layers_fields) > 1
                layers_fields_prefixes = [
                    (layer, field, f"{layer.name()}_" if multi else "")
                    for layer, field in self.layers_fields
                ]
                # Determine search layer index (explicit choice or last layer)
                search_layer = self.search_layer or self.layers_fields[-1][0]
                search_layer_idx = next(
                    (i for i, (l, _f, _p) in enumerate(layers_fields_prefixes) if l is search_layer),
                    len(layers_fields_prefixes) - 1,
                )
                self.html_path = os.path.splitext(self.output_path)[0] + ".html"
                generate_html_companion(
                    self.output_path, self.html_path,
                    layers_fields_prefixes, search_layer_idx,
                    search_field=self.search_field,
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
            if self.html_path:
                QDesktopServices.openUrl(QUrl.fromLocalFile(self.html_path))
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
        self.html_check.setChecked(s.value("svgexport/create_html", False, type=bool))
        self._on_html_check_changed()
        # Per-layer field preferences are restored inside _populate_table.
        # search_layer/field combos are pre-populated in _populate_search_layer_combo.

    def _save_settings(self):
        s = QgsSettings()
        s.setValue("svgexport/width", self.width_spin.value())
        s.setValue("svgexport/create_html", self.html_check.isChecked())
        s.setValue("svgexport/search_layer", self.search_layer_combo.currentText())
        s.setValue(f"svgexport/search_field/{self.search_layer_combo.currentText()}",
                   self.search_field_combo.currentText())
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
        options_layout = QFormLayout(options_group)

        width_row = QHBoxLayout()
        self.width_spin = QSpinBox()
        self.width_spin.setRange(100, 10000)
        self.width_spin.setValue(1200)
        width_row.addWidget(self.width_spin)
        width_row.addStretch()
        options_layout.addRow("Width (px):", width_row)

        self.html_check = QCheckBox("Create inspirational HTML")
        options_layout.addRow("", self.html_check)

        search_layer_row = QHBoxLayout()
        self.search_layer_combo = QComboBox()
        self.search_layer_combo.setEnabled(False)
        search_layer_row.addWidget(self.search_layer_combo)
        search_layer_row.addStretch()
        options_layout.addRow("Search layer:", search_layer_row)

        search_field_row = QHBoxLayout()
        self.search_field_combo = QComboBox()
        self.search_field_combo.setEnabled(False)
        search_field_row.addWidget(self.search_field_combo)
        search_field_row.addStretch()
        options_layout.addRow("Search field:", search_field_row)

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
        self.html_check.stateChanged.connect(self._on_html_check_changed)
        self.search_layer_combo.currentIndexChanged.connect(self._on_search_layer_changed)

        self._populate_table()
        self._populate_search_layer_combo()
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

    def _populate_search_layer_combo(self):
        s = QgsSettings()
        saved_layer = s.value("svgexport/search_layer", "")
        self.search_layer_combo.blockSignals(True)
        self.search_layer_combo.clear()
        for layer, _ in self._checked_layers_fields():
            self.search_layer_combo.addItem(layer.name(), layer.id())
        # Restore saved selection
        idx = self.search_layer_combo.findText(saved_layer)
        if idx >= 0:
            self.search_layer_combo.setCurrentIndex(idx)
        self.search_layer_combo.blockSignals(False)
        self._populate_search_field_combo()

    def _populate_search_field_combo(self):
        s = QgsSettings()
        layer_name = self.search_layer_combo.currentText()
        saved_field = s.value(f"svgexport/search_field/{layer_name}", "")
        self.search_field_combo.blockSignals(True)
        self.search_field_combo.clear()
        layer_id = self.search_layer_combo.currentData()
        if layer_id:
            layer = QgsProject.instance().mapLayer(layer_id)
            if layer:
                for field in layer.fields():
                    self.search_field_combo.addItem(field.name())
        idx = self.search_field_combo.findText(saved_field)
        if idx >= 0:
            self.search_field_combo.setCurrentIndex(idx)
        self.search_field_combo.blockSignals(False)

    def _on_html_check_changed(self):
        enabled = self.html_check.isChecked()
        self.search_layer_combo.setEnabled(enabled)
        self.search_field_combo.setEnabled(enabled)

    def _on_search_layer_changed(self):
        self._populate_search_field_combo()

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
        self._populate_search_layer_combo()
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

        search_layer = None
        search_field = None
        if self.html_check.isChecked():
            layer_id = self.search_layer_combo.currentData()
            search_layer = QgsProject.instance().mapLayer(layer_id) if layer_id else None
            search_field = self.search_field_combo.currentText() or None

        self._save_settings()
        task = SVGExportTask(layers_fields, output, self.width_spin.value(), self.iface,
                             create_html=self.html_check.isChecked(),
                             search_layer=search_layer, search_field=search_field)
        _active_tasks.append(task)

        def _cleanup():
            if task in _active_tasks:
                _active_tasks.remove(task)

        task.taskCompleted.connect(_cleanup)
        task.taskTerminated.connect(_cleanup)

        QgsApplication.taskManager().addTask(task)
        self.close()
