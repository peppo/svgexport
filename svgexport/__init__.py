def classFactory(iface):
    from .plugin import SVGExportPlugin
    return SVGExportPlugin(iface)
