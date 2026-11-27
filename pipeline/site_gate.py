"""POPIA and hygiene gate for the generated static site (build/site).

Usage: python pipeline/site_gate.py [site_dir]

Fails closed (exit 1) if any generated file:
  - lacks an *effective* robots noindex meta (in the document head, not inside
    template/textarea/noscript/script/style or after <body>), the visible DRAFT
    banner or the CSP meta (HTML pages), or robots.txt does not disallow
    everything. Indexing is an opt-in (CW_INDEXABLE=1 and
    CW_SITE_HOST=crimewatch.grokforum.site only); in that mode noindex and
    Disallow: / must be absent, and the gate is run with the same opt-in.
    The opt-in is never set in CI;
  - links anywhere other than an internal page that exists or a URL on the
    reviewed source register (site_content.SOURCES), or loads a script/style
    from outside the site, or has inline script or event-handler attributes;
  - uses a fact label other than the five MediaWatch labels;
  - contains an identity-number, phone or email pattern, a local file-system
    path, an internal name (checked against pipeline/banned_terms.sha256), an
    excluded incident aggregate, or a name from the optional private names
    list (path in env CW_PRIVATE_NAMES_FILE, kept outside the repository);
  - ships map data with keys outside the reviewed schema, or a source URL
    whose host is not on the reviewed source register.
"""
import hashlib
import html as html_lib
import json
import os
import re
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

import build_site as bs
import site_content as C
import sweeps as sw
from popia_gate import ID_RE, PHONE_RE

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SITE = ROOT / "build" / "site"
BANNED_HASHES_FILE = Path(__file__).resolve().parent / "banned_terms.sha256"

REQUIRED_PAGES = ["index.html", "heat-map/index.html", "high-profile/index.html",
                  "media-gap/index.html", "daily-sweeps/index.html",
                  "method/index.html", "robots.txt"]
TEXT_SUFFIXES = {".html", ".js", ".css", ".json", ".txt"}

HIDDEN_TAGS = ("template", "textarea", "noscript", "script", "style")
HIDDEN_META = re.compile(r"(?is)<meta\b[^>]*\bnoindex\b")
# Approved public contact only. Compared after HTML-entity and obfuscation decode.
ALLOWED_EMAILS = {"privacy@grokforum.site"}
AT_BRACKET = re.compile(r"(?i)\s*[\[\(\{]\s*at\s*[\]\)\}]\s*")
DOT_BRACKET = re.compile(r"(?i)\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*")
PLAIN_AT_DOT = re.compile(
    r"(?i)\b([A-Za-z0-9._%+\-]+)\s+at\s+([A-Za-z0-9\-]+(?:\s+dot\s+[A-Za-z0-9\-]+)+)\b"
)
MAILTO_RX = re.compile(r"(?i)mailto:([^\s\"\'<>`()\[\]{}|\\]+)")
EMAIL_AFTER_DECODE = re.compile(
    r"(?<![A-Za-z0-9._%+\-])([A-Za-z0-9][A-Za-z0-9._%+\-]{0,63})@"
    r"((?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,62}[A-Za-z0-9])?\.)+[A-Za-z]{2,24})"
)

class GateError(Exception):
    pass


# Format characters (Unicode category Cf), plus two that may not be Cf in
# every Unicode version: U+034F (combining grapheme joiner, usually Mn) and
# U+180E (Mongolian vowel separator).
_STRIP_ALWAYS = frozenset("͏᠎")
UNESCAPE_CAP = 8


def decode_obfuscation(text: str) -> str:
    """Turn HTML-entity, nested-entity, mailto percent-encoding and [at]/[dot] forms into plain text."""
    t = unicodedata.normalize("NFKC", text)
    for _ in range(UNESCAPE_CAP):
        nxt = html_lib.unescape(t)
        if nxt == t:
            break
        t = nxt
    else:
        # Still changing after the cap: fail closed rather than silently
        # leaving a deeper nest (e.g. 9-deep) only partly decoded.
        if html_lib.unescape(t) != t:
            raise GateError(
                f"HTML entities still changing after {UNESCAPE_CAP} unescape passes"
            )
    t = "".join(ch for ch in t if ch not in _STRIP_ALWAYS and unicodedata.category(ch) != "Cf")

    def unq(m):
        return "mailto:" + unquote(unquote(m.group(1)))

    t = MAILTO_RX.sub(unq, t)
    t = AT_BRACKET.sub("@", t)
    t = DOT_BRACKET.sub(".", t)
    t = PLAIN_AT_DOT.sub(lambda m: f"{m.group(1)}@{re.sub(r'(?i)\s+dot\s+', '.', m.group(2))}", t)
    return t


