"""Standalone test: load gemeinden.shp and export it to SVG via the api."""

import os
import sys

import qgis_init  # bootstraps QGIS, starts QgsApplication

from qgis.core import QgsVectorLayer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "svgexport"))

from api import export_layer_to_svg_vector

SHP = os.path.join(ROOT, "test_data", "gemeinden.shp")
OUT_DIR = os.path.join(HERE, "test_output")
os.makedirs(OUT_DIR, exist_ok=True)

layer = QgsVectorLayer(SHP, "gemeinden", "ogr")
assert layer.isValid(), f"Layer failed to load: {SHP}"
print(f"Loaded layer: {layer.name()}, features: {layer.featureCount()}, CRS: {layer.crs().authid()}")

QML = os.path.join(ROOT, "test_data", "gemeinden_style.qml")
msg, ok = layer.loadNamedStyle(QML)
assert ok, f"Failed to load style: {msg}"
print(f"Style loaded: {QML}")

OUT_VECTOR = os.path.join(OUT_DIR, "gemeinden_vector.svg")
export_layer_to_svg_vector(layer, OUT_VECTOR, id_field="ags", width=1200)
assert os.path.exists(OUT_VECTOR), "Vector SVG was not created"
print(f"Vector SVG exported to: {OUT_VECTOR}")

# --- point layer ---
GEOMTYPES = os.path.join(ROOT, "test_data", "geomtypes")

point_layer = QgsVectorLayer(os.path.join(GEOMTYPES, "point.shp"), "point", "ogr")
assert point_layer.isValid(), "Point layer failed to load"
print(f"Loaded point layer: features={point_layer.featureCount()}")

OUT_POINT = os.path.join(OUT_DIR, "point_vector.svg")
export_layer_to_svg_vector(point_layer, OUT_POINT, id_field="id", width=800)
assert os.path.exists(OUT_POINT), "Point SVG was not created"
with open(OUT_POINT) as f:
    content = f.read()
assert "<circle" in content, "Point SVG should contain <circle> elements"
print(f"Point SVG exported to: {OUT_POINT}")

# --- line layer ---
line_layer = QgsVectorLayer(os.path.join(GEOMTYPES, "line.shp"), "line", "ogr")
assert line_layer.isValid(), "Line layer failed to load"
print(f"Loaded line layer: features={line_layer.featureCount()}")

OUT_LINE = os.path.join(OUT_DIR, "line_vector.svg")
export_layer_to_svg_vector(line_layer, OUT_LINE, id_field="id", width=800)
assert os.path.exists(OUT_LINE), "Line SVG was not created"
with open(OUT_LINE) as f:
    content = f.read()
assert 'fill:none' in content, "Line SVG paths should have fill:none"
print(f"Line SVG exported to: {OUT_LINE}")

# --- multi-layer extent test ---
import re
from api import export_layers_to_svg_vector

gemeinden_layer = QgsVectorLayer(SHP, "gemeinden2", "ogr")
assert gemeinden_layer.isValid(), "gemeinden layer (multi-test) failed to load"

point_layer2 = QgsVectorLayer(os.path.join(ROOT, "test_data", "geomtypes", "point.shp"), "point2", "ogr")
assert point_layer2.isValid(), "point layer (multi-test) failed to load"

OUT_MULTI = os.path.join(OUT_DIR, "multi_layer.svg")
export_layers_to_svg_vector(
    layers_fields=[(gemeinden_layer, "ags"), (point_layer2, "id")],
    output_path=OUT_MULTI,
    width=1200,
)
assert os.path.exists(OUT_MULTI), "Multi-layer SVG was not created"

with open(OUT_MULTI) as f:
    svg_content = f.read()

# Extract horizontal (x) coordinates only:
#   - cx="..." on <circle> elements
#   - first number after M or L in path d attributes (x comes before y)
x_coords = [float(v) for v in re.findall(r'(?:cx|[ML])\s+([\d.]+)', svg_content)]
assert any(x < 600 for x in x_coords), (
    f"Expected at least one x-coordinate < 600 but got min={min(x_coords):.1f}. "
    "The map extent is probably wrong (too large), making everything tiny."
)
print(f"Multi-layer SVG: {len(x_coords)} x-coords found, min={min(x_coords):.1f} — extent OK")
