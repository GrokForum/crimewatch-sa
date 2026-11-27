"""Build the static CrimeWatch SA site from official-derived data and reviewed content.

Usage: python pipeline/build_site.py [outdir]     (default: build/site)

Output is deterministic (no timestamps), has no secrets and no third-party
requests. By default every page carries a robots noindex meta, a visible DRAFT
banner, and robots.txt Disallow: /. Indexing is a deploy-time opt-in only:
CW_INDEXABLE=1 and CW_SITE_HOST=crimewatch.grokforum.site must both be set;
any other host is refused. The opt-in is never set in CI. Nothing here deploys
or publishes. The daily register flag (CW_DAILY_REGISTER) defaults to off. A flag-on build, or a public /daily/ build, is refused unless answers (a) and (b) and a public-page GO are all recorded in pipeline/daily_preconditions.json.
"""
import hashlib
import html
import json
import math
import os
import shutil
import sys
from pathlib import Path

import pandas as pd

import daily_release as dr
import site_content as C
import sweeps

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ASSETS_SRC = ROOT / "site_assets"
DEFAULT_OUT = ROOT / "build" / "site"

LAYERS = [
    # key, menu label, available at station level
    ("gbv_sexual_offences", "GBV: sexual offences", True),
    ("gbv_rape", "GBV: rape", True),
    ("kidnapping", "Kidnapping", True),
    ("murder", "Murder", True),
    ("attempted_murder", "Attempted murder", True),
    ("all_17_serious", "ALL: 17 community-reported serious crimes", True),
    ("gangs", "Gang violence", False),
    ("political", "Political killings", False),
    ("farm", "Farm attacks", False),
]
LAYER_TO_CATEGORY = {
    "gbv_sexual_offences": "Sexual offences",
    "gbv_rape": "Rape",
    "kidnapping": "Kidnapping",
    "murder": "Murder",
    "attempted_murder": "Attempted murder",
    "all_17_serious": "17 Community reported serious Crime",
}
NO_STATION_DATA = "No station-level SAPS data"

PAGES = [
    ("/", "Home"),
    ("/heat-map/", "Heat map"),
    ("/high-profile/", "High-profile crimes"),
    ("/media-gap/", "Media vs official"),
    ("/daily-sweeps/", "Daily sweeps"),
    ("/method/", "Method and sources"),
]

CSP = ("default-src 'none'; style-src 'self'; script-src 'self'; img-src 'self'; "
       "base-uri 'none'; form-action 'none'")

APPROVED_SITE_HOST = "crimewatch.grokforum.site"
PRIVACY_EMAIL = "privacy@grokforum.site"


class ContentError(Exception):
    pass


def resolve_indexable(indexable=None, host=None) -> bool:
    """Return True only for the explicit approved opt-in. Fail closed otherwise."""
    if indexable is None:
        raw = os.environ.get("CW_INDEXABLE", "")
        if raw in ("", "0", "false", "no"):
            return False
        if raw != "1":
            raise SystemExit(
                f"FAIL CW_INDEXABLE={raw!r} is not accepted (set to 1 to opt in, or leave unset)"
            )
        indexable = True
    if not indexable:
        return False
    resolved = os.environ.get("CW_SITE_HOST", "") if host is None else host
    if resolved != APPROVED_SITE_HOST:
        raise SystemExit(
            f"FAIL indexing refused: CW_SITE_HOST must be {APPROVED_SITE_HOST} (got {resolved!r})"
        )
    return True



# ---------------------------------------------------------------- helpers
def e(text) -> str:
    return html.escape(str(text), quote=True)


def src_links(ids) -> str:
    if not ids:
        raise ContentError("figure without a source")
    parts = []
    for sid in ids:
        if sid not in C.SOURCES:
            raise ContentError(f"unknown source id {sid!r}")
        title, url, _kind = C.SOURCES[sid]
        parts.append(f'<a href="{e(url)}" rel="noopener noreferrer">{e(title)}</a>')
    return '<span class="src">Source: ' + "; ".join(parts) + "</span>"


