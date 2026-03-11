"""Reliability: corrupt database file handling."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import run_sql


def test_corrupt_db_exits_nonzero(tmp_path):
    db = tmp_path / "corrupt.db"
    db.write_bytes(b"\x00\xff\xde\xad\xbe\xef" * 100)
    r = run_sql(db, "SELECT * FROM t")
    assert r.returncode != 0
    assert r.stderr.strip() != ""
    assert "Traceback" not in r.stderr


def test_truncated_db_exits_nonzero(tmp_path):
    db = tmp_path / "truncated.db"
    # Write partial content
    db.write_text("partial json {")
    r = run_sql(db, "SELECT * FROM t")
    assert r.returncode != 0
    assert "Traceback" not in r.stderr
