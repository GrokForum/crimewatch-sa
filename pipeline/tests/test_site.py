"""Tests for the static site generator and the site POPIA/hygiene gate."""
import json
import re
import shutil
from pathlib import Path

import pandas as pd
import pytest

import build_site as bs
import site_content as C
import site_gate as sg

ROOT = bs.ROOT
PAGES = ["index.html", "heat-map/index.html", "high-profile/index.html",
         "media-gap/index.html", "method/index.html"]
# Official SAPS Q2 2026/27 ratios per 100,000 (PDF slides 21 and 43): murder, rape.
OFFICIAL_RATIOS = {
    "Eastern Cape": (16.2, 23.3), "Free State": (6.6, 20.9), "Gauteng": (8.1, 10.1),
    "KwaZulu-Natal": (9.0, 16.8), "Limpopo": (2.6, 16.7), "Mpumalanga": (4.8, 14.3),
    "North West": (5.1, 17.1), "Northern Cape": (6.0, 21.0), "Western Cape": (14.4, 15.1),
}


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    return bs.build(tmp_path_factory.mktemp("site") / "site")


@pytest.fixture
def site_copy(site, tmp_path):
    dst = tmp_path / "site"
    shutil.copytree(site, dst)
    return dst


def map_data(site):
    text = (site / "assets" / "map-data.js").read_text()
    return json.loads(text[len("window.CW_DATA = "):].rstrip().rstrip(";"))


def test_pages_exist(site):
    for rel in PAGES + ["404.html", "robots.txt", "assets/site.css", "assets/map.js", "assets/map-data.js", "manifest.json"]:
        assert (site / rel).is_file(), rel


def test_build_is_deterministic(site, tmp_path):
    other = bs.build(tmp_path / "again")
    for path in sorted(site.rglob("*")):
        if path.is_file():
            rel = path.relative_to(site)
            assert path.read_bytes() == (other / rel).read_bytes(), rel


def test_gate_passes_on_generated_site(site):
    assert sg.check_site(site, private_names=[]) == []


def test_every_page_is_draft_noindex(site):
    for rel in PAGES:
        html = (site / rel).read_text()
        assert '<meta name="robots" content="noindex, nofollow">' in html
        assert "<strong>DRAFT.</strong>" in html
    assert "Disallow: /" in (site / "robots.txt").read_text()


def test_menu_has_required_layers(site):
    html = (site / "heat-map" / "index.html").read_text()
    for key in ["gbv_sexual_offences", "gbv_rape", "kidnapping", "murder", "attempted_murder", "all_17_serious"]:
        assert f'value="{key}"' in html
    for key in ["gangs", "political", "farm"]:
        assert re.search(rf'value="{key}"[^>]*>[^<]*no station-level SAPS data', html), key


def test_gang_political_farm_are_unavailable_not_zero(site):
    d = map_data(site)
    by_key = {l["key"]: l for l in d["layers"]}
    for key in ["gangs", "political", "farm"]:
        assert by_key[key]["available"] is False
    for row in d["stations"] + d["districts"]:
        assert not {"gangs", "political", "farm"} & set(row["v"])
    for info in d["provinces"].values():
        assert not {"gangs", "political", "farm"} & set(info["values"])


def test_levels_are_province_district_station_only(site):
    d = map_data(site)
    assert len(d["provinces"]) == 9
    assert len(d["districts"]) == 55
    assert len(d["stations"]) == 1174
    assert set(d["stations"][0]) == {"s", "d", "p", "v"}


def test_station_values_match_layers_csv(site):
    d = map_data(site)
    st = pd.read_csv(ROOT / "data" / "stations_q2_2026_27_layers.csv")
    assert sum(r["v"]["murder"][0] for r in d["stations"]) == int(st["murder"].sum())
    assert sum(r["v"]["kidnapping"][0] for r in d["stations"]) == int(st["kidnapping"].sum()) == 4934


def test_province_rates_reproduce_official_ratios(site):
    d = map_data(site)
    for prov, (murder, rape) in OFFICIAL_RATIOS.items():
        assert d["provinces"][prov]["values"]["murder"][2] == murder, prov
        assert d["provinces"][prov]["values"]["gbv_rape"][2] == rape, prov


def test_district_disputes_shipped(site):
    d = map_data(site)
    assert d["districtDisputes"]["City of Cape Town District|murder"] == [908, 912]


def test_all_external_links_are_on_the_source_register(site):
    allowed = {u for _t, u, _k in C.SOURCES.values()}
    for rel in PAGES:
        for href in re.findall(r'href="(https?://[^"]+)"', (site / rel).read_text()):
            assert href.replace("&amp;", "&") in allowed, (rel, href)


def test_one_in_nine_is_disputed_and_sadhs_established(site):
    text = (site / "high-profile" / "index.html").read_text()
    assert re.search(r'data-label="Disputed">Disputed</span>[^<]*1 in 9', text)
    assert re.search(r'data-label="Established">Established</span>[^<]*1998', text)