def label_tag(label: str) -> str:
    if label not in C.LABELS:
        raise ContentError(f"fact label {label!r} is not one of {C.LABELS}")
    slug = label.lower().replace(" ", "-")
    return f'<span class="label label-{slug}" data-label="{e(label)}">{e(label)}</span>'


def page(path: str, title: str, body: str, scripts=(), indexable: bool = False) -> str:
    nav = "".join(
        f'<li><a href="{href}"{" aria-current=\"page\"" if href == path else ""}>{e(name)}</a></li>'
        for href, name in PAGES
    )
    script_tags = "".join(f'<script src="{s}" defer></script>' for s in scripts)
    robots = "index, follow" if indexable else "noindex, nofollow"
    return f"""<!doctype html>
<html lang="en-ZA">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="{robots}">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="no-referrer">
<link rel="stylesheet" href="/assets/site.css">
<title>DRAFT · {e(title)} · CrimeWatch SA</title>
{script_tags}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="draft" role="note"><p><strong>DRAFT.</strong> Not yet published. Edition of {e(C.EDITION)}. Official and civil-society figures are shown side by side and are never added together. Private victims and suspects appear only as totals.</p></div>
<header><p class="brand"><a href="/">CrimeWatch SA</a></p>
<nav aria-label="Site"><ul>{nav}</ul></nav></header>
<main id="main">
{body}
</main>
<footer><p>Fact labels: Proven, Established, Alleged, Disputed, Not established (<a href="{e(C.SOURCES['methodology'][1])}" rel="noopener noreferrer">MediaWatch SA methodology</a>). Code, data and public issues: <a href="{e(C.SOURCES['repo'][1])}" rel="noopener noreferrer">GrokForum/crimewatch-sa</a>. Map boundaries made with Natural Earth.</p>
<p>Privacy contact: <a href="mailto:{PRIVACY_EMAIL}">{PRIVACY_EMAIL}</a>.</p>
<p class="disclaimer">{e(sweeps.DISCLAIMER)}</p></footer>
</body>
</html>
"""


def fmt(n) -> str:
    return f"{int(n):,}"


# ---------------------------------------------------------------- data
def load_frames():
    long_df = pd.read_csv(DATA / "saps_q2_2026_27_long.csv")
    stations = pd.read_csv(DATA / "stations_q2_2026_27_layers.csv")
    districts = pd.read_csv(DATA / "districts_q2_2026_27_layers.csv")
    pop = pd.read_csv(DATA / "province_population_saps_2021series.csv")
    geo = json.loads((DATA / "geo" / "za_provinces.geojson").read_text())
    return long_df, stations, districts, pop, geo


def province_values(long_df, pop):
    prov = long_df[long_df["level"] == "Province"]
    out = {}
    for _, r in pop.iterrows():
        name = r["province"]
        vals = {}
        for key, cat in LAYER_TO_CATEGORY.items():
            row = prov[(prov["area"] == name) & (prov["category"] == cat)]
            if len(row) != 1:
                raise ContentError(f"missing province row {name} {cat}")
            q26, q25 = int(row["q2_2026"].iloc[0]), int(row["q2_2025"].iloc[0])
            vals[key] = [q26, q25, round(q26 / int(r["population"]) * 100_000, 1)]
        out[name] = {"population": int(r["population"]), "values": vals}
    return out


def map_payload(long_df, stations, districts, pop):
    known = json.loads((ROOT / "pipeline" / "expected_pdf_q2_2026_27.json").read_text())["known_district_disputed"]
    provinces = province_values(long_df, pop)
    avail = [k for k, _, ok in LAYERS if ok]
    dist_rows = []
    for _, r in districts.iterrows():
        dist_rows.append({"d": r["district"], "p": r["province"],
                          "v": {k: [int(r[k]), int(r[f"{k}_q2_2025"])] for k in avail}})
    st_rows = []
    for _, r in stations.iterrows():
        st_rows.append({"s": r["station"], "d": r["district"], "p": r["province"],
                        "v": {k: [int(r[k]), int(r[f"{k}_q2_2025"])] for k in avail}})
    disputes = {k: [v["district_row"], v["station_rows_sum"]] for k, v in known.items()}
    return {
        "edition": C.EDITION,
        "period": "Jul–Sep 2026 (vs Jul–Sep 2025)",
        "source": C.SOURCES["saps_q2_xlsx"][1],
        "layers": [{"key": k, "label": lab, "available": ok} for k, lab, ok in LAYERS],
        "noData": NO_STATION_DATA,
        "provinces": provinces,
        "districts": dist_rows,
        "stations": st_rows,
        "districtDisputes": disputes,
    }


