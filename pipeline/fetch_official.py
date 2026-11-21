"""Collector for official files listed in data/manifest.json.

Downloads over HTTPS with certificate verification against a reviewed CA
bundle (never disabled). Any certificate or TLS failure is logged visibly:

  * a GitHub Actions error annotation and a plain line on stderr, and
  * one JSON line appended to logs/collector.log (the run log),

and the step exits 2 (TLS) or 1 (other download failure). Nothing is retried
silently. After download the file is checked against the manifest pin.

Usage: python pipeline/fetch_official.py [entry] [dest]
"""
import json
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import verify_workbook as vw

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CAFILE = ROOT / "ci" / "certs" / "saps-chain.pem"
LOG_PATH = ROOT / "logs" / "collector.log"
EXIT_TLS = 2
EXIT_DOWNLOAD = 1


def _is_tls_error(exc: BaseException) -> bool:
    if isinstance(exc, ssl.SSLError):
        return True
    reason = getattr(exc, "reason", None)
    return isinstance(reason, ssl.SSLError)


def log_failure(kind: str, url: str, exc: BaseException, log_path: Path = LOG_PATH) -> None:
    message = f"{kind} error fetching {url}: {exc}"
    # Visible in the Actions UI as an annotation, and plain on stderr.
    print(f"::error title=Collector {kind} failure::{message}", file=sys.stderr)
    print(f"FAIL {message}", file=sys.stderr)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "time_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": kind,
        "url": url,
        "error": f"{type(exc).__name__}: {exc}",
    }
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def ssl_context(cafile: Path = DEFAULT_CAFILE) -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=str(cafile))
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def fetch(url: str, dest: Path, cafile: Path = DEFAULT_CAFILE, log_path: Path = LOG_PATH,
          opener=urllib.request.urlopen, timeout: int = 120) -> int:
    try:
        with opener(url, context=ssl_context(cafile), timeout=timeout) as resp:
            data = resp.read()
    except Exception as exc:  # noqa: BLE001 - every failure is logged and fails the step
        if _is_tls_error(exc):
            log_failure("TLS", url, exc, log_path)
            return EXIT_TLS
        log_failure("download", url, exc, log_path)
        return EXIT_DOWNLOAD
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    print(f"downloaded {len(data)} bytes from {url}")
    return 0


def main(argv) -> int:
    entry = argv[1] if len(argv) > 1 else "workbook"
    manifest = vw.load_manifest()
    meta = manifest.get(entry)
    if not isinstance(meta, dict) or "url" not in meta:
        print(f"FAIL manifest has no fetchable entry {entry!r}", file=sys.stderr)
        return EXIT_DOWNLOAD
    dest = Path(argv[2]) if len(argv) > 2 else ROOT / meta["path"]
    code = fetch(meta["url"], dest)
    if code:
        return code
    if entry == "workbook":
        vw.verify(dest, manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
