"""Collector TLS logging, bad-manifest guard, dq malformed-data path, district gate, manifest pins."""
import hashlib
import io
import json
import ssl
import urllib.error
from pathlib import Path

import pandas as pd
import pytest

import dq_check as dq
import fetch_official as fo
import verify_workbook as vw

ROOT = fo.ROOT
DATA = ROOT / "data"


# ---- collector
def _raiser(exc):
    def opener(url, context=None, timeout=None):
        assert isinstance(context, ssl.SSLContext)
        assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
        raise exc
    return opener


@pytest.mark.parametrize("exc", [
    ssl.SSLCertVerificationError(1, "certificate verify failed: unable to get local issuer certificate"),
    urllib.error.URLError(ssl.SSLError(1, "TLSV1_ALERT_PROTOCOL_VERSION")),
])
def test_tls_failure_is_loud_and_fails(tmp_path, capsys, exc):
    log = tmp_path / "logs" / "collector.log"
    code = fo.fetch("https://example.invalid/x.xlsx", tmp_path / "x.xlsx", log_path=log, opener=_raiser(exc))
    err = capsys.readouterr().err
    assert code == fo.EXIT_TLS == 2
    assert "::error title=Collector TLS failure::" in err
    assert "FAIL TLS error fetching https://example.invalid/x.xlsx" in err
    rec = json.loads(log.read_text().strip().splitlines()[-1])
    assert rec["kind"] == "TLS" and rec["url"].endswith("x.xlsx")
    assert not (tmp_path / "x.xlsx").exists()


def test_non_tls_failure_is_loud_and_fails(tmp_path, capsys):
    log = tmp_path / "collector.log"
    code = fo.fetch("https://example.invalid/x", tmp_path / "x", log_path=log,
                    opener=_raiser(urllib.error.HTTPError("https://example.invalid/x", 403, "Forbidden", {}, None)))
    err = capsys.readouterr().err
    assert code == fo.EXIT_DOWNLOAD == 1
    assert "::error title=Collector download failure::" in err
    assert json.loads(log.read_text())["kind"] == "download"


def test_successful_fetch_writes_file(tmp_path):
    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    code = fo.fetch("https://example.invalid/ok", tmp_path / "ok.bin", log_path=tmp_path / "l.log",
                    opener=lambda url, context=None, timeout=None: Resp(b"PKdata"))
    assert code == 0
    assert (tmp_path / "ok.bin").read_bytes() == b"PKdata"
    assert not (tmp_path / "l.log").exists()


def test_ca_bundle_is_used_and_no_insecure_flags():
    ctx = fo.ssl_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    wf = (ROOT / ".github" / "workflows" / "nightly.yml").read_text()
    assert "curl -k" not in wf and "--insecure" not in wf
    assert "fetch_official.py" in wf


# ---- verify_workbook bad-manifest guard
@pytest.mark.parametrize("content, msg", [
    (None, "manifest not found"),
    ("{not json", "not valid JSON"),
    ('{"other": {}}', "no 'workbook' entry"),
    ('{"workbook": {"url": "u", "path": "p", "size": 1}}', "missing ['sha256']"),
    ('{"workbook": {"url": "u", "path": "p", "size": "big", "sha256": "x"}}', "malformed"),
])
def test_bad_manifest_fails_friendly(tmp_path, content, msg):
    p = tmp_path / "manifest.json"
    if content is not None:
        p.write_text(content)
    with pytest.raises(SystemExit) as exc:
        vw.load_manifest(p)
    assert str(exc.value).startswith("FAIL") and msg in str(exc.value)


def test_verify_accepts_str_path(tmp_path):
    with pytest.raises(SystemExit) as exc:
        vw.verify(str(tmp_path / "missing.xlsx"))
    assert "missing workbook" in str(exc.value)


# ---- dq malformed data (TypeError path) fails clearly, no traceback
def test_dq_malformed_counts_fail_clearly(tmp_path, capsys):
    df = pd.read_csv(DATA / "saps_q2_2026_27_long.csv")
    df["q2_2026"] = df["q2_2026"].astype(object)
    df.loc[df.index[0], "q2_2026"] = "n/a"
    p = tmp_path / "bad.csv"
    df.to_csv(p, index=False)
    assert dq.main(p) == 1
    assert "FAIL" in capsys.readouterr().out


# ---- district gate
def test_district_gate_passes_on_committed_data(capsys):
    assert dq.run_district_gate(DATA) == 0
    out = capsys.readouterr().out
    assert "DISPUTED district Amathole District|murder: district row 160 vs station rows sum 156" in out


def test_district_gate_flags_unlisted_dispute(tmp_path, capsys):
    for name in ("districts_q2_2026_27_layers.csv", "stations_q2_2026_27_layers.csv"):
        (tmp_path / name).write_bytes((DATA / name).read_bytes())
    d = pd.read_csv(tmp_path / "districts_q2_2026_27_layers.csv")
    d.loc[d["district"] == "Alfred Nzo District", "murder"] += 1
    d.to_csv(tmp_path / "districts_q2_2026_27_layers.csv", index=False)
    assert dq.run_district_gate(tmp_path) > 0
    assert "FAIL unlisted district dispute Alfred Nzo District|murder" in capsys.readouterr().out


# ---- manifest pins for derived and boundary files
def test_manifest_pins_match_committed_files():
    m = json.loads((DATA / "manifest.json").read_text())
    assert m["raw_data_sheet"] == {"workbook_sheet": "RAW Data", "stations": 1174, "districts": 55, "categories": 44}
    for rel, pin in m["derived"].items():
        data = (ROOT / rel).read_bytes()
        assert len(data) == pin["size"], rel
        assert hashlib.sha256(data).hexdigest() == pin["sha256"], rel
    geo = json.loads((DATA / "geo" / "za_provinces.geojson").read_text())
    assert len(geo["features"]) == 9
    assert all(set(f["properties"]) == {"province"} for f in geo["features"])
    assert m["provinces_geo_source"]["sha256"] == "22d0e3ad85eb3e27f17cabf8ba2d50e554fbc27a87796ff891d958185da62fb5"
