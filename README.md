# CrimeWatch SA

South African crime figures, official and civil-society counts side by side, with victims first.

Every figure is attributed to a source. No number is invented; an estimate is labelled as one. Fact labels follow the [MediaWatch SA methodology](https://github.com/GrokForum/mediawatch-sa/blob/main/docs/METHODOLOGY.md): **Proven**, **Established**, **Alleged**, **Disputed**, and **Not established**. Official SAPS and NPA wording and statistics record what was charged or counted, not what a court found.

## How the work is checked

AI research assistants working under a human owner draft the figures. Any derived number is AI-derived arithmetic from the official counts and is labelled that way.

The work is checked by a researcher, by source reviewers, and by an independent critic. An external auditor, independent of the researcher, source reviewers and independent critic, audits the published site and repo. The audit is advisory and doesn't block publishing. Findings are raised as issues on this repository, and each one we act on is noted in the commit history with the commit that fixed it.

This repository is private. Publishing is off. Nothing here is made public until the owner gives a named GO.

## Pipeline

The research pipeline ingests the official SAPS quarterly workbook, writes official-derived CSVs, and runs a data-quality gate that compares workbook totals with figures typed from the official PDF. See `pipeline/README.md`.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
# Optional: download the official workbook (the SAPS TLS chain often fails CA verification)
mkdir -p raw/q2-2026-27
curl -fsSL -k -o raw/q2-2026-27/2026-2027_-_2nd_Quarter_WEB.xlsx \
  https://www.saps.gov.za/services/downloads/2026/2026-2027_-_2nd_Quarter_WEB.xlsx
.venv/bin/python pipeline/ingest_saps_xlsx.py
.venv/bin/python -m pytest -q
.venv/bin/python pipeline/dq_check.py
```

Tests also run against the committed official-derived CSVs when the workbook is not present.

A nightly workflow (00:00 UTC, 02:00 SAST) sets up Python, installs pinned dependencies, downloads the workbook, builds, runs pytest and the data-quality gate. It has no deploy, publish or Pages step, and no secrets.

## Data

| Path | What |
|---|---|
| `data/stations_q2_2026_27_layers.csv` | One row per police station (1,174 stations). Official counts for the heat-map layers SAPS publishes at station level (GBV, kidnapping, murder and the 17 serious-crime total). Gang, political and farm columns are blank, not zero: SAPS does not publish those series at station level. |
| `data/saps_q2_2026_27_long.csv` | Official counts at station, district, province and national level, used by the data-quality gate. |

Both files are aggregates derived from the official SAPS Q2 2026/27 workbook. They do not name private people. The raw workbook is not stored in this repository; the nightly workflow downloads it from saps.gov.za.

## Change process

DEV work happens on a branch. A change is reviewed before it is merged. Rollback is git. Publishing stays off until the owner gives a named GO.
