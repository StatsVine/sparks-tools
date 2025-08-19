import argparse
import csv
import json
import os
from collections import defaultdict
from os import path
from pathlib import Path

import yaml


def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_fields(schema_path):
    schema = load_yaml(schema_path)["fields"]
    fields = {
        k: v.get("unique", False) for k, v in schema.items() if v.get("active", True)
    }
    return fields


def load_csv(filepath):
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_csv(data, filename, fields):
    with open(filename, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)
    return filename


def write_json(data, filepath, fields, minified=False):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=None if minified else 2, ensure_ascii=False)
    return filepath


def write_json_min(data, file, fields):
    write_json(data, file, fields)


def write_ndjson(data, filepath, fields):
    with open(filepath, "w", encoding="utf-8") as f:
        for row in data:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return filepath


def write_field_mappings(file, data, dest_dir, fields):
    os.makedirs(dest_dir, exist_ok=True)
    for field, field_unique in fields.items():
        if field_unique:
            mapping = {}
        else:
            mapping = defaultdict(list)
        for row in data:
            id_value = row.get(field)
            if id_value:
                if field_unique:
                    mapping[id_value] = row
                else:
                    mapping[id_value].append(row)
        if not mapping:
            continue
        write_json(mapping, dest_dir / f"{file}.{field}.json", fields, minified=False)
        write_json(
            mapping, dest_dir / f"{file}.{field}.min.json", fields, minified=True
        )


FILE_WRITERS = {
    write_csv: ".csv",
    write_json: ".json",
    write_json_min: ".min.json",
    write_ndjson: ".ndjson",
}


def process_file(file: str, csv_file: Path, schema_file: Path, dest_dir: Path):
    os.makedirs(dest_dir, exist_ok=True)

    fields = load_fields(schema_file)
    data = load_csv(csv_file)
    data = [{k: d[k] or None for k in fields if k in d} for d in data]

    for writer, ext in FILE_WRITERS.items():
        writer(data, path.join(dest_dir, file + ext), fields)

    write_field_mappings(file, data, Path(dest_dir) / "by_field", fields)


def process_files(
    files: list[str] | set[str], csv_dir: Path, schema_dir: Path, dest_dir: Path
):
    for file in files:
        process_file(
            file,
            path.join(csv_dir, file + ".csv"),
            path.join(schema_dir, file + ".yaml"),
            path.join(dest_dir, file),
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", help="File to run", default=None, nargs="*")
    parser.add_argument("--csv_dir", help="Path to csvs", default="data/")
    parser.add_argument("--schema_dir", help="Path to schemas", default="schema/")
    parser.add_argument("--dist_dir", help="Path to dist", default="dist/")
    args = parser.parse_args()

    files = (
        args.files
        if args.files
        else [
            Path(f).stem
            for f in os.listdir(args.schema_dir)
            if path.isfile(path.join(args.schema_dir, f))
        ]
    )

    os.makedirs(args.dist_dir, exist_ok=True)

    process_files(files, Path(args.csv_dir), Path(args.schema_dir), Path(args.dist_dir))


if __name__ == "__main__":
    main()