def project_paths(geo):
    """Equirectangular projection scaled by cos(mean latitude); returns (paths, viewBox)."""
    pts = [pt for f in geo["features"] for poly in f["geometry"]["coordinates"] for ring in poly for pt in ring]
    lon0, lon1 = min(p[0] for p in pts), max(p[0] for p in pts)
    lat0, lat1 = min(p[1] for p in pts), max(p[1] for p in pts)
    kx = math.cos(math.radians((lat0 + lat1) / 2))
    scale = 900 / ((lon1 - lon0) * kx)

    def xy(p):
        return (round((p[0] - lon0) * kx * scale, 1), round((lat1 - p[1]) * scale, 1))

    paths = {}
    for f in geo["features"]:
        d = []
        for poly in f["geometry"]["coordinates"]:
            for ring in poly:
                coords = [xy(p) for p in ring]
                d.append("M" + "L".join(f"{x},{y}" for x, y in coords) + "Z")
        paths[f["properties"]["province"]] = "".join(d)
    height = round((lat1 - lat0) * scale, 1)
    return paths, f"0 0 900 {height}"


# ---------------------------------------------------------------- pages
def home_page(indexable=False):
    cards = []
    for value, lab, detail, flabel, srcs in C.HEADLINES:
        cards.append(f'<div class="metric"><p class="value">{e(value)}</p><p class="mlabel">{e(lab)}</p>'
                     f'<p>{e(detail)} {label_tag(flabel)}</p>{src_links(srcs)}</div>')
    body = f"""<h1>CrimeWatch SA</h1>
<p class="lede">South African crime figures, official and civil-society counts side by side, with victims first. Every figure links to its source and carries a fact label.</p>
<h2>Latest official quarter (Jul–Sep 2026)</h2>
<p>Counts below are what SAPS recorded or counted. They are not a census of every crime that occurred.</p>
<div class="metrics">{''.join(cards)}</div>
<h2>On this site</h2>
<ul>
<li><a href="/heat-map/">Heat map</a>: zoom from South Africa to a province, its police districts and stations, by crime type.</li>
<li><a href="/high-profile/">High-profile crimes</a>: murder, rape, GBV, kidnapping, gang violence, farm and rural violence, political killings and wildlife crime.</li>
<li><a href="/media-gap/">Media vs official</a>: what the official tables emphasise against what the news emphasised, and misreported statistics.</li>
<li><a href="/daily-sweeps/">Daily sweeps</a>: pick a day, or search official, police and media handles, in the daily editions.</li>
<li><a href="/method/">Method and sources</a>: rules, fact labels, privacy, how the work is checked, and the source register.</li>
</ul>"""
    return page("/", "Official SAPS Q2 2026/27 figures", body, indexable=indexable)


