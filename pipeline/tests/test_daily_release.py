"""Fail-closed tests for the daily register release check (RFC-006 §11)."""
import json
import shutil
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pytest

import build_site as bs
import daily_release as dr
import site_gate as sg

VALID_DATE = "2026-11-26"
VALID_SUMMARY_A = (
    "Keep redacted records until a request via the published privacy address, "
    "then remove them from every surface."
)
VALID_SUMMARY_B = (
    "The critic reviewer, not the author, gives the per-day sign-off and may "
    "override a mapping with history."
)


def _today_sast():
    return date.fromisoformat(
        __import__("datetime")
        .datetime.now(ZoneInfo("Africa/Johannesburg"))
        .date()
        .isoformat()
    )


def _answer(date=VALID_DATE, summary=VALID_SUMMARY_A, recorded=True):
    return {"recorded": recorded, "date": date, "summary": summary}


def _go(date=VALID_DATE, recorded=True):
    return {"recorded": recorded, "date": date}


def _write_preconditions(tmp_path, **entries):
    data = {
        "answer_a": _answer(summary=VALID_SUMMARY_A),
        "answer_b": _answer(summary=VALID_SUMMARY_B),
        "public_page_go": _go(),
    }
    data.update(entries)
    path = tmp_path / "preconditions.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _all_three(tmp_path):
    return _write_preconditions(tmp_path)


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


def test_refuses_when_answer_a_is_unrecorded(tmp_path):
    path = _write_preconditions(tmp_path, answer_a={"recorded": False})
    fails = dr.check_daily_release_allowed(path=path)
    assert any("answer (a)" in f for f in fails)
    with pytest.raises(dr.DailyReleaseError, match=r"answer \(a\)"):
        dr.assert_build_allowed(flag=True, daily_pages_present=False, path=path)


def test_refuses_when_answer_b_is_unrecorded(tmp_path):
    path = _write_preconditions(tmp_path, answer_b={"recorded": False})
    fails = dr.check_daily_release_allowed(path=path)
    assert any("answer (b)" in f for f in fails)
    assert not any("answer (a)" in f for f in fails)
    with pytest.raises(dr.DailyReleaseError, match=r"answer \(b\)"):
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


@pytest.mark.parametrize(
    "bad_date",
    ["x", "FIXTURE", "2026-13-40", "2026/11/26", "26 Nov 2026"],
)
def test_rejects_non_iso_or_unparseable_date(tmp_path, bad_date):
    path = _write_preconditions(
        tmp_path, public_page_go=_go(date=bad_date)
    )
    fails = dr.check_daily_release_allowed(path=path)
    assert any("public-page GO is not recorded" in f for f in fails)
    with pytest.raises(dr.DailyReleaseError, match="public-page GO"):
        dr.assert_build_allowed(flag=True, path=path)


def test_rejects_future_iso_date(tmp_path):
    future = (_today_sast() + timedelta(days=1)).isoformat()
    path = _write_preconditions(tmp_path, public_page_go=_go(date=future))
    fails = dr.check_daily_release_allowed(path=path)
    assert any("public-page GO is not recorded" in f for f in fails)


@pytest.mark.parametrize("field", ["answer_a", "answer_b"])
@pytest.mark.parametrize(
    "bad_date",
    ["x", "FIXTURE", "2026-13-40", "2026/11/26", "26 Nov 2026"],
)
def test_rejects_non_iso_or_unparseable_date_on_answers_a_and_b(
    tmp_path, field, bad_date
):
    summary = VALID_SUMMARY_A if field == "answer_a" else VALID_SUMMARY_B
    path = _write_preconditions(
        tmp_path, **{field: _answer(date=bad_date, summary=summary)}
    )
    fails = dr.check_daily_release_allowed(path=path)
    label = "answer (a)" if field == "answer_a" else "answer (b)"
    assert any(label in f for f in fails)


