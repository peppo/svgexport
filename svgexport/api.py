import xml.etree.ElementTree as ET

from qgis.core import (
    QgsVectorLayer, QgsWkbTypes,
    QgsRenderContext, QgsRectangle,
    QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsProject,
)
from qgis.PyQt.QtGui import QColor

_NS = "http://www.w3.org/2000/svg"
_MM_TO_PX = 96 / 25.4  # mm → px at 96 DPI


def _color_to_hex(color: QColor) -> str:
    return f"#{color.red():02x}{color.green():02x}{color.blue():02x}"


def _color_parts(color: QColor, prop: str) -> list:
    parts = [f"{prop}:{_color_to_hex(color)}"]
    if color.alpha() < 255:
        parts.append(f"{prop}-opacity:{color.alpha()/255:.3f}")
    return parts


def _polygon_style(symbol) -> str:
    fill_color = symbol.color()
    stroke_color = QColor(35, 35, 35)
    stroke_width_mm = 0.26
    sl = symbol.symbolLayer(0)
    if hasattr(sl, "strokeColor"):
        stroke_color = sl.strokeColor()
    if hasattr(sl, "strokeWidth"):
        stroke_width_mm = sl.strokeWidth()
    stroke_px = round(stroke_width_mm * _MM_TO_PX, 2)
    parts = _color_parts(fill_color, "fill")
    parts += _color_parts(stroke_color, "stroke")
    parts.append(f"stroke-width:{stroke_px}")
    return ";".join(parts)


def _line_style(symbol) -> str:
    color = symbol.color()
    width_mm = 0.26
    sl = symbol.symbolLayer(0)
    if hasattr(sl, "width"):
        width_mm = sl.width()
    width_px = round(width_mm * _MM_TO_PX, 2)
    parts = ["fill:none"] + _color_parts(color, "stroke")
    parts.append(f"stroke-width:{width_px}")
    return ";".join(parts)


# Marker shapes that have no fill — only stroke.
_STROKE_ONLY_SHAPES = {"cross", "cross2", "x", "line", "arrowhead"}


def _sl_style(sl, no_fill=False) -> str:
    """Build a CSS style string for one SimpleMarker symbol layer."""
    parts = []
    color = sl.color() if hasattr(sl, "color") else QColor(0, 0, 0, 0)
    if no_fill or color.alpha() == 0:
        parts.append("fill:none")
    else:
        parts += _color_parts(color, "fill")
    if hasattr(sl, "strokeColor"):
        parts += _color_parts(sl.strokeColor(), "stroke")
    if hasattr(sl, "strokeWidth"):
        parts.append(f"stroke-width:{round(sl.strokeWidth() * _MM_TO_PX, 2)}")
    return ";".join(parts)


def _add_marker_shape(parent, shape_name, half_px, style):
    """Append one SVG shape element for a QGIS marker, centered at origin."""
    s = round(half_px, 2)
    t = round(s / 3, 2)  # arm thickness for cross shapes

    if shape_name in ("square", "rectangle"):
        el = ET.SubElement(parent, f"{{{_NS}}}rect")
        el.set("x", str(round(-s, 2))); el.set("y", str(round(-s, 2)))
        el.set("width", str(round(2 * s, 2))); el.set("height", str(round(2 * s, 2)))
    elif shape_name == "diamond":
        el = ET.SubElement(parent, f"{{{_NS}}}polygon")
        el.set("points", f"0,{-s} {s},0 0,{s} {-s},0")
    elif shape_name == "triangle":
        el = ET.SubElement(parent, f"{{{_NS}}}polygon")
        el.set("points", f"0,{-s} {s},{s} {-s},{s}")
    elif shape_name == "cross_fill":
        el = ET.SubElement(parent, f"{{{_NS}}}path")
        el.set("d", (
            f"M {-t},{-s} L {t},{-s} L {t},{-t} L {s},{-t} "
            f"L {s},{t} L {t},{t} L {t},{s} L {-t},{s} "
            f"L {-t},{t} L {-s},{t} L {-s},{-t} L {-t},{-t} Z"
        ))
    elif shape_name in ("cross", "plus"):
        el = ET.SubElement(parent, f"{{{_NS}}}path")
        el.set("d", f"M {-s},0 L {s},0 M 0,{-s} L 0,{s}")
    elif shape_name in ("cross2", "x"):
        el = ET.SubElement(parent, f"{{{_NS}}}path")
        el.set("d", f"M {-s},{-s} L {s},{s} M {s},{-s} L {-s},{s}")
    else:  # circle (default / fallback)
        el = ET.SubElement(parent, f"{{{_NS}}}circle")
        el.set("r", str(s))

    if style:
        el.set("style", style)


