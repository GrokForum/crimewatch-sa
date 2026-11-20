"""POPIA gate for committed data files.

Fails closed (exit 1) if:
  - a CSV under data/ has no reviewed column allowlist (this covers any future
    incident-level file);
  - a file has a column that is not on its allowlist (free-text columns are
    not allowlisted);
  - a pinned-constant column has a value other than the reviewed constant;
  - any cell matches an identity-number, phone or email pattern.

Official police-station, district and province names, crime-category labels
and integer counts are allowed. Unpublished station layers stay explicit nulls.
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MANIFEST_PATH = DATA_DIR / "manifest.json"

# Patterns aimed at private personal information. Applied to every cell as text.
ID_RE = re.compile(r"\b[0-9]{13}\b")
PHONE_RE = re.compile(r"(?:\+27[0-9]{9}\b|\b0[6-8][0-9]{8}\b)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

PINNED_NOTE = (
    "Counts recorded by SAPS (charges counted, not court findings). "
    "gangs, political and farm have no official station-level series in this "
    "release: left blank, not zero."
)
PINNED_PERIOD = "Jul-Sep 2026"
PINNED_SOURCE_URL = json.loads(MANIFEST_PATH.read_text())["workbook"]["url"]

# Reviewed allowlists. A new CSV under data/ without an entry fails closed.
# No free-text column is listed. `note`, `period` and `source_url` are pinned
# constants, not narrative fields.
ALLOWLIST = {
    "saps_q2_2026_27_long.csv": (
        "level",
        "area",
        "District",
        "Province",
        "category",
        "q2_2025",
        "q2_2026",
        "count_diff",
    ),
    "stations_q2_2026_27_layers.csv": (
        "station",
        "district",
        "province",
        "gbv_sexual_offences",
        "gbv_sexual_offences_q2_2025",
        "gbv_rape",
        "gbv_rape_q2_2025",
        "gangs",
        "kidnapping",
        "kidnapping_q2_2025",
        "political",
        "farm",
        "murder",
        "murder_q2_2025",
        "attempted_murder",
        "attempted_murder_q2_2025",
        "all_17_serious",
        "all_17_serious_q2_2025",
        "period",
        "source_url",
        "note",
    ),
    "districts_q2_2026_27_layers.csv": (
        "district",
        "province",
        "gbv_sexual_offences",
        "gbv_sexual_offences_q2_2025",
        "gbv_rape",
        "gbv_rape_q2_2025",
        "gangs",
        "kidnapping",
        "kidnapping_q2_2025",
        "political",
        "farm",
        "murder",
        "murder_q2_2025",
        "attempted_murder",
        "attempted_murder_q2_2025",
        "all_17_serious",
        "all_17_serious_q2_2025",
        "period",
        "source_url",
    ),
    "province_population_saps_2021series.csv": (
        "province",
        "population",
        "source_url",
        "source_note",
    ),
}

PINNED_POP_URL = "https://www.saps.gov.za/services/downloads/2026/2026-2027_-_2nd_Quarter_WEB.pdf"
PINNED_POP_NOTE = "SAPS Q2 2026/27 pack slide 21 (mid-year population estimates 2021 series)"

PINNED = {
    "stations_q2_2026_27_layers.csv": {
        "period": PINNED_PERIOD,
        "source_url": PINNED_SOURCE_URL,
        "note": PINNED_NOTE,
    },
    "districts_q2_2026_27_layers.csv": {
        "period": PINNED_PERIOD,
        "source_url": PINNED_SOURCE_URL,
    },
    "province_population_saps_2021series.csv": {
        "source_url": PINNED_POP_URL,
        "source_note": PINNED_POP_NOTE,
    },
}

# Boundary files may carry only the official province name per feature.
GEO_PROPERTIES = {"province"}


class PopiaError(Exception):
    pass


def _scan_patterns(path: Path, df: pd.DataFrame, failures: list) -> None:
    for col in df.columns:
        for idx, value in df[col].items():
            if pd.isna(value):
                continue
            text = str(value)
            if ID_RE.search(text):
                failures.append(f"{path.name}:{col}:{idx}: identity-number pattern")
                return
            if PHONE_RE.search(text):
                failures.append(f"{path.name}:{col}:{idx}: phone pattern")
                return
            if EMAIL_RE.search(text):
                failures.append(f"{path.name}:{col}:{idx}: email pattern")
                return


def check_file(path: Path) -> list:
    failures = []
    name = path.name
    if name not in ALLOWLIST:
        return [
            f"{name}: no reviewed column allowlist "
            "(new data files, including incident-level files, fail closed until reviewed)"
        ]
    df = pd.read_csv(path)
    allowed = list(ALLOWLIST[name])
    extra = [c for c in df.columns if c not in allowed]
    missing = [c for c in allowed if c not in df.columns]
    if extra:
        failures.append(f"{name}: columns not on the allowlist (free-text banned): {extra}")
    if missing:
        failures.append(f"{name}: allowlisted columns missing: {missing}")
    for col, expected in PINNED.get(name, {}).items():
        if col in df.columns:
            unexpected = sorted({str(v) for v in df[col].fillna("").unique() if str(v) != expected})
            if unexpected:
                failures.append(f"{name}:{col}: pinned constant departed from the reviewed value")
    _scan_patterns(path, df, failures)
    return failures


def check_geojson(path: Path) -> list:
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        return [f"{path.name}: unreadable boundary file ({exc})"]
    failures = []
    for i, feat in enumerate(doc.get("features", [])):
        extra = set(feat.get("properties", {})) - GEO_PROPERTIES
        if extra:
            failures.append(f"{path.name}:feature {i}: properties not on the allowlist: {sorted(extra)}")
    return failures


def check_tree(data_dir: Path = DATA_DIR) -> list:
    failures = []
    csvs = sorted(data_dir.rglob("*.csv"))
    if not csvs:
        return [f"no CSV files under {data_dir}"]
    for path in csvs:
        failures.extend(check_file(path))
    for path in sorted(data_dir.rglob("*.geojson")):
        failures.extend(check_geojson(path))
    return failures


def main(argv):
    target = Path(argv[1]) if len(argv) > 1 else DATA_DIR
    failures = check_tree(target) if target.is_dir() else check_file(target)
    if failures:
        for item in failures:
            print("FAIL", item)
        return 1
    print("PASS POPIA gate")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