def test_excluded_material_absent(site):
    blob = "".join(p.read_text() for p in site.rglob("*") if p.is_file())
    assert "87 incidents" not in blob
    assert "26 " + "farm murders" not in blob
    for host in ["iol.co.za/news/crime-and-courts/farm", "netwerk24", "maroelamedia"]:
        assert host not in blob


def test_unknown_label_or_source_fails_build(monkeypatch):
    with pytest.raises(bs.ContentError):
        bs.label_tag("Likely")
    with pytest.raises(bs.ContentError):
        bs.src_links(["not-a-source"])
    with pytest.raises(bs.ContentError):
        bs.src_links([])


# ---- failing fixtures for the site gate
def _inject(site, rel, text):
    p = site / rel
    p.write_text(p.read_text().replace("</main>", text + "</main>"))


@pytest.mark.parametrize("snippet, expect", [
    ("<p>contact someone@example.org</p>", "email pattern"),
    ("<p>call 082 555 1234</p>", "phone pattern"),
    ("<p>ID 8001015009087</p>", "identity-number pattern"),
    ("<p>see /work" + "space/crimewatch</p>", "local file-system path"),
    ('<p><a href="https://example.com/x">x</a></p>', "not on the reviewed source register"),
    ('<p><a href="/nope/">x</a></p>', "broken or non-internal link"),
    ('<span data-label="Likely">Likely</span>', "fact label not allowed"),
    ("<script>alert(1)</script>", "inline script"),
    ('<p onclick="x()">x</p>', "inline event handler"),
    ("<p>87 farm-attack incidents in the register</p>", "excluded incident aggregate"),
])
def test_gate_failing_fixtures(site_copy, snippet, expect):
    _inject(site_copy, "method/index.html", snippet)
    fails = sg.check_site(site_copy, private_names=[])
    assert any(expect in f for f in fails), fails


def test_gate_flags_internal_names_by_hash(site_copy):
    import hashlib
    _inject(site_copy, "index.html", "<p>Zebrafinch drafted this</p>")
    banned = {hashlib.sha256(b"zebrafinch").hexdigest()}
    fails = sg.scan_text("index.html", (site_copy / "index.html").read_text(), banned, [])
    assert any("internal or excluded name" in f for f in fails)


def test_gate_private_names_list(site_copy):
    _inject(site_copy, "index.html", "<p>Jane Testcase</p>")
    fails = sg.check_site(site_copy, private_names=["jane testcase"])
    assert any("private names list" in f for f in fails)


def test_gate_missing_noindex_and_draft(site_copy):
    p = site_copy / "media-gap" / "index.html"
    t = p.read_text().replace('<meta name="robots" content="noindex, nofollow">', "")
    t = t.replace("<strong>DRAFT.</strong>", "<strong>Live.</strong>")
    p.write_text(t)
    fails = sg.check_site(site_copy, private_names=[])
    assert any("noindex" in f for f in fails)
    assert any("DRAFT" in f for f in fails)


def test_gate_robots_must_disallow(site_copy):
    (site_copy / "robots.txt").write_text("User-agent: *\nAllow: /\n")
    assert any("robots.txt" in f for f in sg.check_site(site_copy, private_names=[]))


def test_gate_map_schema_and_unavailable_layers(site_copy):
    p = site_copy / "assets" / "map-data.js"
    d = map_data(site_copy)
    d["stations"][0]["victim"] = "x"
    for l in d["layers"]:
        if l["key"] == "farm":
            l["available"] = True
    p.write_text("window.CW_DATA = " + json.dumps(d) + ";\n")
    fails = sg.check_site(site_copy, private_names=[])
    assert any("row keys differ" in f for f in fails)
    assert any("farm layer marked available" in f for f in fails)


def test_banned_hash_file_has_no_plain_names():
    text = sg.BANNED_HASHES_FILE.read_text()
    body = [ln for ln in text.splitlines() if not ln.startswith("#")]
    assert body and all(re.fullmatch(r"[0-9a-f]{64}", ln) for ln in body)


def test_repo_public_text_has_no_internal_names_or_local_paths():
    banned = sg.load_banned_hashes()
    skip_dirs = {".git", ".venv", "build", "raw", "logs", "__pycache__", ".pytest_cache"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or skip_dirs & set(path.relative_to(ROOT).parts):
            continue
        if path.suffix not in {".py", ".md", ".json", ".yml", ".yaml", ".txt", ".csv", ".css", ".js", ".ini", ".cfg", ".toml", ""}:
            continue
        if path.name == "banned_terms.sha256":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = path.relative_to(ROOT).as_posix()
        assert not sg.PATH_RE.search(text) or path.name in {"site_gate.py"}, rel
        fails = sg.scan_text(rel, text, banned, [])
        assert not any("internal or excluded name" in f for f in fails), rel
