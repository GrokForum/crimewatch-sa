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


def load_manifest(path=MANIFEST_PATH):
    return json.loads(Path(path).read_text())


def verify(workbook: Path, manifest=None) -> None:
    meta = (manifest or load_manifest())["workbook"]
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
