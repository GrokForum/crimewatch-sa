"""Tests for the daily-sweep catalog, page and site gate."""
import json
from pathlib import Path

import pytest

import build_site as bs
import site_gate as sg
import sweeps


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    return bs.build(tmp_path_factory.mktemp("sweeps-site") / "site")


@pytest.fixture
def site_copy(site, tmp_path):
    import shutil
    dst = tmp_path / "site"
    shutil.copytree(site, dst)
    return dst


DISCLAIMER = (
    "We are not responsible for anything published by anyone else, "
    "including personal information."
)


def test_committed_catalog_loads():
    catalog = sweeps.load()
    assert catalog["disclaimer"] == DISCLAIMER
    dates = [d["date"] for d in catalog["days"]]
    assert dates == sorted(dates, reverse=True)
    assert "2026-11-20" in dates and "2026-11-21" in dates
    for day in catalog["days"]:
        for item in day["items"]:
            assert item["sources"], item["id"]
            for h in item.get("handles") or []:
                assert h["role"] in sweeps.PUBLISHABLE_ROLES


def test_item_without_source_is_refused():
    catalog = sweeps.load()
    catalog["days"][0]["items"].append({
        "id": "no-source",
        "kind": "news",
        "title": "Untitled",
        "summary": "A farmer and his wife were attacked.",
        "sources": [],
    })
    fails = sweeps.validate(catalog)
    assert any("every fact needs a reference" in f for f in fails)


def test_private_handle_is_refused():
    catalog = sweeps.load()
    catalog["days"][0]["items"].append({
        "id": "private-handle",
        "kind": "news",
        "title": "A resident reports an incident",
        "summary": "A farmer and his wife were attacked.",
        "handles": [{"handle": "SomeNeighbour", "role": "private", "display": "@SomeNeighbour"}],
        "sources": [{"title": "SAPS", "url": "https://www.saps.gov.za/services/crimestats.php"}],
    })
    fails = sweeps.validate(catalog)
    assert any("not publishable" in f for f in fails)


def test_unlisted_x_handle_url_is_refused():
    catalog = sweeps.load()
    catalog["days"][0]["items"].append({
        "id": "bad-x",
        "kind": "x-pulse",
        "title": "Pulse",
        "summary": "An unlisted private account is not cited on our page.",
        "handles": [{"handle": "SAPoliceService", "role": "police", "display": "@SAPoliceService"}],
        "sources": [{"title": "unlisted", "url": "https://x.com/SomePrivateUser/status/1"}],
    })
    fails = sweeps.validate(catalog)
    assert any("not a publishable handle" in f for f in fails)


def test_disclaimer_typo_is_refused():
    catalog = sweeps.load()
    catalog["disclaimer"] = "We are not responsible for other people's posts."
    fails = sweeps.validate(catalog)
    assert any("disclaimer" in f for f in fails)


def test_email_in_catalog_is_refused():
    catalog = sweeps.load()
    catalog["days"][0]["summary"] = "Contact a***@example.com for more."
    # Use a real-looking pattern; popia EMAIL_RE will match example.com
    catalog["days"][0]["summary"] = "Write to victim@example.com for more."
    fails = sweeps.validate(catalog)
    assert any("email pattern" in f for f in fails)


def test_daily_sweeps_page_has_controls_and_disclaimer(site):
    html = (site / "daily-sweeps" / "index.html").read_text()
    assert 'id="sweep-day"' in html
    assert 'for="sweep-day"' in html
    assert 'id="sweep-handle"' in html
    assert "Search sweeps by handle" in html
    assert 'role="search"' in html
    assert 'aria-live="polite"' in html
    assert DISCLAIMER in html
    assert "a farmer and his wife" in html
    assert "Public figures, officials, police and media accounts can be named" in html
    assert "DRAFT" in html
    assert "noindex" in html
    assert "default-src 'none'" in html
    assert "script-src 'self'" in html
    assert 'src="/assets/sweeps.js"' in html
    assert 'src="/assets/sweeps-data.js"' in html
    assert 'id="sweep-results"' in html
    # Build-time editions are in the HTML (usable without JavaScript).
    assert "2026-11-21" in html
    assert "Worcester" in html
    assert "https://x.com/SAPoliceService/status/2124081562438303853" in html
    assert "@SAPoliceService" in html
    # No submitting form (CSP form-action 'none').
    assert "<form" not in html.lower()


