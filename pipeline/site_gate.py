"""POPIA and hygiene gate for the generated static site (build/site).

Usage: python pipeline/site_gate.py [site_dir]

Fails closed (exit 1) if any generated file:
  - lacks the robots noindex meta, the visible DRAFT banner or the CSP meta
    (HTML pages), or robots.txt does not disallow everything;
  - links anywhere other than an internal page that exists or a URL on the
    reviewed source register (site_content.SOURCES), or loads a script/style
    from outside the site, or has inline script or event-handler attributes;
  - uses a fact label other than the five MediaWatch labels;
  - contains an identity-number, phone or email pattern, a local file-system
    path, an internal name (checked against pipeline/banned_terms.sha256), an
    excluded incident aggregate, or a name from the optional private names
    list (path in env CW_PRIVATE_NAMES_FILE, kept outside the repository);
  - ships map data with keys outside the reviewed schema.
"""
import hashlib
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import site_content as C
from popia_gate import EMAIL_RE, ID_RE, PHONE_RE

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SITE = ROOT / "build" / "site"
BANNED_HASHES_FILE = Path(__file__).resolve().parent / "banned_terms.sha256"

REQUIRED_PAGES = ["index.html", "heat-map/index.html", "high-profile/index.html",
                  "media-gap/index.html", "method/index.html", "robots.txt"]
TEXT_SUFFIXES = {".html", ".js", ".css", ".json", ".txt"}
# Built from parts so this file does not itself contain a local path.
PATH_RE = re.compile("(?:" + "|".join([r"/work" + r"space\b", r"/ho" + r"me/", r"/cur" + r"sor/", r"/t" + r"mp/", r"/Us" + r"ers/"]) + ")")
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]+")
# The farm-attack incident aggregate excluded by review (incident-derived, re-identification risk).
INCIDENT_AGG_RE = re.compile(r"\b87\b[^.<]{0,60}\bincident", re.IGNORECASE)
PHONE_LOOSE_RE = re.compile(r"(?:\+27|\b0)[ -]?[1-8][0-9][ -]?[0-9]{3}[ -]?[0-9]{4}\b")

MAP_TOP_KEYS = {"edition", "period", "source", "layers", "noData", "provinces",
                "districts", "stations", "districtDisputes"}
MAP_ROW_KEYS = {"districts": {"d", "p", "v"}, "stations": {"s", "d", "p", "v"}}


def load_banned_hashes(path: Path = BANNED_HASHES_FILE) -> set:
    return {ln.strip() for ln in path.read_text().splitlines() if ln.strip() and not ln.startswith("#")}


def load_private_names() -> list:
    p = os.environ.get("CW_PRIVATE_NAMES_FILE")
    if not p:
        return []
    return [ln.strip() for ln in Path(p).read_text().splitlines() if ln.strip() and not ln.startswith("#")]


class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.scripts, self.styles, self.labels = [], [], [], []
        self.meta = {}
        self.inline_script = False
        self.handlers = []
        self.text = []
        self._in_draft = 0
        self.draft_text = ""
        self._stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for k in a:
            if k.startswith("on"):
                self.handlers.append(f"{tag}[{k}]")
        if tag == "a" and "href" in a:
            self.links.append(a["href"])
        if tag == "script":
            if a.get("src"):
                self.scripts.append(a["src"])
            else:
                self.inline_script = True
        if tag == "link":
            self.styles.append(a.get("href", ""))
        if tag == "meta":
            key = a.get("name") or a.get("http-equiv")
            if key:
                self.meta[key.lower()] = a.get("content", "")
        if "data-label" in a:
            self.labels.append(a["data-label"])
        if "draft" in (a.get("class") or "").split():
            self._in_draft += 1
            self._stack.append(tag)
        elif self._in_draft:
            self._stack.append(tag)

    def handle_endtag(self, tag):
        if self._in_draft and self._stack:
            self._stack.pop()
            if not self._stack:
                self._in_draft = 0

    def handle_data(self, data):
        self.text.append(data)
        if self._in_draft:
            self.draft_text += data


def _internal_ok(site: Path, href: str) -> bool:
    target = href.split("#", 1)[0]
    if target == "":
        return True
    if not target.startswith("/") or target.startswith("//"):
        return False
    rel = target.lstrip("/")
    cand = site / rel
    return (cand.is_file()) or (cand / "index.html").is_file()


