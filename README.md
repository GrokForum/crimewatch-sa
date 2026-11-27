# CrimeWatch SA

South African crime figures, official and civil-society counts side by side, with victims first.

Every figure is attributed to a source. No number is invented; an estimate is labelled as one. Fact labels follow the [MediaWatch SA methodology](https://github.com/GrokForum/mediawatch-sa/blob/main/docs/METHODOLOGY.md): **Proven**, **Established**, **Alleged**, **Disputed**, and **Not established**. Official SAPS and NPA wording and statistics record what was charged or counted, not what a court found.

## How the work is checked

AI research assistants working under a human owner draft the figures. Any derived number is AI-derived arithmetic from the official counts and is labelled that way.

The work is checked by a researcher, by source reviewers, and by an independent critic. An external auditor, independent of the researcher, source reviewers and independent critic, audits the published site and repo. The audit is advisory and doesn't block publishing. Findings are raised as public issues on this repository, and each one we act on is noted in the commit history with the commit that fixed it.

This repository is public. The site it generates is a DRAFT: every page carries a visible DRAFT banner and a robots `noindex` meta, and `robots.txt` disallows all crawling. Nothing is deployed or published until the owner gives a named GO.

## Pipeline

The research pipeline ingests the official SAPS quarterly workbook, writes official-derived CSVs, and runs a data-quality gate that compares workbook totals with figures typed from the official PDF. See `pipeline/README.md`.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
# Optional: download the official workbook (TLS verified against the reviewed
# CA bundle, then checked against the manifest pin)
.venv/bin/python pipeline/fetch_official.py workbook
.venv/bin/python pipeline/ingest_saps_xlsx.py
.venv/bin/python -m pytest -q
.venv/bin/python pipeline/dq_check.py
.venv/bin/python pipeline/popia_gate.py
.venv/bin/python pipeline/build_site.py build/site
.venv/bin/python pipeline/site_gate.py build/site
```

Tests also run against the committed official-derived CSVs when the workbook is not present. The workbook's size and sha256 are pinned in `data/manifest.json`; the pin is bumped only by a reviewed change, and a mismatch fails closed.

A certificate or TLS error in the collector is never silent: it prints a GitHub Actions `::error` annotation and a `FAIL` line on stderr, appends a JSON line to `logs/collector.log`, and fails the step (exit 2).

A nightly workflow (00:00 UTC, 02:00 SAST) sets up Python, installs pinned dependencies, downloads and verifies the workbook, re-ingests and checks the derived files still match their pins, runs pytest, the data-quality gate and the POPIA data gate, builds the static site and runs the site POPIA and hygiene gate on the generated pages. It has no deploy, publish or Pages step, and no secrets.

## Site

`pipeline/build_site.py` generates a static site into `build/site/` (not committed): a home page, a zoomable heat map (province, police district and station level; GBV, kidnapping, murder, attempted murder and the 17 serious crimes; gang, political and farm layers shown as having no station-level SAPS data, not as zeros), a high-profile crimes page, a media-vs-official page, a daily-sweeps page (day drop-down and handle search, built at compile time from `data/sweeps.json`) and a method page. Content lives in `pipeline/site_content.py`; every external link must be on its reviewed source register or a validated daily-sweep citation. The pages use no third-party requests and a strict Content-Security-Policy. Province boundaries are made with Natural Earth (public domain).

`pipeline/site_gate.py` fails the build if a page lacks an effective DRAFT banner, `noindex` or CSP (a `noindex` meta inside `<template>` or after `<body>` does not count); links outside the source register; uses a label other than the five; or contains an ID number, phone number, email address (including HTML-entity encodings such as `&#64;`), a local path, an internal name, an excluded incident aggregate, or a name from an optional private names list kept outside the repository. The approved privacy contact is privacy@grokforum.site. Every page carries this disclaimer: “We are not responsible for anything published by anyone else, including personal information.”

Indexing is a deploy-time opt-in: `CW_INDEXABLE=1` and `CW_SITE_HOST=crimewatch.grokforum.site` must both be set, and any other host is refused. The default, and the nightly workflow, stay at `noindex` and `robots.txt` `Disallow: /`. The opt-in is never set in CI.

## Data

| Path | What |
|---|---|
| `data/stations_q2_2026_27_layers.csv` | One row per police station (1,174 stations). Official counts for the heat-map layers SAPS publishes at station level (GBV, kidnapping, murder and the 17 serious-crime total). Gang, political and farm columns are blank, not zero: SAPS does not publish those series at station level. |
| `data/saps_q2_2026_27_long.csv` | Official counts at station, district, province and national level, used by the data-quality gate. |
| `data/districts_q2_2026_27_layers.csv` | The workbook's own police-district rows (55 districts) for the same layers. Sums match the national totals; two districts (Amathole, City of Cape Town) differ from the sum of their station rows and are listed as Disputed. |
| `data/province_population_saps_2021series.csv` | Provincial populations printed on slide 21 of the official Q2 pack (2021 mid-year series), used for rates per 100,000. |
| `data/geo/za_provinces.geojson` | Province outlines, mainland, simplified to 3 decimals from Natural Earth v5.1.2 (public domain) by `tools/extract_provinces.py`. |

The derived files' sizes and sha256 are pinned in `data/manifest.json`. The CSVs are aggregates derived from the official SAPS Q2 2026/27 workbook. They do not name private people. The raw workbook is not stored in this repository; the nightly workflow downloads it from saps.gov.za.

## Change process

DEV work happens on a branch. A change is reviewed before it is merged. Rollback is git. Publishing stays off until the owner gives a named GO.
