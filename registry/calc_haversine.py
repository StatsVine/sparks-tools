import csv
import json
from decimal import Decimal

from haversine import Unit, haversine


def calculate_distances(locations: list[dict], unit: Unit):
    all_distances = {}
    for src in locations:
        src_distances = {}
        for dest in locations:
            if src == dest:
                continue
            # FIXME hardcoded field names
            (src_coords, dest_coords) = (
                (Decimal(loc["latitude"]), Decimal(loc["longitude"]))
                for loc in [src, dest]
            )
            dist = haversine(src_coords, dest_coords, unit=unit)
            # FIXME hardcoded id field name
            src_distances[dest["id"]] = int(dist)
        all_distances[src["id"]] = dict(
            sorted(src_distances.items(), key=lambda s: s[1])
        )
    return all_distances


def process_csv(csv_path, unit: Unit):
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = [dict(d) for d in reader]

    distances = calculate_distances(rows, unit)
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
    args = parser.parse_args()

    distances = process_csv(args.csv, args.units)
    print(json.dumps(distances))
