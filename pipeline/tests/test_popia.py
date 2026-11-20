from pathlib import Path

import pandas as pd

import ingest_saps_xlsx as ing
import popia_gate as popia


def test_committed_data_passes_popia_gate():
    failures = popia.check_tree(ing.ROOT / "data")
    assert failures == []
    assert popia.main([]) == 0


def test_unlisted_csv_fails_closed(tmp_path):
    path = tmp_path / "farm-attacks-2026.csv"
    pd.DataFrame({"station": ["X"], "count": [1]}).to_csv(path, index=False)
    failures = popia.check_tree(tmp_path)
    assert any("no reviewed column allowlist" in f for f in failures)
    assert popia.main(["popia", str(tmp_path)]) == 1


def test_free_text_column_is_rejected(tmp_path):
    src = ing.ROOT / "data" / "stations_q2_2026_27_layers.csv"
    df = pd.read_csv(src)
    df["narrative"] = "free text"
    path = tmp_path / "stations_q2_2026_27_layers.csv"
    df.to_csv(path, index=False)
    failures = popia.check_file(path)
    assert any("not on the allowlist" in f for f in failures)


def test_email_pattern_is_rejected(tmp_path):
    src = ing.ROOT / "data" / "saps_q2_2026_27_long.csv"
    df = pd.read_csv(src, nrows=5)
    df.loc[0, "area"] = "alert@example.com"
    path = tmp_path / "saps_q2_2026_27_long.csv"
    df.to_csv(path, index=False)
    failures = popia.check_file(path)
    assert any("email pattern" in f for f in failures)


def test_phone_and_id_patterns_are_rejected(tmp_path):
    src = ing.ROOT / "data" / "saps_q2_2026_27_long.csv"
    df = pd.read_csv(src, nrows=5)
    df.loc[0, "area"] = "0821234567"
    path = tmp_path / "saps_q2_2026_27_long.csv"
    df.to_csv(path, index=False)
    assert any("phone pattern" in f for f in popia.check_file(path))
    df.loc[0, "area"] = "8001015009087"
    df.to_csv(path, index=False)
    assert any("identity-number pattern" in f for f in popia.check_file(path))
