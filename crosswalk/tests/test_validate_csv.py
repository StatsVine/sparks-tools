"""Tests for validate_csv, focused on uniqueness.

Run with `pytest crosswalk/tests/` from the repo root.
"""

import subprocess
import sys
import textwrap
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validate_csv import check_duplicate_ids  # noqa: E402


VALIDATOR = Path(__file__).resolve().parents[1] / "validate_csv.py"


# --- unit: check_duplicate_ids ------------------------------------------


def test_global_uniqueness_flags_repeat():
    seen = set()
    assert check_duplicate_ids("espn_id", "11", seen, 2) == []
    errors = check_duplicate_ids("espn_id", "11", seen, 3)
    assert len(errors) == 1
    assert "Duplicate value '11'" in errors[0]


def test_blank_is_never_a_duplicate():
    seen = set()
    for row in range(2, 6):
        assert check_duplicate_ids("espn_id", "", seen, row) == []


def test_same_value_allowed_in_different_scopes():
    """ESPN reuses team id 11 across sports."""
    seen = set()
    fields = ["sport_id"]
    assert check_duplicate_ids("espn_id", "11", seen, 2, ("baseball",), fields) == []
    assert check_duplicate_ids("espn_id", "11", seen, 3, ("football",), fields) == []
    assert check_duplicate_ids("espn_id", "11", seen, 4, ("basketball",), fields) == []


def test_repeat_within_one_scope_is_flagged():
    seen = set()
    fields = ["sport_id"]
    check_duplicate_ids("espn_id", "11", seen, 2, ("baseball",), fields)
    errors = check_duplicate_ids("espn_id", "11", seen, 3, ("baseball",), fields)
    assert len(errors) == 1
    assert "within sport_id='baseball'" in errors[0]


# --- integration: full validate_csv run ---------------------------------


def _run(tmp_path, schema, rows):
    (tmp_path / "s.yaml").write_text(textwrap.dedent(schema))
    (tmp_path / "d.csv").write_text(rows)
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(tmp_path / "d.csv"),
            "--schema",
            str(tmp_path / "s.yaml"),
        ],
        capture_output=True,
        text=True,
    )


SCOPED = """\
    ---
    fields:
      sparks_id:
        type: string
        required: true
        unique: true
      sport_id:
        type: string
        required: true
      espn_id:
        type: integer
        required: false
        unique: true
        unique_within: [sport_id]
"""


def test_scoped_collision_across_sports_passes(tmp_path):
    r = _run(
        tmp_path, SCOPED, "sparks_id,sport_id,espn_id\na,baseball,11\nb,football,11\n"
    )
    assert r.returncode == 0, r.stdout


def test_scoped_collision_within_sport_fails(tmp_path):
    r = _run(
        tmp_path, SCOPED, "sparks_id,sport_id,espn_id\na,baseball,11\nb,baseball,11\n"
    )
    assert r.returncode == 1
    assert "within sport_id='baseball'" in r.stdout


def test_unknown_unique_within_field_is_a_schema_error(tmp_path):
    """A typo would otherwise silently widen uniqueness back to global."""
    bad = SCOPED.replace("unique_within: [sport_id]", "unique_within: [sprot_id]")
    r = _run(tmp_path, bad, "sparks_id,sport_id,espn_id\na,baseball,11\n")
    assert r.returncode == 2
    assert "unknown field 'sprot_id'" in r.stdout


def test_unscoped_uniqueness_unchanged(tmp_path):
    """Regression: fields without unique_within stay globally unique."""
    plain = SCOPED.replace("    unique_within: [sport_id]\n", "")
    r = _run(
        tmp_path, plain, "sparks_id,sport_id,espn_id\na,baseball,11\nb,football,11\n"
    )
    assert r.returncode == 1
    assert "Duplicate value '11'" in r.stdout
