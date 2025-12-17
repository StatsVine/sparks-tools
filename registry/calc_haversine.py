import csv
import json
from decimal import Decimal

from haversine import Unit, haversine


def calculate_distances(
    locations: list[dict], unit: Unit, min_distance: int, max_distance: int
):
    all_distances = {}
    for src in locations:
        src_distances = {}
        for dest in locations:
            if src == dest:
                continue
            # FIXME hardcoded field names
            (src_coords, dest_coords) = (
                (Decimal(loc["latitude_dd"]), Decimal(loc["longitude_dd"]))
                for loc in [src, dest]
            )
            dist = haversine(src_coords, dest_coords, unit=unit)
            # FIXME hardcoded id field name
            if dist >= min_distance and dist <= max_distance:
                src_distances[dest["sparks_id"]] = int(dist)
        all_distances[src["sparks_id"]] = dict(
            sorted(src_distances.items(), key=lambda s: s[1])
        )
    return all_distances


def process_csv(csv_path, unit: Unit, min_distance: int, max_distance: int):
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = [dict(d) for d in reader]

    distances = calculate_distances(rows, unit, min_distance, max_distance)
    return distances


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Calculate distances between a list of Places"
    )
    parser.add_argument("csv")
    units = {u.value for u in Unit}
    parser.add_argument(
        "--units", help="Unit", type=str, choices=units, default="mi", required=False
    )
    parser.add_argument(
        "--filter-min",
        help="Filter by min distance",
        type=int,
        default=0,
        required=False,
    )
    parser.add_argument(
        "--filter-max",
        help="Filter by max distance",
        type=int,
        default=5000,
        required=False,
    )
    args = parser.parse_args()

    distances = process_csv(
        args.csv, args.units, min_distance=args.filter_min, max_distance=args.filter_max
    )
    print(json.dumps(distances))
