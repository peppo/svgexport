"""Test HTML companion generation with gemeinden + point + line layers."""

import json
import os
import re
import sys

import qgis_init  # bootstraps QGIS, starts QgsApplication

from qgis.core import QgsVectorLayer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "svgexport"))

from api import export_layers_to_svg_vector
from html import generate_html_companion

SHP_GEMEINDEN = os.path.join(ROOT, "test_data", "gemeinden.shp")
QML_GEMEINDEN = os.path.join(ROOT, "test_data", "gemeinden_style.qml")
GEOMTYPES = os.path.join(ROOT, "test_data", "geomtypes")
OUT_DIR = os.path.join(HERE, "test_output")
os.makedirs(OUT_DIR, exist_ok=True)

OUT_SVG = os.path.join(OUT_DIR, "test_html_multilayer.svg")
OUT_HTML = os.path.join(OUT_DIR, "test_html_multilayer.html")

# --- Load layers ---
gemeinden = QgsVectorLayer(SHP_GEMEINDEN, "gemeinden", "ogr")
assert gemeinden.isValid(), f"gemeinden failed to load: {SHP_GEMEINDEN}"
msg, ok = gemeinden.loadNamedStyle(QML_GEMEINDEN)
assert ok, f"Failed to load gemeinden style: {msg}"

point_layer = QgsVectorLayer(os.path.join(GEOMTYPES, "point.shp"), "point", "ogr")
assert point_layer.isValid(), "point layer failed to load"

line_layer = QgsVectorLayer(os.path.join(GEOMTYPES, "line.shp"), "line", "ogr")
assert line_layer.isValid(), "line layer failed to load"

layers_fields = [(gemeinden, "ags"), (point_layer, "id"), (line_layer, "id")]

# --- Export SVG ---
export_layers_to_svg_vector(layers_fields=layers_fields, output_path=OUT_SVG, width=1200)
assert os.path.exists(OUT_SVG), "SVG was not created"
print(f"SVG exported: {OUT_SVG}")

# --- Generate HTML companion ---
layers_fields_prefixes = [(layer, field, f"{layer.name()}_") for layer, field in layers_fields]
generate_html_companion(OUT_SVG, OUT_HTML, layers_fields_prefixes, search_layer_idx=0)
assert os.path.exists(OUT_HTML), "HTML was not created"
print(f"HTML generated: {OUT_HTML}")

with open(OUT_HTML, encoding="utf-8") as f:
    html = f.read()

# --- No unreplaced placeholders ---
unreplaced = re.findall(r'__[A-Z_]+__', html)
assert not unreplaced, f"Unreplaced placeholders in HTML: {unreplaced}"
print("No unreplaced placeholders.")

# --- Extract embedded layers JSON ---
m = re.search(r'const layers = (\[.*?\]);', html, re.DOTALL)
assert m, "Could not find 'const layers = ...' in HTML"
embedded_layers = json.loads(m.group(1))
assert len(embedded_layers) == 3, f"Expected 3 layers, got {len(embedded_layers)}"
print(f"Found {len(embedded_layers)} layers in HTML.")

# --- Check each layer's data ---
gemeinden_layer_data = next(l for l in embedded_layers if l["idPrefix"] == "gemeinden_")
assert gemeinden_layer_data["idField"] == "ags"
assert len(gemeinden_layer_data["data"]) == gemeinden.featureCount()
# Spot-check a known AGS value
ags_values = [str(r["ags"]) for r in gemeinden_layer_data["data"]]
assert any(v for v in ags_values), "ags field has no values"
print(f"gemeinden layer: {len(gemeinden_layer_data['data'])} features, first AGS: {ags_values[0]}.")

point_layer_data = next(l for l in embedded_layers if l["idPrefix"] == "point_")
assert point_layer_data["idField"] == "id"
assert len(point_layer_data["data"]) == point_layer.featureCount()
print(f"point layer: {len(point_layer_data['data'])} features.")

line_layer_data = next(l for l in embedded_layers if l["idPrefix"] == "line_")
assert line_layer_data["idField"] == "id"
assert len(line_layer_data["data"]) == line_layer.featureCount()
print(f"line layer: {len(line_layer_data['data'])} features.")

# --- SVG element IDs match data ---
svg_ids = set(re.findall(r'\bid="(gemeinden_[^"]+)"', html))
assert len(svg_ids) == gemeinden.featureCount(), (
    f"SVG gemeinden ID count ({len(svg_ids)}) != feature count ({gemeinden.featureCount()})"
)
print(f"All {len(svg_ids)} gemeinden SVG IDs accounted for.")

# --- searchLayerIdx is correct ---
m2 = re.search(r'const searchLayerIdx = (\d+);', html)
assert m2, "Could not find searchLayerIdx in HTML"
assert int(m2.group(1)) == 0, f"Expected searchLayerIdx=0, got {m2.group(1)}"
print("searchLayerIdx = 0 (gemeinden).")

print("\nAll assertions passed.")