@pytest.mark.parametrize("field", ["answer_a", "answer_b"])
def test_rejects_future_iso_date_on_answers_a_and_b(tmp_path, field):
    future = (_today_sast() + timedelta(days=1)).isoformat()
    summary = VALID_SUMMARY_A if field == "answer_a" else VALID_SUMMARY_B
    path = _write_preconditions(
        tmp_path, **{field: _answer(date=future, summary=summary)}
    )
    fails = dr.check_daily_release_allowed(path=path)
    label = "answer (a)" if field == "answer_a" else "answer (b)"
    assert any(label in f for f in fails)


@pytest.mark.parametrize("placeholder", ["TODO", "TBD", "FIXTURE", "x"])
def test_rejects_placeholder_summary(tmp_path, placeholder):
    path = _write_preconditions(
        tmp_path, answer_a=_answer(summary=placeholder)
    )
    fails = dr.check_daily_release_allowed(path=path)
    assert any("answer (a)" in f for f in fails)


def test_rejects_too_short_summary(tmp_path):
    path = _write_preconditions(tmp_path, answer_a=_answer(summary="too short"))
    fails = dr.check_daily_release_allowed(path=path)
    assert any("answer (a)" in f for f in fails)


def test_accepts_genuine_summary_mentioning_one_placeholder(tmp_path):
    summary = (
        "Keep redacted records until a request; a TODO from the owner is not "
        "a dated summary of the retention rule."
    )
    assert "TODO" in summary
    path = _write_preconditions(tmp_path, answer_a=_answer(summary=summary))
    assert dr.check_daily_release_allowed(path=path) == []


def test_rejects_summary_mostly_of_placeholder_tokens(tmp_path):
    summary = "TBD TBD TBD TBD TBD TBD TBD"
    assert len(summary) >= 24
    path = _write_preconditions(tmp_path, answer_a=_answer(summary=summary))
    fails = dr.check_daily_release_allowed(path=path)
    assert any("answer (a)" in f for f in fails)


def test_rejects_summary_of_repeated_characters(tmp_path):
    summary = "a" * 28
    path = _write_preconditions(tmp_path, answer_a=_answer(summary=summary))
    fails = dr.check_daily_release_allowed(path=path)
    assert any("answer (a)" in f for f in fails)


def test_non_dict_preconditions_raises_daily_release_error():
    with pytest.raises(dr.DailyReleaseError, match="JSON object"):
        dr.check_daily_release_allowed(preconditions=["not", "a", "dict"])
    with pytest.raises(dr.DailyReleaseError, match="JSON object"):
        dr.assert_build_allowed(flag=True, preconditions=["not", "a", "dict"])


def test_build_site_refuses_flag_on_against_committed_preconditions(
    tmp_path, monkeypatch
):
    monkeypatch.setenv(dr.FLAG_ENV, "1")
    with pytest.raises(dr.DailyReleaseError, match="public-page GO"):
        bs.build(tmp_path / "site")
    assert not (tmp_path / "site" / "daily").exists()


