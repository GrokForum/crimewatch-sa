from pathlib import Path
import pandas as pd
import pytest

import ingest_saps_xlsx as ing
import dq_check as dq

LONG_CSV = ing.ROOT / "data" / "saps_q2_2026_27_long.csv"
LAYERS_CSV = ing.ROOT / "data" / "stations_q2_2026_27_layers.csv"


def _xlsx_available() -> bool:
    return Path(ing.DEFAULT_XLSX).is_file()


@pytest.fixture(scope="session")
def long_df():
    if _xlsx_available():
        return ing.load_raw()
    return pd.read_csv(LONG_CSV)


def test_all_hard_checks_match_pdf(long_df):
    bad = [(n, g, e) for n, g, e in dq.checks(long_df) if g != e]
    assert bad == []


def test_wc_murder_dispute_is_reported(long_df):
    d = dq.disputed(long_df)
    assert d["Western Cape"] == (1113, 1109)
    assert d["Eastern Cape"] == (1064, 1068)
    assert set(d) == {"Western Cape", "Eastern Cape"}


def test_station_layers_shape(long_df):
    lay = ing.station_layers(long_df)
    assert lay["station"].is_unique
    assert len(lay) == 1174
    for col in ("gangs", "political", "farm"):
        assert lay[col].isna().all()  # not zero: no official station series
    assert int(lay["murder"].sum()) == 5590
    assert int(lay["kidnapping"].sum()) == 4934


def test_spot_check_stations(long_df):
    lay = ing.station_layers(long_df).set_index("station")
    assert lay.loc["Khayelitsha", "murder"] == 66
    assert lay.loc["Delft", "murder"] == 66
    assert lay.loc["Lwandle", "murder"] == 48
    assert lay.loc["Lwandle", "murder_q2_2025"] == 15


def test_committed_layers_csv_agrees_with_rebuild(long_df):
    rebuilt = ing.station_layers(long_df)
    committed = pd.read_csv(LAYERS_CSV)
    assert list(rebuilt["station"]) == list(committed["station"])
    assert int(committed["murder"].sum()) == 5590
    assert len(committed) == 1174
    for col in ("gangs", "political", "farm"):
        assert committed[col].isna().all()
