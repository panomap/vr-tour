#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def outer_ring(geometry):
    if not geometry:
        return None
    if geometry.get("type") == "Polygon":
        return geometry.get("coordinates", [None])[0]
    if geometry.get("type") == "MultiPolygon":
        polygons = geometry.get("coordinates", [])
        return polygons[0][0] if polygons and polygons[0] else None
    return None


def centroid(ring):
    if not ring:
        return None
    points = ring[:-1] if ring[0] == ring[-1] else ring
    if not points:
        return None
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def point_in_ring(point, ring):
    if not point or not ring or len(ring) < 4:
        return False

    x, y = point
    inside = False
    j = len(ring) - 1

    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        intersects = ((yi > y) != (yj > y)) and x < ((xj - xi) * (y - yi)) / (yj - yi) + xi
        if intersects:
            inside = not inside
        j = i

    return inside


def feature_id(feature):
    props = feature.get("properties") or {}
    return str(props.get("sector_id") or props.get("id") or props.get("name") or "unknown").strip()


def split_lots(lots_path, sectors_path, output_dir):
    lots_data = json.loads(lots_path.read_text(encoding="utf-8"))
    sectors_data = json.loads(sectors_path.read_text(encoding="utf-8"))
    lots = lots_data.get("features") or []
    sectors = []

    for sector_feature in sectors_data.get("features") or []:
        sector_ring = outer_ring(sector_feature.get("geometry"))
        sector_id = feature_id(sector_feature)
        if sector_id and sector_ring:
            sectors.append((sector_id, sector_feature, sector_ring))

    output_dir.mkdir(parents=True, exist_ok=True)
    buckets = {sector_id: [] for sector_id, _, _ in sectors}
    unassigned = []

    for lot in lots:
        lot_ring = outer_ring(lot.get("geometry"))
        lot_center = centroid(lot_ring)
        matched_sector = None

        for sector_id, _, sector_ring in sectors:
            if point_in_ring(lot_center, sector_ring):
                matched_sector = sector_id
                break

        if matched_sector:
            lot_copy = dict(lot)
            props = dict(lot_copy.get("properties") or {})
            props["sector_id"] = matched_sector
            lot_copy["properties"] = props
            buckets[matched_sector].append(lot_copy)
        else:
            unassigned.append(lot)

    for sector_id, sector_lots in buckets.items():
        out = {
            "type": "FeatureCollection",
            "features": sector_lots,
        }
        (output_dir / f"{sector_id}.geojson").write_text(
            json.dumps(out, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    unassigned_out = {
        "type": "FeatureCollection",
        "features": unassigned,
    }
    (output_dir / "unassigned.geojson").write_text(
        json.dumps(unassigned_out, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    print(f"Lots: {len(lots)}")
    print(f"Sectors: {len(sectors)}")
    for sector_id, sector_lots in buckets.items():
        print(f"{sector_id}: {len(sector_lots)}")
    print(f"unassigned: {len(unassigned)}")


def main():
    parser = argparse.ArgumentParser(description="Split lot GeoJSON into files by sector polygons.")
    parser.add_argument("--lots", default="data/lots.geojson", type=Path)
    parser.add_argument("--sectors", default="data/sectors.geojson", type=Path)
    parser.add_argument("--out", default="data/sector-lots", type=Path)
    args = parser.parse_args()
    split_lots(args.lots, args.sectors, args.out)


if __name__ == "__main__":
    main()
