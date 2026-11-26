"""Fail-closed gate for the daily register flag and for a public /daily/ build.

A public /daily/ build, or any daily_register=on (CW_DAILY_REGISTER=1) build,
is refused unless all three are recorded in pipeline/daily_preconditions.json:
answer (a) retention/takedown, answer (b) per-day reviewer, and a public-page
GO. The committed file records (a) and (b) and does not record a public-page
GO, so the live check refuses.

The flag defaults to off. This module does not schedule anything.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

FLAG_ENV = "CW_DAILY_REGISTER"
PRECONDITIONS_FILE = Path(__file__).resolve().parent / "daily_preconditions.json"

# Subtree under the generated site that counts as a public /daily/ build.
DAILY_SITE_PREFIX = "daily/"


class DailyReleaseError(Exception):
    """A daily-register build or flag setting is not allowed."""


def flag_on(environ=None) -> bool:
    """Return True only for CW_DAILY_REGISTER=1. Unset or empty is off.

    Any other value is refused (same pattern as CW_INDEXABLE).
    """
    env = os.environ if environ is None else environ
    raw = env.get(FLAG_ENV, "")
    if raw == "":
        return False
    if raw == "1":
        return True
    raise DailyReleaseError(
        f"FAIL {FLAG_ENV}={raw!r} is not accepted (set to 1 to opt in, or leave unset)"
    )


def _recorded(entry) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get("recorded") is not True:
        return False
    date = entry.get("date")
    summary = entry.get("summary")
    return bool(isinstance(date, str) and date.strip()) or bool(
        isinstance(summary, str) and summary.strip()
    )


def _public_page_go_recorded(entry) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get("recorded") is not True:
        return False
    date = entry.get("date")
    return isinstance(date, str) and bool(date.strip())


def load_preconditions(path: Path | None = None) -> dict:
    path = Path(path) if path is not None else PRECONDITIONS_FILE
    if not path.is_file():
        raise DailyReleaseError(
            "FAIL daily preconditions file is missing; fail closed"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DailyReleaseError(
            f"FAIL daily preconditions file is not valid JSON: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise DailyReleaseError("FAIL daily preconditions file must be a JSON object")
    return data


def check_daily_release_allowed(preconditions=None, path: Path | None = None) -> list:
    """Return fail strings if (a), (b) or a public-page GO is not recorded."""
    try:
        data = preconditions if preconditions is not None else load_preconditions(path)
    except DailyReleaseError as exc:
        msg = str(exc)
        if msg.startswith("FAIL "):
            msg = msg[5:]
        return [msg]
    fails = []
    if not _recorded(data.get("answer_a")):
        fails.append("daily register: answer (a) retention/takedown is not recorded")
    if not _recorded(data.get("answer_b")):
        fails.append("daily register: answer (b) per-day reviewer is not recorded")
    if not _public_page_go_recorded(data.get("public_page_go")):
        fails.append("daily register: public-page GO is not recorded")
    return fails


def daily_pages_present(site: Path) -> bool:
    site = Path(site)
    if (site / "daily" / "index.html").is_file():
        return True
    daily = site / "daily"
    if daily.is_dir():
        return any(daily.rglob("*"))
    return False


def assert_build_allowed(
    flag=None,
    daily_pages_present=False,  # noqa: F811 - argument name matches the RFC wording
    path: Path | None = None,
    environ=None,
) -> None:
    """Raise DailyReleaseError if a flag-on or /daily/ build is not allowed.

    A default build (flag off, no daily pages) is allowed.
    """
    on = flag_on(environ) if flag is None else bool(flag)
    if not on and not daily_pages_present:
        return
    fails = check_daily_release_allowed(path=path)
    if fails:
        raise DailyReleaseError("FAIL " + "; ".join(fails))


def gate_fails_for_site(site: Path, environ=None, path: Path | None = None) -> list:
    """Fails to add to the site gate when the flag is on or /daily/ is present."""
    try:
        on = flag_on(environ)
    except DailyReleaseError as exc:
        msg = str(exc)
        if msg.startswith("FAIL "):
            msg = msg[5:]
        return [msg]
    if on or daily_pages_present(site):
        return check_daily_release_allowed(path=path)
    return []
