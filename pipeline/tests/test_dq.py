import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

import dq_check as dq
import ingest_saps_xlsx as ing
from provinces import UnknownProvinceError

LONG_CSV = ing.ROOT / "data" / "saps_q2_2026_27_long.csv"
LAYERS_CSV = ing.ROOT / "data" / "stations_q2_2026_27_layers.csv"
DQ_SCRIPT = Path(dq.__file__).resolve()


@pytest.fixture
def long_df_with_wrong_national_murder(long_df):
    """Fixture that must fail the hard PDF checks."""
    bad = long_df.copy()
    mask = (bad["level"] == "National") & (bad["category"] == "Murder")
    bad.loc[mask, "q2_2026"] = bad.loc[mask, "q2_2026"] + 1
    return bad


def _run_dq(path):
    return subprocess.run(
        [sys.executable, str(DQ_SCRIPT), str(path)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_expected_number_of_checks(long_df):
    res = dq.checks(long_df)
    assert len(res) == dq.EXPECTED_CHECK_COUNT
    assert dq.EXPECTED_CHECK_COUNT == 48


def test_all_hard_checks_match_pdf(long_df):
    bad = [(n, g, e) for n, g, e in dq.checks(long_df) if g != e]
    assert bad == []


def test_hard_check_fixture_must_fail(long_df_with_wrong_national_murder):
    bad = [(n, g, e) for n, g, e in dq.checks(long_df_with_wrong_national_murder) if g != e]
    assert bad, "a mutated national murder total must fail at least one hard check"


def test_known_disputed_is_read(long_df):
    known = dq.EXPECTED["known_disputed"]
    assert known["Western Cape"]["xlsx_station_rows_sum"] == 1113
    assert known["Western Cape"]["provincial_summary"] == 1109
    assert known["Eastern Cape"]["xlsx_station_rows_sum"] == 1064
    assert known["Eastern Cape"]["provincial_summary"] == 1068
    listed, unexpected, missing, mismatched = dq.classify_disputes(long_df)
    assert unexpected == {}
    assert missing == {}
    assert mismatched == {}
    assert listed["Western Cape"] == (1113, 1109)
    assert listed["Eastern Cape"] == (1064, 1068)


def test_wc_murder_dispute_is_reported(long_df):
    d = dq.disputed(long_df)
    assert d["Western Cape"] == (1113, 1109)
    assert d["Eastern Cape"] == (1064, 1068)
    assert set(d) == {"Western Cape", "Eastern Cape"}


def test_unlisted_dispute_is_a_failure(long_df):
    df = long_df.copy()
    mask = (df["level"] == "Station") & (df["category"] == "Murder") & (df["Province"] == "Free State")
    idx = df.index[mask][0]
    df.loc[idx, "q2_2026"] = int(df.loc[idx, "q2_2026"]) + 5
    listed, unexpected, missing, mismatched = dq.classify_disputes(df)
    assert "Free State" in unexpected
    assert "Western Cape" in listed
    assert "Eastern Cape" in listed
    assert missing == {}
    assert mismatched == {}


def test_station_layers_shape(long_df):
    lay = ing.station_layers(long_df)
    assert lay.duplicated(subset=["station", "province"]).sum() == 0
    assert len(lay) == 1174
    for col in ("gangs", "political", "farm"):
        assert lay[col].isna().all()  # not zero: no official station series
    assert int(lay["murder"].sum()) == 5590
    assert int(lay["kidnapping"].sum()) == 4934


def test_spot_check_stations(long_df):
    lay = ing.station_layers(long_df).set_index(["station", "province"])
    assert lay.loc[("Khayelitsha", "Western Cape"), "murder"] == 66
    assert lay.loc[("Delft", "Western Cape"), "murder"] == 66
    assert lay.loc[("Lwandle", "Western Cape"), "murder"] == 48
    assert lay.loc[("Lwandle", "Western Cape"), "murder_q2_2025"] == 15


def test_committed_layers_csv_agrees_with_rebuild(long_df):
    rebuilt = ing.station_layers(long_df).reset_index(drop=True)
    committed = pd.read_csv(LAYERS_CSV).reset_index(drop=True)
    assert list(rebuilt.columns) == list(committed.columns)
    assert len(rebuilt) == len(committed)
    # Compare every column. Official unpublished layers are explicit nulls in
    # the rebuild (pd.NA) and empty cells in the CSV (NaN); treat those as equal.
    for col in rebuilt.columns:
        left = rebuilt[col]
        right = committed[col]
        if pd.api.types.is_numeric_dtype(left) or pd.api.types.is_numeric_dtype(right) or left.isna().any() or right.isna().any():
            pd.testing.assert_series_equal(
                pd.to_numeric(left, errors="coerce"),
                pd.to_numeric(right, errors="coerce"),
                check_names=False,
                check_dtype=False,
            )
        else:
            pd.testing.assert_series_equal(
                left.astype(str),
                right.astype(str),
                check_names=False,
            )


def test_dq_cli_exit_0_and_prints_disputed():
    result = _run_dq(LONG_CSV)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "DISPUTED Western Cape murder:" in result.stdout
    assert "DISPUTED Eastern Cape murder:" in result.stdout
    assert "station rows sum 1113 vs provincial summary 1109" in result.stdout
    assert "station rows sum 1064 vs provincial summary 1068" in result.stdout


def test_dq_cli_nonzero_on_failure(tmp_path, long_df_with_wrong_national_murder):
    path = tmp_path / "bad.csv"
    long_df_with_wrong_national_murder.to_csv(path, index=False)
    result = _run_dq(path)
    assert result.returncode != 0
    assert "FAIL" in result.stdout


def test_dq_cli_nonzero_on_unlisted_dispute(tmp_path, long_df):
    df = long_df.copy()
    mask = (df["level"] == "Station") & (df["category"] == "Murder") & (df["Province"] == "Free State")
    idx = df.index[mask][0]
    df.loc[idx, "q2_2026"] = int(df.loc[idx, "q2_2026"]) + 5
    path = tmp_path / "unlisted.csv"
    df.to_csv(path, index=False)
    result = _run_dq(path)
    assert result.returncode != 0
    assert "FAIL unlisted dispute Free State" in result.stdout