def scan_text(name: str, text: str, banned: set, private_names: list) -> list:
    fails = []
    for label, rx in (("email pattern", EMAIL_RE), ("identity-number pattern", ID_RE),
                      ("phone pattern", PHONE_RE), ("phone pattern", PHONE_LOOSE_RE),
                      ("local file-system path", PATH_RE),
                      ("excluded incident aggregate", INCIDENT_AGG_RE)):
        m = rx.search(text)
        if m:
            fails.append(f"{name}: {label}")
    for tok in set(TOKEN_RE.findall(text)):
        if hashlib.sha256(tok.casefold().encode()).hexdigest() in banned:
            fails.append(f"{name}: internal or excluded name (token hash match)")
            break
    low = text.casefold()
    for n in private_names:
        if n.casefold() in low:
            fails.append(f"{name}: name from the private names list")
            break
    return fails


def check_html(site: Path, rel: str, text: str, allowed_urls: set) -> list:
    fails = []
    p = _Page()
    p.feed(text)
    if "noindex" not in p.meta.get("robots", ""):
        fails.append(f"{rel}: missing robots noindex meta")
    if "DRAFT" not in p.draft_text:
        fails.append(f"{rel}: missing visible DRAFT banner")
    csp = p.meta.get("content-security-policy", "")
    if "default-src 'none'" not in csp or "script-src 'self'" not in csp:
        fails.append(f"{rel}: missing or weak Content-Security-Policy meta")
    if p.inline_script:
        fails.append(f"{rel}: inline script")
    if p.handlers:
        fails.append(f"{rel}: inline event handler {p.handlers[0]}")
    for src in p.scripts + p.styles:
        if not src.startswith("/") or src.startswith("//") or not (site / src.lstrip("/")).is_file():
            fails.append(f"{rel}: script/style not served from this site: {src}")
    for href in p.links:
        if href.startswith(("http://", "https://", "//")):
            if href not in allowed_urls:
                fails.append(f"{rel}: link not on the reviewed source register: {href}")
        elif not _internal_ok(site, href):
            fails.append(f"{rel}: broken or non-internal link: {href}")
    for lab in p.labels:
        if lab not in C.LABELS:
            fails.append(f"{rel}: fact label not allowed: {lab}")
    return fails


def check_map_data(rel: str, text: str) -> list:
    prefix = "window.CW_DATA = "
    if not text.startswith(prefix):
        return [f"{rel}: unexpected map data wrapper"]
    try:
        d = json.loads(text[len(prefix):].rstrip().rstrip(";"))
    except ValueError as exc:
        return [f"{rel}: map data not valid JSON ({exc})"]
    fails = []
    if set(d) != MAP_TOP_KEYS:
        fails.append(f"{rel}: map data keys differ from the reviewed schema: {sorted(set(d) ^ MAP_TOP_KEYS)}")
    for key, allowed in MAP_ROW_KEYS.items():
        for row in d.get(key, []):
            if set(row) != allowed:
                fails.append(f"{rel}: {key} row keys differ from the reviewed schema")
                break
    for lay in d.get("layers", []):
        if lay.get("key") in ("gangs", "political", "farm") and lay.get("available"):
            fails.append(f"{rel}: {lay['key']} layer marked available but has no station-level SAPS data")
    return fails


def check_site(site: Path = DEFAULT_SITE, private_names=None) -> list:
    site = Path(site)
    if not site.is_dir():
        return [f"site directory not found: {site}"]
    banned = load_banned_hashes()
    names = load_private_names() if private_names is None else private_names
    allowed_urls = {u for _t, u, _k in C.SOURCES.values()}
    fails = []
    for req in REQUIRED_PAGES:
        if not (site / req).is_file():
            fails.append(f"missing required file: {req}")
    robots = site / "robots.txt"
    if robots.is_file() and not re.search(r"^Disallow:\s*/\s*$", robots.read_text(), re.M):
        fails.append("robots.txt: must contain 'Disallow: /' until publishing is approved")
    for path in sorted(site.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(site).as_posix()
        if path.suffix not in TEXT_SUFFIXES:
            fails.append(f"{rel}: unexpected file type in the site")
            continue
        text = path.read_text(encoding="utf-8")
        fails.extend(scan_text(rel, text, banned, names))
        if path.suffix == ".html":
            fails.extend(check_html(site, rel, text, allowed_urls))
        if rel == "assets/map-data.js":
            fails.extend(check_map_data(rel, text))
    return fails


def main(argv):
    site = Path(argv[1]) if len(argv) > 1 else DEFAULT_SITE
    fails = check_site(site)
    if fails:
        for f in fails:
            print("FAIL", f)
        return 1
    print(f"PASS site POPIA and hygiene gate ({site.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