def heat_map_page(payload, paths, viewbox, indexable=False):
    options = "".join(
        f'<option value="{e(k)}"{" selected" if k == "murder" else ""}>{e(lab)}{"" if ok else " (no station-level SAPS data)"}</option>'
        for k, lab, ok in LAYERS)
    shapes = "".join(
        f'<path class="prov" data-province="{e(name)}" d="{d}" tabindex="0" role="button" aria-label="{e(name)}"></path>'
        for name, d in sorted(paths.items()))
    rows = []
    for name, info in sorted(payload["provinces"].items()):
        m = info["values"]["murder"]
        rows.append(f"<tr><td>{e(name)}</td><td>{fmt(m[0])}</td><td>{fmt(m[1])}</td><td>{m[2]}</td></tr>")
    no_data = ", ".join(lab for _, lab, ok in LAYERS if not ok)
    body = f"""<h1>Heat map: recorded crime by province, police district and station</h1>
<p>Official SAPS counts for Jul–Sep 2026 against Jul–Sep 2025, from the RAW Data sheet of the official Q2 2026/27 workbook. Choose a crime type, then click a province to zoom in to its police districts and stations. Province shading is a rate per 100,000 people, calculated from SAPS counts and the SAPS population series printed in the same pack (arithmetic; the murder and rape rates match the official ratios). {label_tag('Proven')} {src_links(['saps_q2_xlsx', 'saps_q2'])}</p>
<p>Levels: province, police district and police station only. No street, farm or victim location is mapped. {e(no_data)}: no station-level SAPS data in this release, so those layers are shown empty, not as zeros. Province figures for those crimes are on the <a href="/high-profile/">high-profile page</a>.</p>
<div class="map-tools" hidden>
<label for="layer">Crime type</label> <select id="layer">{options}</select>
<button type="button" id="zoom-in" aria-label="Zoom in">+</button>
<button type="button" id="zoom-out" aria-label="Zoom out">−</button>
<button type="button" id="zoom-reset">All of South Africa</button>
</div>
<div class="map-wrap">
<svg id="map" class="map" viewBox="{viewbox}" data-viewbox="{viewbox}" role="img" aria-label="Map of South Africa's nine provinces shaded by recorded crime rate">{shapes}</svg>
<div id="legend" class="legend" aria-live="polite"></div>
</div>
<p id="nodata" class="nodata" hidden></p>
<section id="detail" aria-live="polite"></section>
<noscript><p>The interactive map needs JavaScript. The table below gives the official provincial murder counts.</p></noscript>
<h2>Murder by province (static table)</h2>
<table><thead><tr><th>Province</th><th>Jul–Sep 2026</th><th>Jul–Sep 2025</th><th>Per 100,000 (arithmetic)</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p class="note">District figures are the workbook's own police-district rows. In Amathole and City of Cape Town the district row and the sum of its station rows differ (labelled Disputed in the district table); national totals still match. Province totals use the workbook's province rows, so the official provincial murder figures are Eastern Cape 1,068 (station rows sum to 1,064) and Western Cape 1,109 (station rows sum to 1,113; an age-and-sex table gives 1,110). See the high-profile page for the Western Cape's three official totals. {label_tag('Disputed')}</p>
<p class="note">Boundaries: {src_links(['natural_earth'])}. No official police-district boundary map was verified, so districts and stations are listed, not drawn.</p>"""
    return page("/heat-map/", "Heat map", body, scripts=("/assets/map-data.js", "/assets/map.js"), indexable=indexable)


def high_profile_page(indexable=False):
    sections = []
    for item in C.HIGH_PROFILE:
        lis = "".join(f"<li>{label_tag(lab)} {e(text)} {src_links(srcs)}</li>" for lab, text, srcs in item["rows"])
        sections.append(f'<section><h2>{e(item["type"])}</h2><ul class="facts">{lis}</ul></section>')
    out_rows = "".join(
        f"<tr><td>{e(a)}</td><td>{e(b)}</td><td>{e(c)}</td><td>{e(d)}</td><td>{e(f)}</td></tr>"
        for a, b, c, d, f in C.OUTCOMES)
    body = f"""<h1>High-profile crimes</h1>
<p>One entry per high-profile crime type. Official counts and civil-society or survey figures sit side by side with their own labels and are never added together. Per-day figures are arithmetic from official counts (92 days in Jul–Sep 2026, 365 in 2025/26).</p>
{''.join(sections)}
<section><h2>Where reported cases end up (2025/26)</h2>
<p>Detection is SAPS's measure on reported charges; conviction rates are a share of finalised court cases, not of all reported crime. The two conviction series are shown side by side and not averaged. {label_tag('Proven')}</p>
<table><thead><tr><th>Crime</th><th>Charges reported</th><th>SAPS detection rate (2024/25)</th><th>SAPS-reported conviction rate</th><th>NPA conviction rate</th></tr></thead><tbody>{out_rows}</tbody></table>
<p>{src_links(C.OUTCOMES_SOURCES)}</p></section>"""
    return page("/high-profile/", "High-profile crimes", body, indexable=indexable)


