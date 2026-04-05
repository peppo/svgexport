import json
import os


def generate_html_companion(svg_path, html_path, layer, id_field, id_prefix):
    """Generate a self-contained HTML file alongside the SVG.

    Args:
        svg_path: Path to the already-written SVG file.
        html_path: Destination HTML path.
        layer: Top QgsVectorLayer (for feature attributes).
        id_field: The id field name (used as autocomplete search key).
        id_prefix: Prefix used in SVG element IDs ('' or 'layername_').
    """
    template_path = os.path.join(os.path.dirname(__file__), "map_template.html")
    with open(template_path, encoding="utf-8") as f:
        template = f.read()

    # Build JSON data from all feature attributes of the top layer
    records = []
    for feature in layer.getFeatures():
        row = {field.name(): feature[field.name()] for field in layer.fields()}
        records.append(row)
    data_json = json.dumps(records, ensure_ascii=False)

    with open(svg_path, encoding="utf-8") as f:
        svg_content = f.read()
    # Strip the XML declaration (<?xml ...?>) — not valid inside HTML
    if svg_content.startswith("<?xml"):
        svg_content = svg_content[svg_content.index("?>") + 2:].lstrip()

    html = (template
            .replace("__SVG_CONTENT__", svg_content)
            .replace("__DATA_JSON__", data_json)
            .replace("__ID_FIELD__", id_field)
            .replace("__ID_PREFIX__", id_prefix))

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
