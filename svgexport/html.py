import json
import os
import re

from qgis.PyQt.QtCore import QDate, QDateTime, QTime
from qgis.core import NULL


def _coerce(v):
    """Convert QGIS/Qt field values to JSON-serializable Python types."""
    if v is NULL or v is None:
        return None
    if isinstance(v, QDateTime):
        return v.toString("yyyy-MM-ddTHH:mm:ss")
    if isinstance(v, QDate):
        return v.toString("yyyy-MM-dd")
    if isinstance(v, QTime):
        return v.toString("HH:mm:ss")
    return v


def generate_html_companion(svg_path, html_path, layers_fields_prefixes,
                            search_layer_idx=-1, search_field=None):
    """Generate a self-contained HTML file alongside the SVG.

    Args:
        svg_path: Path to the already-written SVG file.
        html_path: Destination HTML path.
        layers_fields_prefixes: List of (layer, id_field, id_prefix) tuples for all exported layers.
        search_layer_idx: Index into layers_fields_prefixes for the search/autocomplete layer (-1 = last).
        search_field: Field name to use for autocomplete/search on the search layer.
                      Defaults to that layer's id_field if not provided.
    """
    template_path = os.path.join(os.path.dirname(__file__), "map_template.html")
    with open(template_path, encoding="utf-8") as f:
        template = f.read()

    # Normalise search_layer_idx first so we can set searchField correctly below
    actual_search_idx = search_layer_idx % len(layers_fields_prefixes)

    # Build layers JSON — one entry per layer with its data
    layers = []
    for i, (layer, id_field, id_prefix, selectable) in enumerate(layers_fields_prefixes):
        records = []
        for feature in layer.getFeatures():
            row = {field.name(): _coerce(feature[field.name()]) for field in layer.fields()}
            records.append(row)
        sf = (search_field or id_field) if i == actual_search_idx else id_field
        layers.append({"idField": id_field, "idPrefix": id_prefix,
                        "searchField": sf, "selectable": selectable, "data": records})

    layers_json = json.dumps(layers, ensure_ascii=False)

    with open(svg_path, encoding="utf-8") as f:
        svg_content = f.read()
    # Strip the XML declaration (<?xml ...?>) — not valid inside HTML
    if svg_content.startswith("<?xml"):
        svg_content = svg_content[svg_content.index("?>") + 2:].lstrip()
    # Remove explicit width/height from the <svg> tag so CSS controls sizing;
    # viewBox is preserved for correct aspect-ratio scaling.
    svg_content = re.sub(r'(<svg\b[^>]*?)\s+width="[^"]*"', r'\1', svg_content)
    svg_content = re.sub(r'(<svg\b[^>]*?)\s+height="[^"]*"', r'\1', svg_content)

    html = (template
            .replace("__LAYERS_JSON__", layers_json)
            .replace("__SEARCH_LAYER_IDX__", str(actual_search_idx))
            .replace("__SVG_CONTENT__", svg_content))

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
