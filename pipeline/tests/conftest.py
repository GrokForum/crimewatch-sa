from pathlib import Path

import pandas as pd
import pytest

import ingest_saps_xlsx as ing

LONG_CSV = ing.ROOT / "data" / "saps_q2_2026_27_long.csv"


@pytest.fixture(scope="session")
def long_df():
    if Path(ing.DEFAULT_XLSX).is_file():
        return ing.load_raw()
    return pd.read_csv(LONG_CSV)