def test_build_site_main_flag_on_exits_1(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(dr.FLAG_ENV, "1")
    code = bs.main([bs.__file__, str(tmp_path / "site")])
    assert code == 1
    captured = capsys.readouterr()
    assert "public-page GO" in captured.err
    assert not (tmp_path / "site" / "daily").exists()


def test_build_itself_refuses_daily_source_without_public_page_go(
    tmp_path, monkeypatch
):
    assets = tmp_path / "assets"
    assets.mkdir()
    # Every asset build() copies from ASSETS_SRC must be present so the
    # hook is reached; a missing file must not mask the /daily/ refusal.
    for name in ("site.css", "map.js", "sweeps.js"):
        shutil.copy(bs.ASSETS_SRC / name, assets / name)
    (assets / "daily").mkdir()
    (assets / "daily" / "index.html").write_text(
        "<html><body>daily source</body></html>", encoding="utf-8"
    )
    monkeypatch.setattr(bs, "ASSETS_SRC", assets)
    with pytest.raises(dr.DailyReleaseError, match="public-page GO"):
        bs.build(tmp_path / "site")
    assert not (tmp_path / "site" / "daily").exists()


def test_gate_fails_for_site_refuses_flag_on_without_daily_tree(
    tmp_path, monkeypatch
):
    monkeypatch.setenv(dr.FLAG_ENV, "1")
    site = tmp_path / "site"
    site.mkdir()
    fails = dr.gate_fails_for_site(site)
    assert any("public-page GO is not recorded" in f for f in fails)
    assert not (site / "daily").exists()
    # The site gate must use the same arm, even with no /daily/ tree.
    gate_fails = sg.check_site(site, private_names=[])
    assert any("public-page GO is not recorded" in f for f in gate_fails)


def test_assert_build_allowed_refuses_daily_rels():
    with pytest.raises(dr.DailyReleaseError, match="public-page GO"):
        dr.assert_build_allowed(flag=False, rels=["daily/index.html"])


def test_assert_build_allowed_refuses_source_dirs(tmp_path):
    src = tmp_path / "src"
    (src / "daily").mkdir(parents=True)
    (src / "daily" / "index.html").write_text("<html><body>src</body></html>")
    with pytest.raises(dr.DailyReleaseError, match="public-page GO"):
        dr.assert_build_allowed(flag=False, source_dirs=[src])


def test_build_itself_refuses_daily_in_output_tree(tmp_path):
    out = tmp_path / "site"
    (out / "daily").mkdir(parents=True)
    (out / "daily" / "index.html").write_text(
        "<html><body>leftover daily</body></html>", encoding="utf-8"
    )
    with pytest.raises(dr.DailyReleaseError, match="public-page GO"):
        bs.build(out)


@pytest.mark.parametrize("rel", ["Daily/index.html", "DAILY/index.html", "DAILY/"])
def test_assert_build_allowed_refuses_case_folded_daily_rels(rel):
    with pytest.raises(dr.DailyReleaseError, match="public-page GO"):
        dr.assert_build_allowed(flag=False, rels=[rel])


def test_assert_build_allowed_refuses_case_folded_source_dirs(tmp_path):
    src = tmp_path / "src"
    (src / "Daily").mkdir(parents=True)
    (src / "Daily" / "index.html").write_text("<html><body>src</body></html>")
    with pytest.raises(dr.DailyReleaseError, match="public-page GO"):
        dr.assert_build_allowed(flag=False, source_dirs=[src])


def test_build_itself_refuses_case_folded_daily_in_output_tree(tmp_path):
    out = tmp_path / "site"
    (out / "DAILY").mkdir(parents=True)
    (out / "DAILY" / "index.html").write_text(
        "<html><body>leftover daily</body></html>", encoding="utf-8"
    )
    with pytest.raises(dr.DailyReleaseError, match="public-page GO"):
        bs.build(out)


def test_build_itself_refuses_case_folded_daily_under_assets_src(
    tmp_path, monkeypatch
):
    assets = tmp_path / "assets"
    assets.mkdir()
    for name in ("site.css", "map.js", "sweeps.js"):
        shutil.copy(bs.ASSETS_SRC / name, assets / name)
    (assets / "Daily").mkdir()
    (assets / "Daily" / "index.html").write_text(
        "<html><body>daily source</body></html>", encoding="utf-8"
    )
    monkeypatch.setattr(bs, "ASSETS_SRC", assets)
    with pytest.raises(dr.DailyReleaseError, match="public-page GO"):
        bs.build(tmp_path / "site")
    assert not (tmp_path / "site" / "Daily").exists()
    assert not (tmp_path / "site" / "daily").exists()


def test_site_gate_refuses_case_folded_daily_tree_without_public_page_go(tmp_path):
    site = tmp_path / "site"
    (site / "DAILY").mkdir(parents=True)
    (site / "DAILY" / "index.html").write_text("<html><body>daily</body></html>")
    fails = sg.check_site(site, private_names=[])
    assert any("public-page GO is not recorded" in f for f in fails)
    assert any("public-page GO is not recorded" in f for f in dr.gate_fails_for_site(site))
