"""Ingest the official SAPS quarterly workbook (RAW Data sheet) and emit CSVs.

Usage: python pipeline/ingest_saps_xlsx.py [xlsx] [outdir]

This script does not fetch or publish. The caller may download the official
workbook from SOURCE_URL to the default path (or set SAPS_Q2_XLSX) first.

Outputs:
  saps_q2_2026_27_long.csv       one row per comp level x area x crime category
  stations_q2_2026_27_layers.csv one row per station, menu-layer columns
"""
import os
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_XLSX = Path(
    os.environ.get(
        "SAPS_Q2_XLSX",
        ROOT / "raw/q2-2026-27/2026-2027_-_2nd_Quarter_WEB.xlsx",
    )
)
DEFAULT_OUT = ROOT / "data"
SOURCE_URL = "https://www.saps.gov.za/services/downloads/2026/2026-2027_-_2nd_Quarter_WEB.xlsx"
Q25 = "July 2025 to September 2025"
Q26 = "July 2026 to September 2026"

# Menu layers. None = no station-level official series in this release.
LAYERS = {
    "gbv_sexual_offences": "Sexual offences",
    "gbv_rape": "Rape",
    "gangs": None,          # gang-related counts are a national/provincial sample only
    "kidnapping": "Kidnapping",
    "political": None,      # SAPS publishes no political-killing station series
    "farm": None,           # farm/rural counts are provincial only in the PDF
    "murder": "Murder",
    "attempted_murder": "Attempted murder",
    "all_17_serious": "17 Community reported serious Crime",
}


def load_raw(xlsx=DEFAULT_XLSX) -> pd.DataFrame:
    df = pd.read_excel(xlsx, sheet_name="RAW Data", header=2)
    df.columns = [" ".join(str(c).split()) for c in df.columns]
    df = df[df["Comp level"].isin(["Station", "District", "Province", "National"])].copy()
    keep = ["Comp level", "Station", "District", "Province", "Crime_Category", Q25, Q26]
    df = df[keep].rename(columns={"Comp level": "level", "Station": "area", "Crime_Category": "category",
                                  Q25: "q2_2025", Q26: "q2_2026"})
    for c in ("q2_2025", "q2_2026"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    df["count_diff"] = df["q2_2026"] - df["q2_2025"]
    return df


def station_layers(df: pd.DataFrame) -> pd.DataFrame:
    st = df[df["level"] == "Station"]
    base = st[["area", "District", "Province"]].drop_duplicates().rename(
        columns={"area": "station", "District": "district", "Province": "province"})
    for layer, cat in LAYERS.items():
        if cat is None:
            base[layer] = pd.NA
            continue
        sub = st[st["category"] == cat][["area", "q2_2026", "q2_2025"]].rename(
            columns={"area": "station", "q2_2026": layer, "q2_2025": f"{layer}_q2_2025"})
        base = base.merge(sub, on="station", how="left")
    base["period"] = "Jul-Sep 2026"
    base["source_url"] = SOURCE_URL
    base["note"] = ("Counts recorded by SAPS (charges counted, not court findings). gangs, political and farm "
                    "have no official station-level series in this release: left blank, not zero.")
    return base.sort_values(["province", "district", "station"]).reset_index(drop=True)


def main(argv):
    xlsx = Path(argv[1]) if len(argv) > 1 else DEFAULT_XLSX
    out = Path(argv[2]) if len(argv) > 2 else DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    df = load_raw(xlsx)
    df.to_csv(out / "saps_q2_2026_27_long.csv", index=False)
    lay = station_layers(df)
    lay.to_csv(out / "stations_q2_2026_27_layers.csv", index=False)
    print(f"long rows={len(df)} stations={len(lay)} -> {out}")


if __name__ == "__main__":
    main(sys.argv)
