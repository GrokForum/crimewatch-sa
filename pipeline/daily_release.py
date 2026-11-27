"""Fail-closed gate for the daily register flag and for a public /daily/ build.

A public /daily/ build, or any daily_register=on (CW_DAILY_REGISTER=1) build,
is refused unless all three are recorded in pipeline/daily_preconditions.json:
answer (a) retention/takedown, answer (b) per-day reviewer, and a public-page
GO. The committed file records (a) and (b) and does not record a public-page
GO, so the live check refuses.

Dates must be real ISO YYYY-MM-DD values, parseable and not in the future
(Africa/Johannesburg). Summaries for (a) and (b) must meet a minimum length and must not be
made mostly of placeholder tokens or of repeated characters or tokens.
A genuine sentence that merely mentions one such word is allowed.
The /daily/ tree is matched case-insensitively.

The flag defaults to off. This module does not schedule anything.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path

FLAG_ENV = "CW_DAILY_REGISTER"
PRECONDITIONS_FILE = Path(__file__).resolve().parent / "daily_preconditions.json"

# Subtree under the generated site, source trees, or planned rels that
# counts as a public /daily/ build.
DAILY_SITE_PREFIX = "daily/"

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MIN_SUMMARY_LEN = 24
PLACEHOLDER_SUMMARIES = frozenset(
    {
        "todo",
        "tbd",
        "fixture",
        "x",
        "n/a",
        "na",
        "tbc",
        "placeholder",
        "none",
        "null",
        "unknown",
        "pending",
    }
)


class DailyReleaseError(Exception):
    """A daily-register build or flag setting is not allowed."""


def _today_sast() -> date:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("Africa/Johannesburg")).date()
    except Exception:
        return date.today()


def _valid_iso_date(value) -> bool:
    if not isinstance(value, str):
        return False
    raw = value.strip()
    if not ISO_DATE_RE.fullmatch(raw):
        return False
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return False
    return parsed <= _today_sast()


def _summary_tokens(text: str) -> list:
    """Whitespace-separated tokens, punctuation stripped, case-folded."""
    tokens = []
    for part in text.split():
        cleaned = part.strip('.,;:!?()[]{}\'"')
        if cleaned:
            tokens.append(cleaned.casefold())
    return tokens


def _mostly_placeholder_or_repeated(text: str) -> bool:
    """Refuse a summary made mostly of placeholders or of repeated filler.

    A genuine sentence that merely mentions one placeholder word is allowed.
    """
    folded = text.strip().casefold()
    if folded in PLACEHOLDER_SUMMARIES:
        return True
    compact = re.sub(r"[^a-z0-9]+", "", folded)
    if len(compact) >= MIN_SUMMARY_LEN and len(set(compact)) == 1:
        return True
    tokens = _summary_tokens(text)
    if not tokens:
        return False
    if len(tokens) >= 3 and len(set(tokens)) == 1:
        return True
    n_ph = sum(1 for tok in tokens if tok in PLACEHOLDER_SUMMARIES)
    # "Mostly" means at least half the tokens, and more than one placeholder,
    # so a genuine summary that mentions a single TODO/TBD still passes.
    return n_ph >= 2 and n_ph * 2 >= len(tokens)


def _valid_summary(value) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    if _mostly_placeholder_or_repeated(text):
        return False
    if len(text) < MIN_SUMMARY_LEN:
        return False
    return True


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


def is_daily_rel(rel) -> bool:
    """True if a planned output path is under the /daily/ tree (case-folded)."""
    text = str(rel).replace('\\', "/").lstrip("/").casefold()
    prefix = DAILY_SITE_PREFIX.casefold()
    name = prefix.rstrip("/")
    return text == name or text.startswith(prefix)


def daily_in_rels(rels) -> bool:
    return any(is_daily_rel(rel) for rel in rels)


def _daily_dir_entries(root: Path):
    """Yield immediate child paths whose name is 'daily' when case-folded."""
    root = Path(root)
    try:
        entries = root.iterdir()
    except OSError:
        return
    for entry in entries:
        if entry.name.casefold() == DAILY_SITE_PREFIX.casefold().rstrip("/"):
            yield entry


def daily_tree_present(site: Path) -> bool:
    site = Path(site)
    for daily in _daily_dir_entries(site):
        if daily.is_file():
            return True
        if not daily.is_dir():
            continue
        try:
            children = list(daily.rglob("*"))
        except OSError:
            continue
        if any(
            child.is_file() and child.name.casefold() == "index.html"
            for child in children
        ):
            return True
        if children:
            return True
    return False


def daily_sources_present(source_dirs) -> bool:
    return any(daily_tree_present(Path(d)) for d in source_dirs)


def _answer_recorded(entry) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get("recorded") is not True:
        return False
    return _valid_iso_date(entry.get("date")) and _valid_summary(entry.get("summary"))


def _public_page_go_recorded(entry) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get("recorded") is not True:
        return False
    if not _valid_iso_date(entry.get("date")):
        return False
    if "summary" in entry and entry.get("summary") is not None:
        return _valid_summary(entry.get("summary"))
    return True


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
    """Return fail strings if (a), (b) or a public-page GO is not recorded.

    A non-dict preconditions value raises DailyReleaseError (fail closed).
    """
    if preconditions is not None:
        if not isinstance(preconditions, dict):
            raise DailyReleaseError(
                "FAIL daily preconditions must be a JSON object"
            )
        data = preconditions
    else:
        try:
            data = load_preconditions(path)
        except DailyReleaseError as exc:
            msg = str(exc)
            if msg.startswith("FAIL "):
                msg = msg[5:]
            return [msg]
    fails = []
    if not _answer_recorded(data.get("answer_a")):
        fails.append("daily register: answer (a) retention/takedown is not recorded")
    if not _answer_recorded(data.get("answer_b")):
        fails.append("daily register: answer (b) per-day reviewer is not recorded")
    if not _public_page_go_recorded(data.get("public_page_go")):
        fails.append("daily register: public-page GO is not recorded")
    return fails


def assert_build_allowed(
    flag=None,
    daily_pages_present=False,  # noqa: F811 - argument name matches the RFC wording
    path: Path | None = None,
    environ=None,
    rels=None,
    out: Path | None = None,
    source_dirs=None,
    preconditions=None,
) -> None:
    """Raise DailyReleaseError if a flag-on or /daily/ build is not allowed.

    A default build (flag off, no daily pages in planned rels, output, or
    source trees) is allowed. Callers should pass rels, out, and source_dirs
    so this check does not depend on the daily_pages_present argument alone.
    """
    on = flag_on(environ) if flag is None else bool(flag)
    daily = bool(daily_pages_present)
    if rels is not None:
        daily = daily or daily_in_rels(rels)
    if out is not None:
        daily = daily or daily_tree_present(out)
    if source_dirs is not None:
        daily = daily or daily_sources_present(source_dirs)
    if not on and not daily:
        return
    fails = check_daily_release_allowed(preconditions=preconditions, path=path)
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
    if on or daily_tree_present(site):
        return check_daily_release_allowed(path=path)
    return []
