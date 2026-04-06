# SVG Export — QGIS Plugin

Export one or more QGIS vector layers to a single SVG file, with each feature receiving an `id` attribute derived from a chosen field. Optionally generates a self-contained HTML companion file with an interactive map to show how the svg could be used: click any feature to see its attributes, or search by field value to highlight it on the map.

---

## Features

- Export polygon, line, and point layers to SVG, preserving QGIS symbol colours and stroke widths
- Multi-layer export into one SVG, with layer-name prefixes on element IDs
- ID field selection per layer — any field with unique values can be used
- Optional HTML companion file with:
  - Click-to-table: click any feature to display its attributes
  - Search-to-highlight: type a field value in the search box, matching feature is highlighted
  - Works across all exported layers simultaneously
  - Fully self-contained (inline SVG + JSON data, no server needed)
- Opens the generated HTML in the default browser automatically after export

---

## Requirements

- QGIS 3.16 or later (tested on 4.0)
- Python 3.9+ (bundled with QGIS)

---

## Installation

### From the QGIS Plugin Manager

1. Open QGIS → **Plugins → Manage and Install Plugins**
2. Search for *SVG Export*
3. Click **Install**

### From source

```
git clone https://github.com/peppo/svgexport.git
```

Copy (or symlink) the `svgexport/` subdirectory into your QGIS plugin folder:

| Platform | Path |
|----------|------|
| Windows  | `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\` |
| Linux    | `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/` |
| macOS    | `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/` |

Then enable the plugin in **Plugins → Manage and Install Plugins → Installed**.

---

## Usage

1. Open the plugin via **Plugins → SVG Export → Export to SVG** (or the toolbar icon)
2. Check one or more vector layers in the layer table and choose an **ID Field** for each
3. Set the output **Width** in pixels
4. Optionally enable **Create inspirational HTML** and select the **Search layer** and **Search field** (the field used for the autocomplete search box)
5. Choose an output SVG path and click **Export**

When HTML export is enabled, the generated `.html` file opens automatically in the default browser.

### SVG element IDs

| Export type | Element ID format |
|-------------|-------------------|
| Single layer | `{field_value}` — e.g. `09178113` |
| Multi-layer  | `{layer_name}_{field_value}` — e.g. `gemeinden_09178113`, `point_3` |

Point features are wrapped in `<g id="...">` groups; polygon and line features use `<path id="...">`.

---

## Development

### Project layout

```
svgexport/
├── svgexport/           # Plugin source
│   ├── plugin.py        # QGIS entry point
│   ├── dialog.py        # Export dialog and background task
│   ├── api.py           # SVG generation engine
│   ├── html.py          # HTML companion generator
│   └── map_template.html  # HTML/JS template
├── tests/
│   ├── qgis_init.py     # QGIS bootstrap for standalone scripts
│   ├── conftest.py      # pytest fixtures (HTML generation via QGIS subprocess)
│   ├── test_export.py   # SVG export tests (run with QGIS Python directly)
│   ├── test_html.py     # HTML generation script (called by conftest)
│   ├── test_html_structure.py  # Static HTML content tests
│   └── test_html_browser.py   # Playwright browser interaction tests
├── test_data/
│   ├── gemeinden.*      # Polygon shapefile — German municipalities
│   ├── gemeinden_style.qml
│   └── geomtypes/
│       ├── point.*      # Point test layer
│       └── line.*       # Line test layer
└── build.py             # Packages the plugin as a .zip
```

### Building

```
python build.py
```

Produces `svgexport.{version}.zip` ready for installation via the QGIS Plugin Manager.

---

## Tests

The test suite has two parts:

| File | Runner | What it tests |
|------|--------|---------------|
| `test_export.py` | QGIS Python | SVG output — geometry, styles, multi-layer extent |
| `test_html_structure.py` | venv pytest | Generated HTML structure and embedded JSON data |
| `test_html_browser.py` | venv pytest + Playwright | Click-to-table and search-to-highlight in a real browser |

### One-time setup

**1. Create a Python virtual environment** (uses the Python bundled with QGIS):

```powershell
# Windows — adjust the path if your version differs
& "C:\Program Files\QGIS 4.0.0\apps\Python313\python.exe" -m venv .venv
```

**2. Install test dependencies:**

```powershell
.venv\Scripts\pip install pytest playwright
.venv\Scripts\playwright install chromium
```

### Running the tests

```powershell
.venv\Scripts\pytest tests\test_html_structure.py tests\test_html_browser.py -v
```

`conftest.py` automatically calls the QGIS Python to generate the HTML fixture before the tests run — no separate step needed.

**What the fixture does:**

1. Locates the QGIS Python executable (auto-detected from `C:\Program Files\QGIS *`, or override with `QGIS_ROOT`)
2. Runs `tests/test_html.py` as a subprocess — exports SVG and HTML from the three test layers (gemeinden, point, line)
3. Structure and browser tests consume the generated `tests/test_output/test_html_multilayer.html`

### Running the SVG export tests

These tests use the QGIS Python directly and are run standalone:

```powershell
cd tests
& "C:\Program Files\QGIS 4.0.0\apps\Python313\python.exe" test_export.py
```

### Using a non-default QGIS installation

```powershell
$env:QGIS_ROOT = "C:\Program Files\QGIS 4.0.0"
.venv\Scripts\pytest tests\test_html_structure.py tests\test_html_browser.py -v
```

---

## License

GPL-3.0-or-later — see [LICENSE](svgexport/LICENSE).
