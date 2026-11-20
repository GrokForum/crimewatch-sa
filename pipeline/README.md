# CrimeWatch SA pipeline

Ingests the official SAPS quarterly crime workbook, writes official-derived CSVs, and runs a data-quality gate against figures typed from the official PDF.

- `ingest_saps_xlsx.py` reads the official SAPS quarterly workbook (RAW Data sheet) and writes `data/saps_q2_2026_27_long.csv` and `data/stations_q2_2026_27_layers.csv`. It does not fetch or publish. The nightly workflow downloads the workbook first and checks it against the reviewed pin in `data/manifest.json`. Locally, pass the path or set `SAPS_Q2_XLSX`, then run `verify_workbook.py`. Blank or non-numeric cells in the official count columns are a hard failure (exit 1); they are not filled with zero.
- `dq_check.py` compares workbook totals with figures typed from the official PDF (`expected_pdf_q2_2026_27.json`, with PDF page numbers). It asserts a fixed number of hard checks. Known disputed totals listed in `known_disputed` are printed as DISPUTED. An unlisted dispute is a failure.
- `popia_gate.py` checks every CSV under `data/` against a reviewed column allowlist, bans free-text columns, and scans for identity-number, phone and email patterns. A new file without an allowlist, including any future incident-level file, fails closed.
- `tests/` is a pytest suite. From the repository root: `python -m pytest -q`.

The official workbook is not stored in this repository. Download it from the URL in `data/manifest.json`. The SAPS site sends only its leaf certificate, so verification uses the reviewed Sectigo intermediate and root in `ci/certs/saps-chain.pem` (`curl --cacert`, never `curl -k`). `verify_workbook.py` then checks the file against the reviewed size and sha256 pin. The pin is bumped only by a reviewed change.

Station layers: gangs, political and farm are explicit nulls (no official station series in this release), not zero. The CSVs are aggregates at police-station or higher levels. They do not name private people. The `note`, `period` and `source_url` columns on the station file are pinned constants, not free-text fields.
