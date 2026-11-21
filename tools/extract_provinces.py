"""Rebuild data/geo/za_provinces.geojson from the pinned Natural Earth source.

Source (public domain): Natural Earth 10m admin-1 states and provinces,
release v5.1.2. The URL, size and sha256 of the source file are pinned in
data/manifest.json under "provinces_geo_source"; the pin is bumped only by a
reviewed change. Only the nine South African provinces are kept, with the
province name and geometry, coordinates rounded to 3 decimals (about 100 m), mainland only
(the Prince Edward Islands are dropped).

Usage: python tools/extract_provinces.py path/to/ne_10m_admin_1_states_provinces.geojson
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "geo" / "za_provinces.geojson"


def _round(coords):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], 3), round(coords[1], 3)]
    return [_round(c) for c in coords]


def _dedupe_ring(ring):
    out = []
    for pt in ring:
        if not out or out[-1] != pt:
            out.append(pt)
    return out


def extract(src: Path) -> dict:
    manifest = json.loads((ROOT / "data" / "manifest.json").read_text())
    pin = manifest["provinces_geo_source"]
    data = src.read_bytes()
    if hashlib.sha256(data).hexdigest() != pin["sha256"] or len(data) != pin["size"]:
        raise SystemExit("FAIL Natural Earth source does not match the reviewed pin")
    src_json = json.loads(data)
    feats = []
    for f in src_json["features"]:
        if f["properties"].get("adm0_a3") != "ZAF":
            continue
        geom = f["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        polys = [[_dedupe_ring(_round(r)) for r in poly] for poly in polys]
        # Drop the sub-Antarctic Prince Edward Islands (south of 40 S): they are
        # not part of any police district in the RAW Data sheet and would
        # stretch the mainland map.
        polys = [poly for poly in polys if max(pt[1] for pt in poly[0]) > -40]
        feats.append({
            "type": "Feature",
            "properties": {"province": f["properties"]["name"]},
            "geometry": {"type": "MultiPolygon", "coordinates": polys},
        })
    feats.sort(key=lambda x: x["properties"]["province"])
    if len(feats) != 9:
        raise SystemExit(f"FAIL expected 9 provinces, got {len(feats)}")
    return {"type": "FeatureCollection",
            "attribution": "Made with Natural Earth (public domain), v5.1.2",
            "features": feats}


def main(argv):
    out = extract(Path(argv[1]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
