"""Reliability: persistence and data integrity."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, parse_rows, run_sql


def test_data_persists_after_process_exit(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'Alice')")
    r = run_sql(db, "SELECT * FROM t")
    assert_success(r)
    _, rows = parse_rows(r)
    assert rows == [["1", "Alice"]]


def test_null_value_persists(db):
    run_sql(db, "CREATE TABLE t (a INTEGER, b TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, NULL)")
    r = run_sql(db, "SELECT * FROM t")
    _, rows = parse_rows(r)
    assert rows == [["1", ""]]


def test_large_value_persists(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, val TEXT)")
    big = "Z" * 100_000
    run_sql(db, f"INSERT INTO t VALUES (1, '{big}')")
    r = run_sql(db, "SELECT val FROM t")
    assert_success(r)
    assert big in r.stdout


def test_transaction_rollback_does_not_persist(db):
    run_sql(db, "CREATE TABLE t (id INTEGER)")
    run_sql(db, "BEGIN")
    run_sql(db, "INSERT INTO t VALUES (99)")
    run_sql(db, "ROLLBACK")
    r = run_sql(db, "SELECT * FROM t")
    _, rows = parse_rows(r)
    assert rows == []


def test_new_db_file_is_empty(tmp_path):
    db = tmp_path / "brand_new.db"
    run_sql(db, "CREATE TABLE t (id INTEGER)")
    r = run_sql(db, "SELECT * FROM t")
    lines = r.stdout.strip().splitlines()
    assert lines == ["id"]