def media_gap_page(indexable=False):
    rows = "".join(
        f"<tr><td>{e(t)}</td><td>{e(o)}</td><td>{e(m)}</td><td>{e(d)}</td><td>{src_links(s)}</td></tr>"
        for t, o, m, d, s in C.GAP_ROWS)
    fe = "".join(f"<li>{e(t)} {src_links(s)}</li>" for t, s in C.FACTUAL_ERRORS)
    lab, text, srcs = C.FACTUAL_ERROR_OFFICIAL
    body = f"""<h1>Media vs official</h1>
<p>An indicative sample of national crime coverage and public posts, 17–20 November 2026, set against the official Q2 tables. It is not a census and not a scored finding: rows name a MediaWatch driver only as a coverage-pattern observation. Quiet days in the press are not the same as zero crime.</p>
<table><thead><tr><th>Crime type</th><th>Official count (recorded by SAPS)</th><th>What the sample emphasised</th><th>Driver (observation)</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Misreported statistic (factual_error)</h2>
<p>{label_tag(lab)} {e(text)} {src_links(srcs)}</p>
<ul>{fe}</ul>"""
    return page("/media-gap/", "Media vs official", body, indexable=indexable)


def method_page(indexable=False):
    rules = "".join(f"<li>{e(r)}</li>" for r in C.METHOD_RULES)
    popia = "".join(f"<li>{e(r)}</li>" for r in C.METHOD_POPIA)
    checks = "".join(f"<p>{e(r)}</p>" for r in C.CHECKS_TEXT)
    gaps = "".join(f"<li>{e(r)}</li>" for r in C.GAPS_OPEN)
    labels = "".join(f"<li>{label_tag(l)}</li>" for l in C.LABELS)
    reg = "".join(
        f'<tr><td>{e(t)}</td><td>{e(k)}</td><td><a href="{e(u)}" rel="noopener noreferrer">{e(u)}</a></td></tr>'
        for sid, (t, u, k) in C.SOURCES.items())
    body = f"""<h1>Method and sources</h1>
<h2>Rules</h2><ol>{rules}</ol>
<h2>Fact labels</h2><ul class="labels">{labels}</ul>
<h2>Privacy</h2><ul>{popia}</ul>
<h2>How the work is checked</h2>{checks}
<h2>Gaps still open</h2><ul>{gaps}</ul>
<h2>Source register</h2>
<table><thead><tr><th>Source</th><th>Type</th><th>Link</th></tr></thead><tbody>{reg}</tbody></table>"""
    return page("/method/", "Method and sources", body, indexable=indexable)



def _sweep_item_html(item: dict) -> str:
    handles = item.get("handles") or []
    handle_bits = ", ".join(e(h.get("display") or f"@{h['handle']}") for h in handles)
    handle_p = f'<p class="sweep-handles">Handles: {handle_bits}</p>' if handle_bits else ""
    place = f'<p class="note">{e(item["place"])}</p>' if item.get("place") else ""
    lab = label_tag(item["label"]) if item.get("label") else ""
    sources = "".join(
        f'<li><a href="{e(s["url"])}" rel="noopener noreferrer">{e(s["title"])}</a></li>'
        for s in item["sources"]
    )
    return (
        f'<article class="sweep-item" data-id="{e(item["id"])}">'
        f'<h3>{e(item["title"])}</h3>{place}{lab}'
        f'<p>{e(item["summary"])}</p>{handle_p}'
        f'<p class="src">Source:</p><ul class="sweep-sources">{sources}</ul>'
        f"</article>"
    )


def _sweep_day_html(day: dict) -> str:
    items = "".join(_sweep_item_html(item) for item in day["items"])
    if not day["items"]:
        items = '<p class="note">No cited items in this edition.</p>'
    compiled = f' ({e(day["compiled_sast"])})' if day.get("compiled_sast") else ""
    return (
        f'<section class="sweep-day" aria-labelledby="sweep-day-{e(day["date"])}">'
        f'<h2 id="sweep-day-{e(day["date"])}">{e(day["date"])}{compiled}</h2>'
        f'<p class="lede">{e(day["summary"])}</p>{items}</section>'
    )


