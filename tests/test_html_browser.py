"""Browser interaction tests for the HTML companion map.

Requires: pip install playwright && playwright install chromium

These tests are skipped automatically if playwright is not installed.
The html_file fixture in conftest.py generates the HTML via QGIS Python.
"""

import pytest

pytest.importorskip("playwright.sync_api", reason="playwright not installed")


@pytest.fixture(scope="module")
def page(html_file):
    from playwright.sync_api import sync_playwright
    url = "file:///" + html_file.replace("\\", "/")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        pg = browser.new_context().new_page()
        pg.goto(url)
        pg.wait_for_load_state("load")
        yield pg
        browser.close()


@pytest.fixture(scope="module")
def first_gemeinden_id(page):
    """Return the id attribute of the first gemeinden_ SVG element."""
    el_id = page.evaluate(
        "() => { const el = document.querySelector('[id^=\"gemeinden_\"]'); return el ? el.id : null; }"
    )
    assert el_id, "No gemeinden_ element found in SVG"
    return el_id


def test_featureinfo_hidden_on_load(page):
    """#featureinfo panel must start hidden."""
    display = page.locator("#featureinfo").evaluate("el => el.style.display")
    assert display in ("none", ""), "#featureinfo should be hidden on load"


def test_click_gemeinden_shows_table(page, first_gemeinden_id):
    """Clicking a gemeinden polygon fills the data table."""
    page.locator(f"[id='{first_gemeinden_id}']").first.click()
    assert page.locator("#featureinfo").evaluate("el => el.style.display") == "block"
    assert page.locator("#featurefields tr").count() > 0


def test_click_gemeinden_highlights_element(page, first_gemeinden_id):
    """Clicking a gemeinden polygon adds feature-highlight class."""
    page.locator(f"[id='{first_gemeinden_id}']").first.click()
    has_class = page.locator(f"[id='{first_gemeinden_id}']").first.evaluate(
        "el => el.classList.contains('feature-highlight')"
    )
    assert has_class, "Clicked element should have 'feature-highlight' class"


def test_click_point_shows_table(page):
    """Clicking a point feature shows its layer's data."""
    point_id = page.evaluate(
        "() => { const el = document.querySelector('[id^=\"point_\"]'); return el ? el.id : null; }"
    )
    assert point_id, "No point_ element found in SVG"
    page.locator(f"[id='{point_id}']").first.click()
    assert page.locator("#featureinfo").evaluate("el => el.style.display") == "block"
    assert page.locator("#featurefields tr").count() > 0


def test_click_line_shows_table(page):
    """Clicking a line feature shows its layer's data."""
    line_id = page.evaluate(
        "() => { const el = document.querySelector('[id^=\"line_\"]'); return el ? el.id : null; }"
    )
    assert line_id, "No line_ element found in SVG"
    # force=True bypasses Playwright's overlap check — line paths can be
    # visually covered by point symbols but are still clickable via JS events.
    page.locator(f"[id='{line_id}']").first.click(force=True)
    assert page.locator("#featureinfo").evaluate("el => el.style.display") == "block"
    assert page.locator("#featurefields tr").count() > 0


def test_search_highlights_feature(page, first_gemeinden_id):
    """Typing an AGS value and pressing Enter highlights the polygon."""
    # Extract the AGS code from the element id (strip 'gemeinden_' prefix)
    ags = first_gemeinden_id.split("_", 1)[1]
    page.locator("#myInput").fill(ags)
    page.locator("#myInput").press("Enter")
    has_class = page.locator(f"[id='{first_gemeinden_id}']").first.evaluate(
        "el => el.classList.contains('feature-highlight')"
    )
    assert has_class, "Searched element should have 'feature-highlight' class"


def test_search_shows_info(page, first_gemeinden_id):
    """Search also populates the data table."""
    ags = first_gemeinden_id.split("_", 1)[1]
    page.locator("#myInput").fill(ags)
    page.locator("#myInput").press("Enter")
    assert page.locator("#featureinfo").evaluate("el => el.style.display") == "block"
    assert page.locator("#featurefields tr").count() > 0


def test_previous_highlight_removed_on_new_click(page, first_gemeinden_id):
    """Clicking a second feature removes the highlight from the first."""
    page.locator(f"[id='{first_gemeinden_id}']").first.click()

    second_id = page.evaluate(
        "() => { const els = document.querySelectorAll('[id^=\"gemeinden_\"]'); "
        "return els.length > 1 ? els[1].id : null; }"
    )
    if not second_id:
        pytest.skip("Only one gemeinden element found")

    page.locator(f"[id='{second_id}']").first.click()

    assert not page.locator(f"[id='{first_gemeinden_id}']").first.evaluate(
        "el => el.classList.contains('feature-highlight')"
    ), "Previous highlight should be removed"
    assert page.locator(f"[id='{second_id}']").first.evaluate(
        "el => el.classList.contains('feature-highlight')"
    ), "New element should be highlighted"
