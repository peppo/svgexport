"""Session fixtures shared across test files."""

import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_HTML = os.path.join(HERE, "test_output", "test_html_multilayer.html")

# Locate QGIS Python — same candidate list as qgis_init.py
_QGIS_CANDIDATES = [
    r'C:\Program Files\QGIS 3.40.15',
    r'C:\Program Files\QGIS 3.38',
    r'C:\Program Files\QGIS 3.36',
]

def _find_qgis_python():
    root = os.environ.get("QGIS_ROOT")
    candidates = [root] if root else _QGIS_CANDIDATES
    for base in candidates:
        for pattern in [
            os.path.join(base, "apps", "Python312", "python.exe"),
            os.path.join(base, "apps", "Python3",   "python.exe"),
        ]:
            if os.path.isfile(pattern):
                return pattern
    return None


@pytest.fixture(scope="session")
def html_file():
    """Generate the multi-layer HTML test fixture using QGIS Python.

    Runs tests/test_html.py as a subprocess so that QGIS modules are available.
    Returns the path to the generated HTML file.
    """
    qgis_python = _find_qgis_python()
    if not qgis_python:
        pytest.skip("QGIS Python not found — set QGIS_ROOT env var or install QGIS 3.40")

    script = os.path.join(HERE, "test_html.py")
    result = subprocess.run(
        [qgis_python, script],
        capture_output=True,
        text=True,
        cwd=HERE,
    )
    if result.returncode != 0:
        pytest.fail(
            f"HTML generation script failed (exit {result.returncode}):\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    assert os.path.exists(OUT_HTML), f"HTML not found after generation: {OUT_HTML}"
    return OUT_HTML
