"""Reliability: corrupt JSON file and large value handling."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, assert_stdout, run_redis


def test_corrupt_json_exits_nonzero(tmp_path):
    """Corrupt JSON file must not crash with traceback — must exit non-zero."""
    db = tmp_path / "mini_redis.json"
    db.write_text("{ this is not valid json !!!")
    r = run_redis(["GET", "k"], data_path=db)
    assert r.returncode != 0, "Corrupt file should cause non-zero exit"
    assert r.stderr.strip() != "", "Must print error to stderr"
    assert "Traceback" not in r.stderr, "Must not print Python traceback"


def test_large_value_stored_and_retrieved(db):
    """1MB value must be stored and retrieved correctly."""
    big = "A" * 1_000_000
    r_set = run_redis(["SET", "bigkey", big], data_path=db)
    assert_success(r_set)
    r_get = run_redis(["GET", "bigkey"], data_path=db)
    assert_success(r_get)
    assert r_get.stdout.strip() == f'"{big}"'
