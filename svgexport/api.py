import xml.etree.ElementTree as ET

from qgis.core import (
    QgsMapLayer, QgsMapSettings, QgsMapRendererParallelJob,
    QgsVectorLayer, QgsCoordinateTransform, QgsProject, QgsWkbTypes,
)
from qgis.PyQt.QtSvg import QSvgGenerator
from qgis.PyQt.QtCore import QSize, QRectF
from qgis.PyQt.QtGui import QPainter, QColor


def export_layer_to_svg(
    layer: QgsMapLayer,
    output_path: str,
    width: int = 800,
    height: int = 600,
    extent=None,
    crs=None,
    background_color: QColor = None,
):
    """Export a QGIS map layer to an SVG file.

    Args:
        layer: The QgsMapLayer to export. Pass None to export all visible layers
               (requires extent and crs to be provided).
        output_path: Destination .svg file path.
        width: Output width in pixels.
        height: Output height in pixels.
        extent: QgsRectangle defining the map extent. Defaults to the layer extent.
        crs: QgsCoordinateReferenceSystem for the output. Defaults to the layer CRS.
        background_color: Background QColor. Defaults to white.
    """
    if layer is None and extent is None:
        raise ValueError("extent must be provided when layer is None")

    settings = QgsMapSettings()
    settings.setLayers([layer] if layer is not None else [])
    settings.setExtent(extent if extent is not None else layer.extent())
    settings.setOutputSize(QSize(width, height))
    settings.setDestinationCrs(crs if crs is not None else layer.crs())
    settings.setBackgroundColor(background_color if background_color is not None else QColor("white"))

    generator = QSvgGenerator()
    generator.setFileName(output_path)
    generator.setSize(QSize(width, height))
    generator.setViewBox(QRectF(0, 0, width, height))
    generator.setTitle("QGIS SVG Export")
    generator.setDescription("Exported by SVGExport QGIS plugin")

    job = QgsMapRendererParallelJob(settings)
    job.start()
    job.waitForFinished()

    painter = QPainter(generator)
    painter.drawImage(0, 0, job.renderedImage())
    painter.end()


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

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="unicode", xml_declaration=True)