def emails_in(text: str) -> set:
    found = set()
    decoded = decode_obfuscation(text)
    for m in EMAIL_AFTER_DECODE.finditer(decoded):
        found.add(f"{m.group(1)}@{m.group(2)}".lower())
    for m in MAILTO_RX.finditer(decoded):
        tgt = m.group(1).split("?", 1)[0].rstrip(".,:!*_~").lower()
        if "@" in tgt:
            found.add(tgt)
    return found
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
    path = Path(p)
    if not path.is_file():
        raise GateError(f"private names file not found: {p}")
    try:
        return [ln.strip() for ln in path.read_text().splitlines() if ln.strip() and not ln.startswith("#")]
    except OSError as exc:
        raise GateError(f"private names file could not be read: {exc}") from None


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
        self._hidden = {t: 0 for t in HIDDEN_TAGS}
        self.in_body = False
        self.has_effective_noindex = False
        self.has_hidden_noindex = False

    def _hidden_now(self) -> bool:
        return any(self._hidden.values())

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        hidden = self._hidden_now()
        effective = not hidden and not self.in_body
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
            key = (a.get("name") or a.get("http-equiv") or "").strip().lower()
            content = a.get("content", "")
            if key in ("robots", "googlebot") and re.search(r"(?i)\bnoindex\b", content):
                if effective:
                    self.has_effective_noindex = True
                else:
                    self.has_hidden_noindex = True
            if key and effective:
                self.meta[key] = content
        if "data-label" in a and not hidden:
            self.labels.append(a["data-label"])
        if "draft" in (a.get("class") or "").split():
            self._in_draft += 1
            self._stack.append(tag)
        elif self._in_draft:
            self._stack.append(tag)
        if tag in self._hidden:
            self._hidden[tag] += 1
        elif tag == "body":
            self.in_body = True

    def handle_endtag(self, tag):
        if tag in self._hidden and self._hidden[tag]:
            self._hidden[tag] -= 1
        if self._in_draft and self._stack:
            self._stack.pop()
            if not self._stack:
                self._in_draft = 0

    def handle_data(self, data):
        self.text.append(data)
        if self._hidden_now() and HIDDEN_META.search(data):
            self.has_hidden_noindex = True
        if self._in_draft and not self._hidden_now():
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
    for addr in sorted(emails_in(text)):
        if addr not in ALLOWED_EMAILS:
            fails.append(f"{name}: email pattern")
            break
    for label, rx in (("identity-number pattern", ID_RE),
                      ("phone pattern", PHONE_RE), ("phone pattern", PHONE_LOOSE_RE),
                      ("local file-system path", PATH_RE),
                      ("excluded incident aggregate", INCIDENT_AGG_RE)):
        m = rx.search(decode_obfuscation(text)) if label.startswith("phone") or label.startswith("identity") else rx.search(text)
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


def check_html(site: Path, rel: str, text: str, allowed_urls: set, indexable: bool = False) -> list:
    fails = []
    p = _Page()
    p.feed(text)
    if indexable:
        if p.has_effective_noindex:
            fails.append(f"{rel}: noindex meta must not be present when indexing is opted in")
    elif not p.has_effective_noindex:
        extra = (" (one exists only inside template/textarea/noscript/script/style or <body>: not effective)"
                 if p.has_hidden_noindex else "")
        fails.append(f"{rel}: missing robots noindex meta{extra}")
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
        decoded_href = decode_obfuscation(href)
        if decoded_href.lower().startswith("mailto:"):
            addr = decoded_href.split(":", 1)[1].split("?", 1)[0].rstrip(".,:!*_~").lower()
            if addr not in ALLOWED_EMAILS:
                fails.append(f"{rel}: mailto is not the approved privacy contact")
        elif decoded_href.startswith(("http://", "https://", "//")):
            if decoded_href not in allowed_urls:
                fails.append(f"{rel}: link not on the reviewed source register: {decoded_href}")
        elif not _internal_ok(site, decoded_href):
            fails.append(f"{rel}: broken or non-internal link: {decoded_href}")
    for lab in p.labels:
        if lab not in C.LABELS:
            fails.append(f"{rel}: fact label not allowed: {lab}")
    return fails


