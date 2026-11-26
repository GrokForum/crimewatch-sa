"""Fail-closed tests for the daily register release check (RFC-006 §11)."""
import json

import pytest

import daily_release as dr
import site_gate as sg


def _all_three(tmp_path):
    path = tmp_path / "preconditions.json"
    path.write_text(
        json.dumps(
            {
                "answer_a": {
                    "recorded": True,
                    "date": "FIXTURE",
                    "summary": "fixture answer a",
                },
                "answer_b": {
                    "recorded": True,
                    "date": "FIXTURE",
                    "summary": "fixture answer b",
                },
                "public_page_go": {"recorded": True, "date": "FIXTURE"},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_committed_preconditions_record_a_and_b_but_not_public_page_go():
    data = dr.load_preconditions()
    assert data["answer_a"]["recorded"] is True
    assert data["answer_b"]["recorded"] is True
    assert data["public_page_go"]["recorded"] is not True
    fails = dr.check_daily_release_allowed()
    assert any("public-page GO is not recorded" in f for f in fails)
    assert fails  # currently refuses


def test_default_flag_off_build_is_allowed():
    dr.assert_build_allowed(flag=False, daily_pages_present=False)
    assert dr.flag_on(environ={}) is False
    assert dr.gate_fails_for_site(site=".", environ={}) == []


def test_flag_on_against_committed_file_is_refused(monkeypatch):
    monkeypatch.setenv(dr.FLAG_ENV, "1")
    assert dr.flag_on() is True
    with pytest.raises(dr.DailyReleaseError, match="public-page GO"):
        dr.assert_build_allowed()
    fails = dr.check_daily_release_allowed()
    assert any("public-page GO is not recorded" in f for f in fails)


def test_daily_pages_against_committed_file_are_refused():
    with pytest.raises(dr.DailyReleaseError, match="public-page GO"):
        dr.assert_build_allowed(flag=False, daily_pages_present=True)


def test_site_gate_refuses_a_daily_tree_without_public_page_go(tmp_path):
    site = tmp_path / "site"
    (site / "daily").mkdir(parents=True)
    (site / "daily" / "index.html").write_text("<html><body>daily</body></html>")
    fails = sg.check_site(site, private_names=[])
    assert any("public-page GO is not recorded" in f for f in fails)


def test_missing_preconditions_file_fails_closed(tmp_path):
    missing = tmp_path / "no-such.json"
    fails = dr.check_daily_release_allowed(path=missing)
    assert any("missing" in f for f in fails)


def test_refuses_when_answer_a_or_b_is_unrecorded(tmp_path):
    path = tmp_path / "preconditions.json"
    path.write_text(
        json.dumps(
            {
                "answer_a": {"recorded": False},
                "answer_b": {
                    "recorded": True,
                    "date": "FIXTURE",
                    "summary": "fixture",
                },
                "public_page_go": {"recorded": True, "date": "FIXTURE"},
            }
        ),
        encoding="utf-8",
    )
    fails = dr.check_daily_release_allowed(path=path)
    assert any("answer (a)" in f for f in fails)
    with pytest.raises(dr.DailyReleaseError, match=r"answer \(a\)"):
        dr.assert_build_allowed(flag=True, daily_pages_present=False, path=path)


def test_allows_only_when_all_three_are_present_in_a_fixture(tmp_path, monkeypatch):
    path = _all_three(tmp_path)
    assert dr.check_daily_release_allowed(path=path) == []
    monkeypatch.setenv(dr.FLAG_ENV, "1")
    dr.assert_build_allowed(flag=True, daily_pages_present=True, path=path)


def test_invalid_flag_value_is_refused(monkeypatch):
    monkeypatch.setenv(dr.FLAG_ENV, "yes")
    with pytest.raises(dr.DailyReleaseError, match="not accepted"):
        dr.flag_on()
