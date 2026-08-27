import csv
import functools
import re
import sys
import traceback
from collections import defaultdict

import yaml


TYPE_REFERENCE = "reference"
VALID_TYPES = ["string", "integer", "enum", "decimal", TYPE_REFERENCE]


def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


@functools.cache
def load_reference_values(file_path, column_name):
    values = set()
    with open(file_path, "r", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            values.add(row[column_name])
    return values


def validate_field(value, rules, field_name, row_num):
    errors = []

    if "active" in rules and not rules.get("active"):
        return errors

    # Check if required value present
    if rules.get("required") and not value:
        errors.append(f"Row {row_num}: '{field_name}' is required")

    # Check whitespace
    if value and len(value) != len(value.strip()):
        errors.append(
            f"Row {row_num}: '{field_name}' contains leading/trailing whitespace."
        )

    # Validate pattern
    if "pattern" in rules and value:
        if not re.fullmatch(rules["pattern"], value):
            errors.append(
                f"Row {row_num}: '{field_name}' value '{value}' does not match pattern"
            )

    # Check enum value valid
    if value and "enum" in rules and value not in rules["enum"]:
        errors.append(
            f"Row {row_num}: '{field_name}' value '{value}' not in allowed values"
        )

    # Check ref value valid
    if value and "type" in rules and rules["type"] == TYPE_REFERENCE:
        ref_values = load_reference_values(
            rules["reference_file"], rules["reference_column"]
        )
        if value not in ref_values:
            errors.append(
                f"Row {row_num}: '{field_name}' value '{value}' not in reference file"
            )

    return errors


def check_duplicate_ids(
    id_field_name: str,
    id_val: any,
    seen_ids: set,
    line_idx: int,
    scope: tuple = (),
    scope_fields: list = None,
):
    """Flag a repeated value for a unique field.

    An empty value is never a duplicate -- a blank means "no id here", and
    several rows may legitimately have none.

    `scope` narrows uniqueness to rows sharing those values. Some identifiers
    are only unique within a namespace: ESPN reuses team id 11 for the
    Athletics, the Colts and the Pacers, and league names such as "Premier
    League" recur across sports.
    """
    errors = []

    if not id_val:
        return errors

    key = scope + (id_val,)
    if key in seen_ids:
        if scope:
            where = ", ".join(f"{f}='{v}'" for f, v in zip(scope_fields or [], scope))
            errors.append(
                f"Row {line_idx}: Duplicate value '{id_val}' for column "
                f"'{id_field_name}' within {where}"
            )
        else:
            errors.append(
                f"Row {line_idx}: Duplicate value '{id_val}' for column '{id_field_name}'"
            )
    else:
        seen_ids.add(key)
    return errors


def validate_csv(csv_path, core_schema_path, fail_fast=False):
    errors = []

    # Load schemas
    core_schema = load_yaml(core_schema_path)["fields"]

    seen_ids = defaultdict(set)

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        prev_id = None

        # Verify schema
        for field, rules in core_schema.items():
            # Verify field type
            field_type = rules.get("type")
            if field_type not in VALID_TYPES:
                errors.append(f"Schema: {field} is invalid type '{field_type}'")
            # Verify reference type
            # Verify unique_within references real fields; a typo here would
            # silently widen uniqueness back to global
            for scope_field in rules.get("unique_within", []):
                if scope_field not in core_schema:
                    errors.append(
                        f"Schema: {field} unique_within references "
                        f"unknown field '{scope_field}'"
                    )
            # Verify reference type
            if field_type == "reference":
                try:
                    load_reference_values(
                        rules["reference_file"], rules["reference_column"]
                    )
                except Exception as e:
                    errors.append(f"Error loading reference file for {field}: {e}")
                    traceback.print_exc()
        # Escape for schema errors
        if errors:
            print(f"\nSchema validation failed with {len(errors)} errors:\n")
            for e in errors:
                print(e)
            sys.exit(2)

        # Verify row-by-row
        for i, row in enumerate(reader, start=2):  # start=2 to account for header
            # Verify sorting
            if prev_id and row.get("sparks_id") < prev_id:
                errors.append(
                    f"Row {i}: Not sorted, ID '{row.get('sparks_id')}' comes after '{prev_id}'"
                )
                if fail_fast and errors:
                    print("\n".join(errors))
                    sys.exit(1)
            for field, rules in core_schema.items():
                value = row.get(field, "")
                errors.extend(validate_field(value, rules, field, i))
                if rules.get("unique", False):
                    # Metadata fields assumed to not be unique
                    scope_fields = rules.get("unique_within", [])
                    scope = tuple(row.get(f, "") for f in scope_fields)
                    errors.extend(
                        check_duplicate_ids(
                            field, value, seen_ids[field], i, scope, scope_fields
                        )
                    )
                if fail_fast and errors:
                    print("\n".join(errors))
                    sys.exit(1)
            prev_id = row["sparks_id"]

    if errors:
        print(f"\nValidation failed with {len(errors)} errors:\n")
        for e in errors:
            print(e)
        sys.exit(1)
    else:
        print("Validation successful ✅")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate CSV against schema")
    parser.add_argument("csv")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first error")
    args = parser.parse_args()

    validate_csv(args.csv, args.schema, fail_fast=args.fail_fast)