def _ring_to_svg(points, x0, y0, scale, close=True) -> str:
    parts = []
    for i, pt in enumerate(points):
        sx = round((pt.x() - x0) * scale, 2)
        sy = round((y0 - pt.y()) * scale, 2)
        parts.append(f"{'M' if i == 0 else 'L'} {sx} {sy}")
    if close:
        parts.append("Z")
    return " ".join(parts)


def _geometry_to_svg_d(geom, x0, y0, scale) -> str:
    """Return SVG path `d` string for polygon, multipolygon, line, or multiline."""
    wkb_type = QgsWkbTypes.flatType(geom.wkbType())
    parts = []

    if wkb_type == QgsWkbTypes.Polygon:
        for ring in geom.asPolygon():
            parts.append(_ring_to_svg(ring, x0, y0, scale, close=True))
    elif wkb_type == QgsWkbTypes.MultiPolygon:
        for polygon in geom.asMultiPolygon():
            for ring in polygon:
                parts.append(_ring_to_svg(ring, x0, y0, scale, close=True))
    elif wkb_type == QgsWkbTypes.LineString:
        parts.append(_ring_to_svg(geom.asPolyline(), x0, y0, scale, close=False))
    elif wkb_type == QgsWkbTypes.MultiLineString:
        for line in geom.asMultiPolyline():
            parts.append(_ring_to_svg(line, x0, y0, scale, close=False))

    return " ".join(parts)


def _render_marker_at(parent, symbol, cx, cy):
    """Append a <g transform="translate(cx,cy)"> with one element per symbol layer."""
    g = ET.SubElement(parent, f"{{{_NS}}}g")
    g.set("transform", f"translate({cx},{cy})")
    if symbol is None:
        el = ET.SubElement(g, f"{{{_NS}}}circle")
        el.set("r", "4")
        return g
    for i in range(symbol.symbolLayerCount()):
        sl = symbol.symbolLayer(i)
        if sl.layerType() != "SimpleMarker":
            continue
        shape = sl.properties().get("name", "circle")
        half_px = round(sl.size() / 2 * _MM_TO_PX, 2)
        no_fill = shape in _STROKE_ONLY_SHAPES
        style = _sl_style(sl, no_fill=no_fill)
        _add_marker_shape(g, shape, half_px, style)
    return g


def _add_point_elements(parent, geom, feature_id, symbol, x0, y0, scale):
    """Add SVG element(s) for a point or multipoint feature."""
    wkb_type = QgsWkbTypes.flatType(geom.wkbType())
    points = [geom.asPoint()] if wkb_type == QgsWkbTypes.Point else geom.asMultiPoint()

    if len(points) == 1:
        pt = points[0]
        cx = round((pt.x() - x0) * scale, 2)
        cy = round((y0 - pt.y()) * scale, 2)
        g = _render_marker_at(parent, symbol, cx, cy)
        g.set("id", str(feature_id))
    else:
        outer = ET.SubElement(parent, f"{{{_NS}}}g")
        outer.set("id", str(feature_id))
        for pt in points:
            cx = round((pt.x() - x0) * scale, 2)
            cy = round((y0 - pt.y()) * scale, 2)
            _render_marker_at(outer, symbol, cx, cy)


