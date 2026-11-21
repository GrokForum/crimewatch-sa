"""Check a downloaded official SAPS workbook against the reviewed pin.

The sha256 pin in data/manifest.json is bumped only by a reviewed change.
A missing file or a size/hash mismatch fails closed (exit 1).
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "data" / "manifest.json"


REQUIRED_KEYS = ("url", "path", "size", "sha256")


def load_manifest(path=MANIFEST_PATH):
    """Read the reviewed manifest, or exit 1 with a plain message if it is unusable."""
    try:
        manifest = json.loads(Path(path).read_text())
    except FileNotFoundError:
        raise SystemExit(f"FAIL manifest not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"FAIL manifest is not valid JSON ({path}): {exc}")
    meta = manifest.get("workbook") if isinstance(manifest, dict) else None
    if not isinstance(meta, dict):
        raise SystemExit(f"FAIL manifest has no 'workbook' entry: {path}")
    missing = [k for k in REQUIRED_KEYS if k not in meta]
    if missing:
        raise SystemExit(f"FAIL manifest 'workbook' entry is missing {missing}: {path}")
    if not isinstance(meta["size"], int) or not isinstance(meta["sha256"], str) or len(meta["sha256"]) != 64:
        raise SystemExit(f"FAIL manifest 'workbook' size/sha256 malformed: {path}")
    return manifest


def verify(workbook: Path, manifest=None) -> None:
    meta = (manifest or load_manifest())["workbook"]
    workbook = Path(workbook)
    if not workbook.is_file():
        raise SystemExit(f"FAIL missing workbook: {workbook}")
    data = workbook.read_bytes()
    size = len(data)
    digest = hashlib.sha256(data).hexdigest()
    if size != meta["size"] or digest != meta["sha256"]:
        raise SystemExit(
            "FAIL workbook pin mismatch: "
            f"size={size} sha256={digest} "
            f"(expected size={meta['size']} sha256={meta['sha256']}). "
            "The pin is bumped only by a reviewed change."
        )
    if data[:2] != b"PK":
        raise SystemExit("FAIL workbook is not a zip/xlsx")
    print(f"PASS workbook pin size={size} sha256={digest}")


def main(argv):
    manifest = load_manifest()
    default = ROOT / manifest["workbook"]["path"]
    path = Path(argv[1]) if len(argv) > 1 else default
    verify(path, manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
