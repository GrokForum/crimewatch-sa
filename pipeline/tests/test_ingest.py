from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook

import ingest_saps_xlsx as ing
import dq_check as dq
from provinces import UnknownProvinceError, canonical_province

Q25 = ing.Q25
Q26 = ing.Q26


def _mini_xlsx(path: Path, rows):
    """Write a tiny official-shaped workbook (header on row 3)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "RAW Data"
    ws.append([])
    ws.append([])
    ws.append(["Comp level", "Station", "District", "Province", "Crime_Category", Q25, Q26])
    for row in rows:
        ws.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def test_coerce_count_rejects_blank_and_non_numeric():
    with pytest.raises(ing.IngestError, match="non-numeric"):
        ing.coerce_count_column(pd.Series([1, None, 3]), "q2_2026")
    with pytest.raises(ing.IngestError, match="non-numeric"):
        ing.coerce_count_column(pd.Series([1, "n/a", 3]), "q2_2026")
    assert ing.coerce_count_column(pd.Series([1, 0, 3]), "q2_2026").tolist() == [1, 0, 3]


def test_load_raw_fails_on_non_numeric_cell(tmp_path):
    path = tmp_path / "bad.xlsx"
    _mini_xlsx(path, [
        ["Station", "Delft", "City of Cape Town District", "Western Cape", "Murder", 60, "n/a"],
    ])
    with pytest.raises(ing.IngestError, match="non-numeric"):
        ing.load_raw(path)
    assert ing.main(["ingest", str(path), str(tmp_path / "out")]) == 1


def test_merge_on_station_and_province(long_df):
    extra = long_df[(long_df["level"] == "Station") & (long_df["area"] == "Delft")].copy()
    extra["Province"] = "Eastern Cape"
    extra["q2_2026"] = 7
    extra["q2_2025"] = 1
    combined = pd.concat([long_df, extra], ignore_index=True)
    lay = ing.station_layers(combined)
    assert lay.duplicated(subset=["station", "province"]).sum() == 0
    key = lay.set_index(["station", "province"])
    assert key.loc[("Delft", "Western Cape"), "murder"] == 66
    assert key.loc[("Delft", "Eastern Cape"), "murder"] == 7
    assert len(lay) == len(long_df[long_df["level"] == "Station"][["area", "Province"]].drop_duplicates()) + 1


def test_duplicate_station_key_is_rejected(long_df):
    extra = long_df[(long_df["level"] == "Station") & (long_df["area"] == "Delft")].copy()
    # same station and province, so the key is no longer unique
    combined = pd.concat([long_df, extra], ignore_index=True)
    with pytest.raises(ing.IngestError, match="duplicate station\\+province"):
        ing.station_layers(combined)


def test_western_cape_case_is_normalised_for_disputes(long_df):
    df = long_df.copy()
    mask = (df["level"] == "Station") & (df["Province"] == "Western Cape")
    df.loc[mask, "Province"] = "Western cape"
    assert canonical_province("Western cape") == "Western Cape"
    d = dq.disputed(df)
    assert d["Western Cape"] == (1113, 1109)
    assert "Western cape" not in d


def test_unknown_province_is_rejected(long_df):
    df = long_df.copy()
    mask = (df["level"] == "Station") & (df["Province"] == "Western Cape")
    df.loc[mask, "Province"] = "Natal"
    with pytest.raises(UnknownProvinceError, match="Natal"):
        dq.disputed(df)


def test_unpublished_layers_are_explicit_nulls(long_df):
    lay = ing.station_layers(long_df)
    for col in ing.UNPUBLISHED_LAYERS:
        assert lay[col].isna().all()
        # explicit nulls, not a column of zeros
        assert not (lay[col].fillna(999) == 0).any()