def check_map_data(rel: str, text: str, allowed_urls: set) -> list:
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
    src = d.get("source")
    if src not in allowed_urls:
        fails.append(f"{rel}: source URL is not on the reviewed source register: {src}")
    for url in re.findall(r"https?://[^\s\"\']+", text):
        if url not in allowed_urls:
            fails.append(f"{rel}: URL is not on the reviewed source register: {url}")
    for key, allowed in MAP_ROW_KEYS.items():
        for row in d.get(key, []):
            if set(row) != allowed:
                fails.append(f"{rel}: {key} row keys differ from the reviewed schema")
                break
    for lay in d.get("layers", []):
        if lay.get("key") in ("gangs", "political", "farm") and lay.get("available"):
            fails.append(f"{rel}: {lay['key']} layer marked available but has no station-level SAPS data")
    return fails


def check_site(site: Path = DEFAULT_SITE, private_names=None, indexable=None, host=None) -> list:
    site = Path(site)
    if not site.is_dir():
        return [f"site directory not found: {site}"]
    live = bs.resolve_indexable(indexable, host)
    banned = load_banned_hashes()
    names = load_private_names() if private_names is None else private_names
    catalog = sw.load()
    allowed_urls = {u for _t, u, _k in C.SOURCES.values()} | sw.citation_urls(catalog)
    fails = []
    for req in REQUIRED_PAGES:
        if not (site / req).is_file():
            fails.append(f"missing required file: {req}")
    robots = site / "robots.txt"
    if robots.is_file():
        rtxt = robots.read_text()
        if live:
            if re.search(r"(?m)^Disallow:\s*/\s*$", rtxt):
                fails.append("robots.txt: must not contain 'Disallow: /' when indexing is opted in")
            if not re.search(r"(?m)^Allow:\s*/\s*$", rtxt):
                fails.append("robots.txt: must contain 'Allow: /' when indexing is opted in")
        elif not re.search(r"(?m)^Disallow:\s*/\s*$", rtxt):
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
            fails.extend(check_html(site, rel, text, allowed_urls, indexable=live))
            if sw.DISCLAIMER not in text:
                fails.append(f"{rel}: missing required external-publication disclaimer")
        if rel == "assets/map-data.js":
            fails.extend(check_map_data(rel, text, allowed_urls))
        if rel == "assets/sweeps-data.js":
            fails.extend(check_sweeps_data(rel, text, allowed_urls))
    return fails


def check_sweeps_data(rel: str, text: str, allowed_urls: set) -> list:
    prefix = "window.CW_SWEEPS = "
    if not text.startswith(prefix):
        return [f"{rel}: unexpected sweeps data wrapper"]
    try:
        json.loads(text[len(prefix):].rstrip().rstrip(";"))
    except ValueError as exc:
        return [f"{rel}: sweeps data not valid JSON ({exc})"]
    fails = []
    for url in re.findall(r"https?://[^\s\"\']+", text):
        if url not in allowed_urls:
            fails.append(f"{rel}: URL is not a reviewed sweep citation: {url}")
    if sw_disclaimer_missing(text):
        fails.append(f"{rel}: missing required external-publication disclaimer")
    return fails


def sw_disclaimer_missing(text: str) -> bool:
    return sw.DISCLAIMER not in text


def main(argv):
    site = Path(argv[1]) if len(argv) > 1 else DEFAULT_SITE
    try:
        fails = check_site(site)
    except (GateError, SystemExit) as exc:
        # resolve_indexable uses SystemExit; a missing names file uses GateError.
        message = exc.args[0] if exc.args else exc
        if isinstance(exc, SystemExit) and exc.code not in (None, 0) and not isinstance(exc.code, str):
            return exc.code
        print(f"FAIL {message}", file=sys.stderr)
        return 1
    if fails:
        for f in fails:
            print("FAIL", f)
        return 1
    print(f"PASS site POPIA and hygiene gate ({site.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
