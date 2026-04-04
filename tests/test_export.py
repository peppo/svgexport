"""Standalone test: load gemeinden.shp and export it to SVG via the api."""

import os
import sys

import qgis_init  # bootstraps QGIS, starts QgsApplication

from qgis.core import QgsVectorLayer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "svgexport"))

from api import export_layer_to_svg, export_layer_to_svg_vector

SHP = os.path.join(HERE, "test_data", "gemeinden.shp")
OUT_DIR = os.path.join(HERE, "test_output")
os.makedirs(OUT_DIR, exist_ok=True)

layer = QgsVectorLayer(SHP, "gemeinden", "ogr")
assert layer.isValid(), f"Layer failed to load: {SHP}"
print(f"Loaded layer: {layer.name()}, features: {layer.featureCount()}, CRS: {layer.crs().authid()}")

OUT_RASTER = os.path.join(OUT_DIR, "gemeinden_export.svg")
export_layer_to_svg(layer, OUT_RASTER, width=1200, height=900)
assert os.path.exists(OUT_RASTER), "Raster SVG was not created"
print(f"Raster SVG exported to: {OUT_RASTER}")

OUT_VECTOR = os.path.join(OUT_DIR, "gemeinden_vector.svg")
export_layer_to_svg_vector(layer, OUT_VECTOR, id_field="ags", width=1200)
assert os.path.exists(OUT_VECTOR), "Vector SVG was not created"
print(f"Vector SVG exported to: {OUT_VECTOR}")
