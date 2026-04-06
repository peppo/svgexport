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


@pytest.fixture(scope="module")
def first_name_value(page):
    """Return the 'name' field value of the first gemeinden feature (search field)."""
    return page.evaluate(
        "() => { const sl = layers[searchLayerIdx]; "
        "return sl.data.length > 0 ? String(sl.data[0][sl.searchField]) : null; }"
    )


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


def test_search_uses_search_field(page, first_gemeinden_id, first_name_value):
    """Search uses searchField (name), not idField (ags)."""
    assert first_name_value, "Could not read first name value from layers data"
    page.locator("#myInput").fill(first_name_value)
    page.locator("#myInput").press("Enter")
    has_class = page.locator(f"[id='{first_gemeinden_id}']").first.evaluate(
        "el => el.classList.contains('feature-highlight')"
    )
    assert has_class, "Feature matching search field value should be highlighted"


def test_search_shows_info(page, first_name_value):
    """Search populates the data table."""
    page.locator("#myInput").fill(first_name_value)
    page.locator("#myInput").press("Enter")
    assert page.locator("#featureinfo").evaluate("el => el.style.display") == "block"
    assert page.locator("#featurefields tr").count() > 0


def test_search_multi_highlight(page):
    """Searching a value shared by multiple features highlights all of them."""
    # The 'art' field has repeated values (e.g. 'Gemeinde') — use ueboname which
    # groups multiple Gemeinden under one Verwaltungsgemeinschaft
    match_count = page.evaluate("""() => {
        const sl = layers[searchLayerIdx];
        const val = 'Allershausen';
        return sl.data.filter(n => String(n[sl.searchField]).toLowerCase().includes(val.toLowerCase())).length;
    }""")

    if match_count < 1:
        pytest.skip("No features matching 'Allershausen' in name field")

    page.locator("#myInput").fill("Allershausen")
    page.locator("#myInput").press("Enter")

    highlighted = page.evaluate(
        "() => document.querySelectorAll('.feature-highlight').length"
    )
    assert highlighted >= 1, "At least one feature should be highlighted after search"

    if match_count > 1:
        assert highlighted == match_count, (
            f"Expected {match_count} highlighted features, got {highlighted}"
        )


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


def test_search_clears_previous_highlights(page, first_gemeinden_id, first_name_value):
    """Running a new search clears highlights from the previous one."""
    # First: click-select one feature
    page.locator(f"[id='{first_gemeinden_id}']").first.click()
    assert page.locator(f"[id='{first_gemeinden_id}']").first.evaluate(
        "el => el.classList.contains('feature-highlight')"
    ), "Pre-condition: first element should be highlighted"

    # Then: search for a different name — previous highlight must vanish
    second_name = page.evaluate("""() => {
        const sl = layers[searchLayerIdx];
        return sl.data.length > 1 ? String(sl.data[1][sl.searchField]) : null;
    }""")
    if not second_name or second_name == first_name_value:
        pytest.skip("Cannot find a distinct second name value")

    page.locator("#myInput").fill(second_name)
    page.locator("#myInput").press("Enter")

    still_highlighted = page.locator(f"[id='{first_gemeinden_id}']").first.evaluate(
        "el => el.classList.contains('feature-highlight')"
    )
    assert not still_highlighted, "Previous click-highlight should be cleared by new search"
