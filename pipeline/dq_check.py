"""Data-quality gate: compare workbook totals with figures typed from the official PDF.

Exit code 0 = all hard checks pass and every dispute is in the reviewed
known_disputed list (with matching values). Known disputed totals are printed
as DISPUTED, not failed. An unlisted dispute, a listed dispute that is missing,
or a listed dispute whose values have changed, is a failure (exit 1).
"""
import json
import sys
from pathlib import Path
import pandas as pd

from provinces import UnknownProvinceError, normalise_geo

HERE = Path(__file__).resolve().parent
EXPECTED = json.loads((HERE / "expected_pdf_q2_2026_27.json").read_text())
EXPECTED_CHECK_COUNT = EXPECTED["expected_check_count"]


def _prepared(long_df: pd.DataFrame) -> pd.DataFrame:
    return normalise_geo(long_df)


def checks(long_df: pd.DataFrame):
    long_df = _prepared(long_df)
    res = []
    nat = long_df[long_df["level"] == "National"]
    st = long_df[long_df["level"] == "Station"]
    prov = long_df[long_df["level"] == "Province"]
    for cat, exp in EXPECTED["national"].items():
        n = nat[nat["category"] == cat]
        s = st[st["category"] == cat]
        res.append((f"national {cat} q2_2026 workbook vs PDF p{exp['pdf_page']}",
                    int(n["q2_2026"].sum()), exp["q2_2026"]))
        res.append((f"national {cat} q2_2025 workbook vs PDF p{exp['pdf_page']}",
                    int(n["q2_2025"].sum()), exp["q2_2025"]))
        res.append((f"national {cat} q2_2026 station sum vs PDF", int(s["q2_2026"].sum()), exp["q2_2026"]))
    for key, cat in (("province_murder_q2_2026", "Murder"), ("province_kidnapping_q2_2026", "Kidnapping")):
        for p, v in EXPECTED[key].items():
            if p.startswith("_"):
                continue
            got = int(prov[(prov["category"] == cat) & (prov["area"] == p)]["q2_2026"].sum())
            res.append((f"province {p} {cat} workbook row vs PDF p{EXPECTED[key]['_pdf_page']}", got, v))
    if len(res) != EXPECTED_CHECK_COUNT:
        raise AssertionError(f"expected {EXPECTED_CHECK_COUNT} checks, got {len(res)}")
    return res


def disputed(long_df: pd.DataFrame):
    """Station-row murder sums that differ from the provincial summary, by canonical province."""
    long_df = _prepared(long_df)
    st = long_df[(long_df["level"] == "Station") & (long_df["category"] == "Murder")]
    out = {}
    for p in EXPECTED["province_murder_q2_2026"]:
        if p.startswith("_"):
            continue
        out[p] = (int(st[st["Province"] == p]["q2_2026"].sum()), EXPECTED["province_murder_q2_2026"][p])
    return {p: v for p, v in out.items() if v[0] != v[1]}


def classify_disputes(long_df: pd.DataFrame):
    """Compare observed disputes with the reviewed known_disputed list.

    Returns (listed, unexpected, missing, mismatched) where:
      listed      – observed and matches the reviewed values (print as DISPUTED)
      unexpected  – observed but not in the list (fail)
      missing     – listed but not observed (fail)
      mismatched  – listed but the station-sum / provincial figures changed (fail)
    """
    actual = disputed(long_df)
    known = EXPECTED["known_disputed"]
    listed, unexpected, missing, mismatched = {}, {}, {}, {}
    for p, (stsum, summ) in actual.items():
        if p not in known:
            unexpected[p] = (stsum, summ)
            continue
        exp = (known[p]["xlsx_station_rows_sum"], known[p]["provincial_summary"])
        if (stsum, summ) != exp:
            mismatched[p] = {"got": (stsum, summ), "expected": exp}
        else:
            listed[p] = (stsum, summ)
    for p, info in known.items():
        if p not in actual:
            missing[p] = (info["xlsx_station_rows_sum"], info["provincial_summary"])
    return listed, unexpected, missing, mismatched


def main(path):
    try:
        df = pd.read_csv(path)
        df = _prepared(df)
    except (UnknownProvinceError, FileNotFoundError, ValueError) as exc:
        print(f"FAIL {exc}")
        return 1
    fails = 0
    for name, got, exp in checks(df):
        ok = got == exp
        fails += not ok
        print(("PASS" if ok else "FAIL"), name, got, exp)
    listed, unexpected, missing, mismatched = classify_disputes(df)
    for p, (stsum, summ) in listed.items():
        print(f"DISPUTED {p} murder: station rows sum {stsum} vs provincial summary {summ}")
    for p, (stsum, summ) in unexpected.items():
        fails += 1
        print(f"FAIL unlisted dispute {p} murder: station rows sum {stsum} vs provincial summary {summ}")
    for p, (stsum, summ) in missing.items():
        fails += 1
        print(f"FAIL listed dispute not observed {p} murder: expected {stsum} vs {summ}")
    for p, info in mismatched.items():
        fails += 1
        print(f"FAIL listed dispute values changed {p} murder: got {info['got']} expected {info['expected']}")
    print("fails:", fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else HERE.parent / "data/saps_q2_2026_27_long.csv"))
