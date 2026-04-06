"""Static structure tests for the generated HTML companion file.

These run with venv Python (no QGIS needed). The html_file fixture in
conftest.py generates the file via a QGIS Python subprocess first.
"""

import json
import re


def test_no_unreplaced_placeholders(html_file):
    html = open(html_file, encoding="utf-8").read()
    found = re.findall(r'__[A-Z_]+__', html)
    assert not found, f"Unreplaced placeholders: {found}"


def test_three_layers_embedded(html_file):
    html = open(html_file, encoding="utf-8").read()
    m = re.search(r'const layers = (\[.*?\]);', html, re.DOTALL)
    assert m, "Could not find 'const layers = [...]' in HTML"
    layers = json.loads(m.group(1))
    assert len(layers) == 3, f"Expected 3 layers, got {len(layers)}"


def test_gemeinden_layer_data(html_file):
    html = open(html_file, encoding="utf-8").read()
    m = re.search(r'const layers = (\[.*?\]);', html, re.DOTALL)
    layers = json.loads(m.group(1))
    lyr = next((l for l in layers if l["idPrefix"] == "gemeinden_"), None)
    assert lyr is not None, "No layer with idPrefix 'gemeinden_'"
    assert lyr["idField"] == "ags"
    assert "searchField" in lyr, "gemeinden layer missing 'searchField' key"
    assert lyr["searchField"] == "name", f"Expected searchField='name', got '{lyr['searchField']}'"
    ags_values = [str(r["ags"]) for r in lyr["data"]]
    assert len(ags_values) > 0, "gemeinden data is empty"
    assert any(v for v in ags_values), "ags field has no values"


def test_point_layer_data(html_file):
    html = open(html_file, encoding="utf-8").read()
    m = re.search(r'const layers = (\[.*?\]);', html, re.DOTALL)
    layers = json.loads(m.group(1))
    lyr = next((l for l in layers if l["idPrefix"] == "point_"), None)
    assert lyr is not None, "No layer with idPrefix 'point_'"
    assert lyr["idField"] == "id"
    assert "searchField" in lyr, "point layer missing 'searchField' key"
    assert len(lyr["data"]) > 0


def test_line_layer_data(html_file):
    html = open(html_file, encoding="utf-8").read()
    m = re.search(r'const layers = (\[.*?\]);', html, re.DOTALL)
    layers = json.loads(m.group(1))
    lyr = next((l for l in layers if l["idPrefix"] == "line_"), None)
    assert lyr is not None, "No layer with idPrefix 'line_'"
    assert lyr["idField"] == "id"
    assert "searchField" in lyr, "line layer missing 'searchField' key"
    assert len(lyr["data"]) > 0


def test_svg_ids_match_gemeinden_features(html_file):
    html = open(html_file, encoding="utf-8").read()
    svg_ids = set(re.findall(r'\bid="(gemeinden_[^"]+)"', html))
    m = re.search(r'const layers = (\[.*?\]);', html, re.DOTALL)
    layers = json.loads(m.group(1))
    lyr = next(l for l in layers if l["idPrefix"] == "gemeinden_")
    assert len(svg_ids) == len(lyr["data"]), (
        f"SVG gemeinden element count ({len(svg_ids)}) != "
        f"feature count ({len(lyr['data'])})"
    )


def test_search_layer_idx(html_file):
    html = open(html_file, encoding="utf-8").read()
    m = re.search(r'const searchLayerIdx = (\d+);', html)
    assert m, "Could not find searchLayerIdx in HTML"
    assert int(m.group(1)) == 0, f"Expected searchLayerIdx=0, got {m.group(1)}"
