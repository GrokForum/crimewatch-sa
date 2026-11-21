"""Ingest the official SAPS quarterly workbook (RAW Data sheet) and emit CSVs.

Usage: python pipeline/ingest_saps_xlsx.py [xlsx] [outdir]

This script does not fetch or publish. The caller may download the official
workbook from SOURCE_URL to the default path (or set SAPS_Q2_XLSX) first, and
must verify it against data/manifest.json (the sha256 pin is bumped only by a
reviewed change).

Outputs:
  saps_q2_2026_27_long.csv       one row per comp level x area x crime category
  stations_q2_2026_27_layers.csv one row per station, menu-layer columns
  districts_q2_2026_27_layers.csv one row per police district (official District rows)

Count columns (q2_2025, q2_2026) must be numeric. A blank or non-numeric cell
in those official columns is a hard failure (exit 1). It is not filled with 0.

Legitimate blanks are only the heat-map layers SAPS does not publish at
station level (gangs, political, farm). Those columns are written as explicit
nulls, not zero. See pipeline/README.md.
"""
import os
import sys
from pathlib import Path
import pandas as pd

from provinces import UnknownProvinceError, normalise_geo

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
STATION_KEY = ("station", "province")

# Menu layers. None = no station-level official series in this release
# (written as explicit nulls, not zero).
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

UNPUBLISHED_LAYERS = tuple(name for name, cat in LAYERS.items() if cat is None)


class IngestError(Exception):
    """Bad input in the official workbook or a broken station key."""


def coerce_count_column(series: pd.Series, name: str) -> pd.Series:
    """Return an int series, or raise if any cell is blank or non-numeric."""
    converted = pd.to_numeric(series, errors="coerce")
    bad = converted.isna()
    if bad.any():
        samples = series[bad].head(5).tolist()
        raise IngestError(
            f"bad or non-numeric cells in {name} ({int(bad.sum())} rows), "
            f"examples={samples!r}"
        )
    return converted.astype(int)


def load_raw(xlsx=DEFAULT_XLSX) -> pd.DataFrame:
    df = pd.read_excel(xlsx, sheet_name="RAW Data", header=2)
    df.columns = [" ".join(str(c).split()) for c in df.columns]
    df = df[df["Comp level"].isin(["Station", "District", "Province", "National"])].copy()
    keep = ["Comp level", "Station", "District", "Province", "Crime_Category", Q25, Q26]
    df = df[keep].rename(columns={"Comp level": "level", "Station": "area", "Crime_Category": "category",
                                  Q25: "q2_2025", Q26: "q2_2026"})
    for c in ("q2_2025", "q2_2026"):
        df[c] = coerce_count_column(df[c], c)
    df["count_diff"] = df["q2_2026"] - df["q2_2025"]
    try:
        df = normalise_geo(df)
    except UnknownProvinceError as exc:
        raise IngestError(str(exc)) from exc
    return df


def _assert_unique_station_key(frame: pd.DataFrame, context: str) -> None:
    if frame.duplicated(subset=list(STATION_KEY)).any():
        dups = frame.loc[frame.duplicated(subset=list(STATION_KEY), keep=False), list(STATION_KEY)]
        raise IngestError(f"duplicate station+province key in {context}: {dups.head(10).to_dict('records')}")


def station_layers(df: pd.DataFrame) -> pd.DataFrame:
    st = df[df["level"] == "Station"]
    base = st[["area", "District", "Province"]].drop_duplicates().rename(
        columns={"area": "station", "District": "district", "Province": "province"})
    _assert_unique_station_key(base, "station list")
    for layer, cat in LAYERS.items():
        if cat is None:
            base[layer] = pd.NA
            continue
        sub = st[st["category"] == cat][["area", "Province", "q2_2026", "q2_2025"]].rename(
            columns={"area": "station", "Province": "province",
                     "q2_2026": layer, "q2_2025": f"{layer}_q2_2025"})
        _assert_unique_station_key(sub, f"{layer} series")
        base = base.merge(sub, on=list(STATION_KEY), how="left")
    _assert_unique_station_key(base, "station layers")
    base["period"] = "Jul-Sep 2026"
    base["source_url"] = SOURCE_URL
    base["note"] = ("Counts recorded by SAPS (charges counted, not court findings). gangs, political and farm "
                    "have no official station-level series in this release: left blank, not zero.")
    return base.sort_values(["province", "district", "station"]).reset_index(drop=True)


def _district_key(name) -> str:
    """Official district names differ only in letter case between row types."""
    return " ".join(str(name).split()).casefold()


def district_layers(df: pd.DataFrame) -> pd.DataFrame:
    """One row per police district from the workbook's own District rows.

    Province comes from the station rows of that district (each district sits in
    exactly one province). Values are the official District-row counts, not sums
    of station rows; dq_check compares the two.
    """
    st = df[df["level"] == "Station"]
    dist = df[df["level"] == "District"].copy()
    prov_of = (st.assign(key=st["District"].map(_district_key))[["key", "Province"]]
               .drop_duplicates())
    if prov_of["key"].duplicated().any():
        raise IngestError("a police district maps to more than one province")
    names = (st.assign(key=st["District"].map(_district_key))[["key", "District"]]
             .drop_duplicates("key"))
    dist["key"] = dist["area"].map(_district_key)
    unknown = sorted(set(dist["key"]) - set(prov_of["key"]))
    if unknown:
        raise IngestError(f"district rows with no stations: {unknown}")
    base = names.merge(prov_of, on="key").rename(columns={"District": "district", "Province": "province"})
    for layer, cat in LAYERS.items():
        if cat is None:
            base[layer] = pd.NA
            continue
        sub = dist[dist["category"] == cat][["key", "q2_2026", "q2_2025"]].rename(
            columns={"q2_2026": layer, "q2_2025": f"{layer}_q2_2025"})
        if sub["key"].duplicated().any():
            raise IngestError(f"duplicate district rows for {cat}")
        base = base.merge(sub, on="key", how="left")
    base = base.drop(columns="key")
    base["period"] = "Jul-Sep 2026"
    base["source_url"] = SOURCE_URL
    return base.sort_values(["province", "district"]).reset_index(drop=True)


def main(argv):
    xlsx = Path(argv[1]) if len(argv) > 1 else DEFAULT_XLSX
    out = Path(argv[2]) if len(argv) > 2 else DEFAULT_OUT
    try:
        out.mkdir(parents=True, exist_ok=True)
        df = load_raw(xlsx)
        df.to_csv(out / "saps_q2_2026_27_long.csv", index=False)
        lay = station_layers(df)
        lay.to_csv(out / "stations_q2_2026_27_layers.csv", index=False)
        dl = district_layers(df)
        dl.to_csv(out / "districts_q2_2026_27_layers.csv", index=False)
    except IngestError as exc:
        print(f"FAIL ingest: {exc}", file=sys.stderr)
        return 1
    print(f"long rows={len(df)} stations={len(lay)} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
