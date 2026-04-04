import xml.etree.ElementTree as ET

from qgis.core import (
    QgsVectorLayer, QgsCoordinateTransform, QgsProject, QgsWkbTypes,
    QgsRenderContext,
)
from qgis.PyQt.QtGui import QColor


def _color_to_hex(color: QColor) -> str:
    return f"#{color.red():02x}{color.green():02x}{color.blue():02x}"


def _feature_style_attrs(renderer, feature, context) -> dict:
    """Return SVG style attribute dict for a feature via the layer renderer."""
    symbol = renderer.symbolForFeature(feature, context)
    if symbol is None:
        return {}

    fill_color = symbol.color()
    stroke_color = QColor(35, 35, 35)
    stroke_width_mm = 0.26

    for i in range(symbol.symbolLayerCount()):
        sl = symbol.symbolLayer(i)
        if hasattr(sl, "strokeColor"):
            stroke_color = sl.strokeColor()
        if hasattr(sl, "strokeWidth"):
            stroke_width_mm = sl.strokeWidth()
        break  # first symbol layer only

    stroke_px = round(stroke_width_mm * 96 / 25.4, 2)  # mm → px at 96 DPI

    parts = [f"fill:{_color_to_hex(fill_color)}"]
    if fill_color.alpha() < 255:
        parts.append(f"fill-opacity:{fill_color.alpha()/255:.3f}")
    parts += [f"stroke:{_color_to_hex(stroke_color)}", f"stroke-width:{stroke_px}"]
    if stroke_color.alpha() < 255:
        parts.append(f"stroke-opacity:{stroke_color.alpha()/255:.3f}")

    return {"style": ";".join(parts)}


def _ring_to_svg(points, x0, y0, scale):
    """Convert a list of QgsPointXY to an SVG path ring string."""
    parts = []
    for i, pt in enumerate(points):
        sx = round((pt.x() - x0) * scale, 2)
        sy = round((y0 - pt.y()) * scale, 2)
        parts.append(f"{'M' if i == 0 else 'L'} {sx} {sy}")
    parts.append("Z")
    return " ".join(parts)


def _geometry_to_svg_d(geom, x0, y0, scale):
    """Return the SVG `d` string for a polygon or multipolygon geometry."""
    wkb_type = QgsWkbTypes.flatType(geom.wkbType())
    parts = []

    if wkb_type == QgsWkbTypes.Polygon:
        polygons = [geom.asPolygon()]
    else:
        polygons = geom.asMultiPolygon()

    for polygon in polygons:
        for ring in polygon:
            parts.append(_ring_to_svg(ring, x0, y0, scale))

    return " ".join(parts)


def export_layer_to_svg_vector(
    layer: QgsVectorLayer,
    output_path: str,
    id_field: str,
    width: int = 800,
    extent=None,
    crs=None,
):
    """Export a vector layer to SVG with one <path> per feature.

    Args:
        layer: QgsVectorLayer to export.
        output_path: Destination .svg file path.
        id_field: Layer field whose value becomes the `id` attribute of each path.
        width: Output width in pixels. Height is derived from the extent aspect ratio.
        extent: QgsRectangle defining the map extent. Defaults to layer.extent().
        crs: Target QgsCoordinateReferenceSystem. Defaults to layer.crs().
    """
    if extent is None:
        extent = layer.extent()

    height = round(width * extent.height() / extent.width())
    scale = width / extent.width()
    x0 = extent.xMinimum()
    y0 = extent.yMaximum()

    transform = None
    target_crs = crs or layer.crs()
    if target_crs != layer.crs():
        transform = QgsCoordinateTransform(layer.crs(), target_crs, QgsProject.instance())

    ET.register_namespace("", "http://www.w3.org/2000/svg")
    root = ET.Element(
        "{http://www.w3.org/2000/svg}svg",
        {
            "viewBox": f"0 0 {width} {height}",
            "preserveAspectRatio": "xMaxYMax meet",
        },
    )

    renderer = layer.renderer()
    render_ctx = QgsRenderContext()
    renderer.startRender(render_ctx, layer.fields())

    for feature in layer.getFeatures():
        geom = feature.geometry()
        if transform:
            geom.transform(transform)

        d = _geometry_to_svg_d(geom, x0, y0, scale)
        if not d:
            continue

        path_el = ET.SubElement(root, "{http://www.w3.org/2000/svg}path")
        path_el.set("d", d)
        path_el.set("id", str(feature[id_field]))
        for attr, val in _feature_style_attrs(renderer, feature, render_ctx).items():
            path_el.set(attr, val)

    renderer.stopRender(render_ctx)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="unicode", xml_declaration=True)