ALL_PAGES = [
    "index.html",
    "heat-map/index.html",
    "high-profile/index.html",
    "media-gap/index.html",
    "daily-sweeps/index.html",
    "method/index.html",
    "404.html",
]


def test_disclaimer_is_on_every_page(site):
    for rel in ALL_PAGES:
        text = (site / rel).read_text()
        assert DISCLAIMER in text, rel


def test_method_page_states_t704u_rule(site):
    text = (site / "method" / "index.html").read_text()
    assert "a farmer and his wife" in text
    assert DISCLAIMER in text
    assert "Public figures, officials, police and media accounts can be named" in text
    assert "Every fact has a reference" in text


def test_sweeps_data_payload_and_gate(site):
    text = (site / "assets" / "sweeps-data.js").read_text()
    assert text.startswith("window.CW_SWEEPS = ")
    data = json.loads(text[len("window.CW_SWEEPS = "):].rstrip().rstrip(";"))
    assert data["disclaimer"] == DISCLAIMER
    assert data["days"][0]["date"] >= data["days"][-1]["date"]
    fails = sg.check_site(site)
    assert fails == []


def test_home_and_nav_link_to_daily_sweeps(site):
    home = (site / "index.html").read_text()
    assert 'href="/daily-sweeps/"' in home
    assert 'aria-current="page"' in (site / "daily-sweeps" / "index.html").read_text()

def test_empty_days_use_lean_summary():
    catalog = sweeps.load()
    empty = [d for d in catalog["days"] if not d["items"]]
    assert empty, "fixture should include lean days"
    for day in empty:
        assert day["summary"] == sweeps.LEAN_EMPTY_SUMMARY, day["date"]


def test_empty_day_unsourced_summary_is_refused():
    catalog = sweeps.load()
    for day in catalog["days"]:
        if not day["items"]:
            day["summary"] = "A serious incident in a named town was reported, with no fetched source."
            date = day["date"]
            break
    else:
        raise AssertionError("no empty day in fixture")
    fails = sweeps.validate(catalog)
    assert any("generic lean summary" in f and date in f for f in fails), fails


def test_process_wording_in_item_is_refused():
    catalog = sweeps.load()
    for day in catalog["days"]:
        if day["items"]:
            day["items"][0]["summary"] += " This was not recorded in the notes."
            ident = day["items"][0]["id"]
            break
    else:
        raise AssertionError("no sourced day in fixture")
    fails = sweeps.validate(catalog)
    assert any("operational wording" in f and ident in f for f in fails), fails


def test_gate_flags_missing_disclaimer_on_sweeps_page(site_copy):
    path = site_copy / "daily-sweeps" / "index.html"
    path.write_text(path.read_text().replace(DISCLAIMER, "Disclaimer removed."))
    fails = sg.check_site(site_copy, private_names=[])
    assert any("disclaimer" in f and "daily-sweeps" in f for f in fails), fails


def test_gate_flags_missing_disclaimer_on_any_html_page(site_copy):
    path = site_copy / "404.html"
    path.write_text(path.read_text().replace(DISCLAIMER, "Disclaimer removed."))
    fails = sg.check_site(site_copy, private_names=[])
    assert any("disclaimer" in f and "404.html" in f for f in fails), fails


def test_gate_flags_missing_disclaimer_in_sweeps_data(site_copy):
    path = site_copy / "assets" / "sweeps-data.js"
    path.write_text(path.read_text().replace(DISCLAIMER, "Disclaimer removed."))
    fails = sg.check_site(site_copy, private_names=[])
    assert any("disclaimer" in f and "sweeps-data" in f for f in fails), fails

