"""Data-quality gate: compare workbook totals with figures typed from the official PDF.

Exit code 0 = all hard checks pass. Known disputed totals are reported, not failed.
"""
import json
import sys
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
EXPECTED = json.loads((HERE / "expected_pdf_q2_2026_27.json").read_text())


def checks(long_df: pd.DataFrame):
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
    return res


def disputed(long_df: pd.DataFrame):
    st = long_df[(long_df["level"] == "Station") & (long_df["category"] == "Murder")]
    out = {}
    for p in EXPECTED["province_murder_q2_2026"]:
        if p.startswith("_"):
            continue
        out[p] = (int(st[st["Province"] == p]["q2_2026"].sum()), EXPECTED["province_murder_q2_2026"][p])
    return {p: v for p, v in out.items() if v[0] != v[1]}


def main(path):
    df = pd.read_csv(path)
    fails = 0
    for name, got, exp in checks(df):
        ok = got == exp
        fails += not ok
        print(("PASS" if ok else "FAIL"), name, got, exp)
    for p, (stsum, summ) in disputed(df).items():
        print(f"DISPUTED {p} murder: station rows sum {stsum} vs provincial summary {summ}")
    print("fails:", fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else HERE.parent / "data/saps_q2_2026_27_long.csv"))
