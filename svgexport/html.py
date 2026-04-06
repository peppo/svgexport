import json
import os


def generate_html_companion(svg_path, html_path, layers_fields_prefixes, search_layer_idx=-1):
    """Generate a self-contained HTML file alongside the SVG.

    Args:
        svg_path: Path to the already-written SVG file.
        html_path: Destination HTML path.
        layers_fields_prefixes: List of (layer, id_field, id_prefix) tuples for all exported layers.
        search_layer_idx: Index into layers_fields_prefixes for the search/autocomplete layer (-1 = last).
    """
    template_path = os.path.join(os.path.dirname(__file__), "map_template.html")
    with open(template_path, encoding="utf-8") as f:
        template = f.read()

    # Build layers JSON — one entry per layer with its data
    layers = []
    for layer, id_field, id_prefix in layers_fields_prefixes:
        records = []
        for feature in layer.getFeatures():
            row = {field.name(): feature[field.name()] for field in layer.fields()}
            records.append(row)
        layers.append({"idField": id_field, "idPrefix": id_prefix, "data": records})

    layers_json = json.dumps(layers, ensure_ascii=False)

    # Normalise search_layer_idx
    actual_search_idx = search_layer_idx % len(layers)

    with open(svg_path, encoding="utf-8") as f:
        svg_content = f.read()
    # Strip the XML declaration (<?xml ...?>) — not valid inside HTML
    if svg_content.startswith("<?xml"):
        svg_content = svg_content[svg_content.index("?>") + 2:].lstrip()

    html = (template
            .replace("__LAYERS_JSON__", layers_json)
            .replace("__SEARCH_LAYER_IDX__", str(actual_search_idx))
            .replace("__SVG_CONTENT__", svg_content))

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
