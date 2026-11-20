import hashlib
from pathlib import Path

import pytest

import ingest_saps_xlsx as ing
import verify_workbook as vw


def test_manifest_pin_matches_local_workbook_when_present():
    meta = vw.load_manifest()["workbook"]
    path = ing.ROOT / meta["path"]
    if not path.is_file():
        pytest.skip("official workbook not present")
    vw.verify(path)
    data = path.read_bytes()
    assert len(data) == meta["size"]
    assert hashlib.sha256(data).hexdigest() == meta["sha256"]


def test_pin_mismatch_fails_closed(tmp_path):
    path = tmp_path / "forged.xlsx"
    path.write_bytes(b"PK\x03\x04" + b"0" * 100)
    with pytest.raises(SystemExit, match="pin mismatch"):
        vw.verify(path)


def test_missing_workbook_fails_closed(tmp_path):
    with pytest.raises(SystemExit, match="missing workbook"):
        vw.verify(tmp_path / "absent.xlsx")
