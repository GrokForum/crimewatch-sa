"""Load and validate the publishable daily-sweep catalog (data/sweeps.json).

Fail closed: a missing file, a schema error, a fact without a reference, a
private or unpublished handle named on our page, or a disclaimer typo stops
the site build.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import site_content as C
from popia_gate import EMAIL_RE, ID_RE, PHONE_RE

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = ROOT / "data" / "sweeps.json"

DISCLAIMER = (
    "We are not responsible for anything published by anyone else, "
    "including personal information."
)

# Empty days (no cited items) must use this wording. It does not name an
# incident, a town, or internal working files.
LEAN_EMPTY_SUMMARY = (
    "No new official or news item with a fetched source was added on this lean morning run."
)

# Public catalog text must not point at internal working material.
FORBIDDEN_PROCESS_PHRASES = (
    "private hub",
    "operational notes",
    "the notes",
)

PUBLISHABLE_ROLES = frozenset({"official", "police", "media", "public-figure"})
ITEM_KINDS = frozenset({"news", "official", "civil-society", "x-pulse"})
HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")
DATE_RE = re.compile(r"^20[0-9]{2}-[01][0-9]-[0-3][0-9]$")
# Built from parts so this file does not itself contain a local path.
PATH_RE = re.compile(
    "(?:" + "|".join([r"/work" + r"space\b", r"/ho" + r"me/", r"/cur" + r"sor/", r"/t" + r"mp/", r"/Us" + r"ers/"]) + ")"
)
X_HOSTS = frozenset({"x.com", "www.x.com", "twitter.com", "www.twitter.com"})

# Extra official and major news hosts seen in fetched sweep citations, on top
# of whatever is already in site_content.SOURCES.
EXTRA_SWEEP_HOSTS = frozenset({
    "citizen.co.za",
    "www.citizen.co.za",
    "news24.com",
    "www.news24.com",
    "timeslive.co.za",
    "www.timeslive.co.za",
    "sabcnews.com",
    "www.sabcnews.com",
    "sanews.gov.za",
    "www.sanews.gov.za",
    "mg.co.za",
    "www.mg.co.za",
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
})


class SweepError(Exception):
    pass


def _source_hosts() -> set[str]:
    hosts = set(EXTRA_SWEEP_HOSTS)
    for _title, url, _kind in C.SOURCES.values():
        host = urlparse(url).hostname
        if host:
            hosts.add(host.lower())
    return hosts


def _scan_text(label: str, text: str) -> list[str]:
    fails = []
    if ID_RE.search(text):
        fails.append(f"{label}: identity-number pattern")
    if PHONE_RE.search(text):
        fails.append(f"{label}: phone pattern")
    if EMAIL_RE.search(text):
        fails.append(f"{label}: email pattern")
    if PATH_RE.search(text):
        fails.append(f"{label}: local file-system path")
    low = text.casefold()
    for phrase in FORBIDDEN_PROCESS_PHRASES:
        if phrase in low:
            fails.append(
                f"{label}: operational wording is not for the public catalog"
            )
            break
    return fails


def _check_x_url(url: str, allowed_handles: set[str]) -> str | None:
    parts = urlparse(url)
    host = (parts.hostname or "").lower()
    if host not in X_HOSTS:
        return None
    segs = [s for s in parts.path.split("/") if s]
    if not segs:
        return f"X URL has no handle: {url}"
    handle = segs[0]
    if handle.lower() in {"i", "intent", "hashtag", "search", "explore"}:
        return f"X URL is not a profile or status link: {url}"
    if not HANDLE_RE.fullmatch(handle):
        return f"X URL handle is not valid: {url}"
    if handle.casefold() not in {h.casefold() for h in allowed_handles}:
        return f"X URL is not a publishable handle on this item: {url}"
    if len(segs) == 1:
        return None
    if len(segs) >= 2 and segs[1] == "status" and len(segs) >= 3 and segs[2].isdigit():
        return None
    return f"X URL is not a profile or status link: {url}"


def _check_source_url(url: str, allowed_handles: set[str], hosts: set[str]) -> list[str]:
    fails = []
    if not isinstance(url, str) or not url.startswith("https://"):
        return [f"source URL must be https: {url!r}"]
    parts = urlparse(url)
    host = (parts.hostname or "").lower()
    if not host or host not in hosts:
        fails.append(f"source host is not on the reviewed list: {url}")
        return fails
    xfail = _check_x_url(url, allowed_handles)
    if xfail:
        fails.append(xfail)
    return fails


def _check_item(day: str, item: dict, hosts: set[str]) -> list[str]:
    fails = []
    ident = item.get("id") or "?"
    label = f"{day}/{ident}"
    if not ident or not isinstance(ident, str):
        fails.append(f"{day}: item missing id")
    kind = item.get("kind")
    if kind not in ITEM_KINDS:
        fails.append(f"{label}: kind must be one of {sorted(ITEM_KINDS)}")
    title = item.get("title")
    summary = item.get("summary")
    if not title or not isinstance(title, str):
        fails.append(f"{label}: missing title")
    if not summary or not isinstance(summary, str):
        fails.append(f"{label}: missing summary")
    fact = item.get("label")
    if fact is not None and fact not in C.LABELS:
        fails.append(f"{label}: fact label {fact!r} is not one of {C.LABELS}")
    handles = item.get("handles") or []
    if not isinstance(handles, list):
        fails.append(f"{label}: handles must be a list")
        handles = []
    allowed_handles = set()
    for h in handles:
        if not isinstance(h, dict):
            fails.append(f"{label}: handle entry must be an object")
            continue
        handle = h.get("handle") or ""
        role = h.get("role")
        display = h.get("display") or f"@{handle}"
        if not HANDLE_RE.fullmatch(str(handle)):
            fails.append(f"{label}: handle {handle!r} is not valid")
            continue
        if role not in PUBLISHABLE_ROLES:
            fails.append(
                f"{label}: handle @{handle} role {role!r} is not publishable "
                f"(official, police, media or public-figure)"
            )
            continue
        if display not in (f"@{handle}", handle, f"@{handle}".casefold()):
            # display may only be the handle, with or without @
            if str(display).lstrip("@").casefold() != handle.casefold():
                fails.append(f"{label}: display {display!r} does not match handle {handle}")
        allowed_handles.add(handle)
    sources = item.get("sources") or []
    if not isinstance(sources, list) or not sources:
        fails.append(f"{label}: every fact needs a reference (sources is empty)")
        sources = []
    for src in sources:
        if not isinstance(src, dict) or not src.get("title") or not src.get("url"):
            fails.append(f"{label}: source must have a title and a url")
            continue
        for msg in _check_source_url(src["url"], allowed_handles, hosts):
            fails.append(msg if msg.startswith(label) else f"{label}: {msg}")
    blob = json.dumps(item, ensure_ascii=False)
    fails.extend(_scan_text(label, blob))
    return fails


def validate(catalog: dict) -> list[str]:
    fails = []
    if not isinstance(catalog, dict):
        return ["catalog is not an object"]
    if catalog.get("disclaimer") != DISCLAIMER:
        fails.append("disclaimer does not match the required wording")
    if catalog.get("version") != 1:
        fails.append("catalog version must be 1")
    days = catalog.get("days")
    if not isinstance(days, list) or not days:
        fails.append("catalog has no days")
        return fails
    hosts = _source_hosts()
    seen = set()
    for day in days:
        if not isinstance(day, dict):
            fails.append("day entry must be an object")
            continue
        date = day.get("date")
        if not isinstance(date, str) or not DATE_RE.fullmatch(date):
            fails.append(f"invalid day date: {date!r}")
            continue
        if date in seen:
            fails.append(f"duplicate day: {date}")
        seen.add(date)
        if not day.get("summary") or not isinstance(day.get("summary"), str):
            fails.append(f"{date}: missing summary")
        if not day.get("compiled_sast") or not isinstance(day.get("compiled_sast"), str):
            fails.append(f"{date}: missing compiled_sast")
        items = day.get("items")
        if not isinstance(items, list):
            fails.append(f"{date}: items must be a list")
            continue
        if not items and day.get("summary") and day["summary"] != LEAN_EMPTY_SUMMARY:
            fails.append(
                f"{date}: a day with no cited items must use the generic lean summary"
            )
        ids = set()
        for item in items:
            if not isinstance(item, dict):
                fails.append(f"{date}: item must be an object")
                continue
            ident = item.get("id")
            if ident in ids:
                fails.append(f"{date}: duplicate item id {ident}")
            ids.add(ident)
            fails.extend(_check_item(date, item, hosts))
        fails.extend(_scan_text(date, json.dumps(day, ensure_ascii=False)))
    return fails


def load(path: Path = DEFAULT_CATALOG) -> dict:
    try:
        catalog = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SweepError(f"sweep catalog not found: {path}") from exc
    except ValueError as exc:
        raise SweepError(f"sweep catalog is not valid JSON: {exc}") from exc
    fails = validate(catalog)
    if fails:
        raise SweepError("sweep catalog failed checks:\n" + "\n".join(fails))
    # Newest date first, stable by date descending then as written.
    catalog = {
        "version": catalog["version"],
        "disclaimer": catalog["disclaimer"],
        "days": sorted(catalog["days"], key=lambda d: d["date"], reverse=True),
    }
    return catalog


def citation_urls(catalog: dict) -> set[str]:
    urls = set()
    for day in catalog.get("days", []):
        for item in day.get("items", []):
            for src in item.get("sources", []):
                url = src.get("url")
                if url:
                    urls.add(url)
    return urls


def payload(catalog: dict) -> dict:
    """Strip nothing of substance; return the public, deterministic object."""
    days = []
    for day in catalog["days"]:
        items = []
        for item in day["items"]:
            items.append({
                "id": item["id"],
                "kind": item["kind"],
                "title": item["title"],
                "place": item.get("place") or "",
                "summary": item["summary"],
                "label": item.get("label"),
                "handles": [
                    {
                        "handle": h["handle"],
                        "role": h["role"],
                        "display": h.get("display") or f"@{h['handle']}",
                    }
                    for h in (item.get("handles") or [])
                ],
                "sources": [
                    {"title": s["title"], "url": s["url"]}
                    for s in item["sources"]
                ],
            })
        days.append({
            "date": day["date"],
            "compiled_sast": day["compiled_sast"],
            "summary": day["summary"],
            "items": items,
        })
    return {
        "version": 1,
        "disclaimer": DISCLAIMER,
        "days": days,
    }
