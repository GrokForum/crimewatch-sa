# CrimeWatch SA pipeline

Ingests the official SAPS quarterly crime workbook, writes official-derived CSVs, and runs a data-quality gate against figures typed from the official PDF.

- `ingest_saps_xlsx.py` reads the official SAPS quarterly workbook (RAW Data sheet) and writes `data/saps_q2_2026_27_long.csv` and `data/stations_q2_2026_27_layers.csv`. It does not fetch or publish. The nightly workflow downloads the workbook first; locally, pass the path or set `SAPS_Q2_XLSX`.
- `dq_check.py` compares workbook totals with figures typed from the official PDF (`expected_pdf_q2_2026_27.json`, with PDF page numbers) and reports known disputed totals without failing them.
- `tests/` is a pytest suite. From the repository root: `python -m pytest -q pipeline/tests`.

The official workbook is not stored in this repository. Download it from the SAPS URL recorded as `SOURCE_URL` in `ingest_saps_xlsx.py`. The SAPS site's TLS certificate chain often fails verification against common CA stores; the nightly workflow documents why it uses `curl -k` and then checks that the file is a large `.xlsx` (ZIP/PK magic bytes).

Station layers: gangs, political and farm are blank (no official station series in this release), not zero. The CSVs are aggregates at police-station or higher levels. They do not name private people.