def daily_sweeps_page(catalog, indexable=False):
    days_html = "".join(_sweep_day_html(day) for day in catalog["days"])
    body = f"""<h1>Daily sweeps</h1>
<p class="lede">Official, media and civil-society items from each CrimeWatch daily sweep, with a fetched source on every fact. Pick a day, or search by a public official, police or media handle.</p>
<p class="disclaimer">{e(sweeps.DISCLAIMER)}</p>
<p>On this page, private people are masked or described anonymously, for example “a farmer and his wife”. Public figures, officials, police and media accounts can be named. We may link to an external page that itself names someone; that exposure is the publisher’s. We only report, mask and reference.</p>
<div class="sweep-tools">
<div class="field"><label for="sweep-day">Day</label>
<select id="sweep-day"></select></div>
<div class="field" role="search" aria-labelledby="sweep-search-label">
<label id="sweep-search-label" for="sweep-handle">Search sweeps by handle</label>
<input id="sweep-handle" type="search" list="sweep-handles" autocomplete="off" spellcheck="false">
<datalist id="sweep-handles"></datalist>
</div>
</div>
<p id="sweep-status" aria-live="polite"></p>
<div id="sweep-results">{days_html}</div>
<noscript><p class="note">The editions are listed above in date order. The day menu and handle search need JavaScript, which runs only from this site.</p></noscript>"""
    return page(
        "/daily-sweeps/",
        "Daily sweeps",
        body,
        scripts=("/assets/sweeps-data.js", "/assets/sweeps.js"),
        indexable=indexable,
    )


def not_found_page(indexable=False):
    return page("/404.html", "Not found", '<h1>Page not found</h1><p><a href="/">Back to the home page</a>.</p>', indexable=indexable)


# ---------------------------------------------------------------- build
def build(out: Path = DEFAULT_OUT, indexable=None, host=None) -> Path:
    # Flag defaults off. A flag-on or /daily/ build is refused without (a), (b)
    # and a recorded public-page GO (RFC-006 §11). The public-page GO is not
    # recorded yet, so a flag-on or /daily/ build currently fails closed.
    # The hook inspects planned rels, the output tree, and source assets
    # itself so a /daily/ path cannot be written if the caller omits args.
    live = resolve_indexable(indexable, host)
    catalog = sweeps.load()
    sweep_payload = sweeps.payload(catalog)
    long_df, stations, districts, pop, geo = load_frames()
    payload = map_payload(long_df, stations, districts, pop)
    paths, viewbox = project_paths(geo)
    robots = "User-agent: *\nAllow: /\n" if live else "User-agent: *\nDisallow: /\n"
    files = {
        "index.html": home_page(indexable=live),
        "heat-map/index.html": heat_map_page(payload, paths, viewbox, indexable=live),
        "high-profile/index.html": high_profile_page(indexable=live),
        "media-gap/index.html": media_gap_page(indexable=live),
        "method/index.html": method_page(indexable=live),
        "daily-sweeps/index.html": daily_sweeps_page(catalog, indexable=live),
        "404.html": not_found_page(indexable=live),
        "robots.txt": robots,
        "assets/map-data.js": "window.CW_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + ";\n",
        "assets/sweeps-data.js": "window.CW_SWEEPS = " + json.dumps(sweep_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + ";\n",
    }
    for name in ("site.css", "map.js", "sweeps.js"):
        files[f"assets/{name}"] = (ASSETS_SRC / name).read_text()
    # Detect /daily/ in planned rels, leftover output, and ASSETS_SRC
    # separately. A source-tree daily page is not copied into `files` before
    # this check, so the source_dirs=[ASSETS_SRC] arm is what catches it.
    dr.assert_build_allowed(rels=files, out=out, source_dirs=[ASSETS_SRC])
    if out.exists():
        shutil.rmtree(out)
    for rel, text in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    manifest = {rel: hashlib.sha256((out / rel).read_bytes()).hexdigest() for rel in sorted(files)}
    (out / "manifest.json").write_text(json.dumps({"edition": C.EDITION, "files": manifest}, indent=2) + "\n")
    return out


def main(argv):
    out = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUT
    try:
        build(out)
    except (ContentError, FileNotFoundError, KeyError, ValueError, dr.DailyReleaseError) as exc:
        print(f"FAIL site build: {exc}", file=sys.stderr)
        return 1
    print(f"site built -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