def _render_layer(root, layer, id_field, x0, y0, scale, id_prefix, progress_offset,
                  total_features, progress_callback, should_stop, transform=None):
    """Render one layer's features into the SVG root element."""
    geom_type = QgsWkbTypes.geometryType(layer.wkbType())

    renderer = layer.renderer()
    render_ctx = QgsRenderContext()
    renderer.startRender(render_ctx, layer.fields())

    for i, feature in enumerate(layer.getFeatures()):
        if should_stop and should_stop():
            renderer.stopRender(render_ctx)
            return False

        geom = feature.geometry()
        if transform:
            geom.transform(transform)
        symbol = renderer.symbolForFeature(feature, render_ctx)
        feature_id = f"{id_prefix}{feature[id_field]}"

        if geom_type == QgsWkbTypes.PointGeometry:
            _add_point_elements(root, geom, feature_id, symbol, x0, y0, scale)
        else:
            d = _geometry_to_svg_d(geom, x0, y0, scale)
            if not d:
                continue
            path_el = ET.SubElement(root, f"{{{_NS}}}path")
            path_el.set("id", feature_id)
            path_el.set("d", d)
            if symbol:
                style_fn = _line_style if geom_type == QgsWkbTypes.LineGeometry else _polygon_style
                path_el.set("style", style_fn(symbol))

        if progress_callback and total_features:
            done = progress_offset + i + 1
            progress_callback(done / total_features * 100)

    renderer.stopRender(render_ctx)
    return True


def export_layers_to_svg_vector(
    layers_fields,
    output_path: str,
    width: int = 800,
    extent=None,
    progress_callback=None,
    should_stop=None,
):
    """Export one or more vector layers to a single SVG, one element per feature.

    Args:
        layers_fields: List of (QgsVectorLayer, id_field_name) tuples in
                       bottom-to-top render order (bottom layer drawn first).
        output_path: Destination .svg file path.
        width: Output width in pixels. Height is derived from the combined extent.
        extent: QgsRectangle defining the map extent. Defaults to the union of all
                layer extents.
        progress_callback: Optional callable(percent: float).
        should_stop: Optional callable() -> bool; export aborts when True.
    """
    if not layers_fields:
        raise ValueError("layers_fields must not be empty")

    multi = len(layers_fields) > 1

    # Use the first layer's CRS as the target CRS for all coordinate operations.
    target_crs = layers_fields[0][0].crs()
    project = QgsProject.instance()

    def _make_transform(layer):
        if layer.crs() == target_crs:
            return None
        return QgsCoordinateTransform(layer.crs(), target_crs, project)

    def _layer_extent_in_target(layer):
        ext = QgsRectangle(layer.extent())
        t = _make_transform(layer)
        if t:
            ext = t.transformBoundingBox(ext)
        return ext

    if extent is None:
        extent = _layer_extent_in_target(layers_fields[0][0])
        for layer, _ in layers_fields[1:]:
            extent.combineExtentWith(_layer_extent_in_target(layer))

    height = round(width * extent.height() / extent.width())
    scale = width / extent.width()
    x0 = extent.xMinimum()
    y0 = extent.yMaximum()

    total_features = sum(layer.featureCount() for layer, _ in layers_fields) or 1

    ET.register_namespace("", _NS)
    root = ET.Element(
        f"{{{_NS}}}svg",
        {
            "viewBox": f"0 0 {width} {height}",
            "preserveAspectRatio": "xMidYMid meet",
        },
    )

    progress_offset = 0
    for layer, id_field in layers_fields:
        id_prefix = f"{layer.name()}_" if multi else ""
        ok = _render_layer(
            root, layer, id_field, x0, y0, scale,
            id_prefix=id_prefix,
            progress_offset=progress_offset,
            total_features=total_features,
            progress_callback=progress_callback,
            should_stop=should_stop,
            transform=_make_transform(layer),
        )
        if not ok:
            return
        progress_offset += layer.featureCount()

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="unicode", xml_declaration=True)


def export_layer_to_svg_vector(
    layer: QgsVectorLayer,
    output_path: str,
    id_field: str,
    width: int = 800,
    extent=None,
    progress_callback=None,
    should_stop=None,
):
    """Export a single vector layer to SVG. See export_layers_to_svg_vector."""
    export_layers_to_svg_vector(
        layers_fields=[(layer, id_field)],
        output_path=output_path,
        width=width,
        extent=extent,
        progress_callback=progress_callback,
        should_stop=should_stop,
    )
