"""Extension: CREATE INDEX and EXPLAIN — 16 tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_failure, assert_success, assert_stdout, parse_rows, run_sql


def test_create_index_returns_ok(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    r = run_sql(db, "CREATE INDEX idx_name ON t(name)")
    assert_success(r)
    assert_stdout(r, "OK")


def test_create_index_on_nonexistent_table_exits_1(db):
    r = run_sql(db, "CREATE INDEX idx ON nosuchable(col)")
    assert_failure(r)


def test_explain_seq_scan_no_index_word(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    r = run_sql(db, "EXPLAIN SELECT * FROM t WHERE id = 1")
    assert_success(r)
    assert "index" not in r.stdout.lower()


def test_explain_with_index_contains_index_word(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    run_sql(db, "CREATE INDEX idx_id ON t(id)")
    r = run_sql(db, "EXPLAIN SELECT * FROM t WHERE id = 1")
    assert_success(r)
    assert "index" in r.stdout.lower()


def test_index_does_not_break_select(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, val TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'a')")
    run_sql(db, "INSERT INTO t VALUES (2, 'b')")
    run_sql(db, "CREATE INDEX idx_id ON t(id)")
    r = run_sql(db, "SELECT val FROM t WHERE id = 2")
    assert_success(r)
    _, rows = parse_rows(r)
    assert rows == [["b"]]


def test_index_does_not_break_order(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, val TEXT)")
    run_sql(db, "INSERT INTO t VALUES (3, 'c')")
    run_sql(db, "INSERT INTO t VALUES (1, 'a')")
    run_sql(db, "INSERT INTO t VALUES (2, 'b')")
    run_sql(db, "CREATE INDEX idx_id ON t(id)")
    r = run_sql(db, "SELECT val FROM t ORDER BY id ASC")
    _, rows = parse_rows(r)
    assert [r[0] for r in rows] == ["a", "b", "c"]


def test_index_does_not_break_insert(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, val TEXT)")
    run_sql(db, "CREATE INDEX idx_id ON t(id)")
    run_sql(db, "INSERT INTO t VALUES (10, 'ten')")
    r = run_sql(db, "SELECT val FROM t WHERE id = 10")
    _, rows = parse_rows(r)
    assert rows == [["ten"]]


def test_index_does_not_break_update(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, val TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'old')")
    run_sql(db, "CREATE INDEX idx_id ON t(id)")
    run_sql(db, "UPDATE t SET val = 'new' WHERE id = 1")
    r = run_sql(db, "SELECT val FROM t WHERE id = 1")
    _, rows = parse_rows(r)
    assert rows == [["new"]]


def test_index_does_not_break_delete(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, val TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'a')")
    run_sql(db, "INSERT INTO t VALUES (2, 'b')")
    run_sql(db, "CREATE INDEX idx_id ON t(id)")
    run_sql(db, "DELETE FROM t WHERE id = 1")
    r = run_sql(db, "SELECT * FROM t")
    _, rows = parse_rows(r)
    assert len(rows) == 1


def test_create_index_on_text_column(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT)")
    r = run_sql(db, "CREATE INDEX idx_name ON t(name)")
    assert_success(r)


def test_explain_no_index_on_unindexed_col(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT, score REAL)")
    run_sql(db, "CREATE INDEX idx_id ON t(id)")
    # Query on 'score' which has no index
    r = run_sql(db, "EXPLAIN SELECT * FROM t WHERE score > 5.0")
    assert_success(r)
    assert "index" not in r.stdout.lower()


def test_explain_uses_index_on_indexed_col(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, name TEXT, score REAL)")
    run_sql(db, "CREATE INDEX idx_score ON t(score)")
    r = run_sql(db, "EXPLAIN SELECT * FROM t WHERE score > 5.0")
    assert_success(r)
    assert "index" in r.stdout.lower()


def test_multiple_indexes(db):
    run_sql(db, "CREATE TABLE t (a INTEGER, b TEXT, c REAL)")
    run_sql(db, "CREATE INDEX idx_a ON t(a)")
    run_sql(db, "CREATE INDEX idx_b ON t(b)")
    r_a = run_sql(db, "EXPLAIN SELECT * FROM t WHERE a = 1")
    r_b = run_sql(db, "EXPLAIN SELECT * FROM t WHERE b = 'x'")
    assert "index" in r_a.stdout.lower()
    assert "index" in r_b.stdout.lower()


def test_index_persists_after_restart(db):
    run_sql(db, "CREATE TABLE t (id INTEGER, val TEXT)")
    run_sql(db, "INSERT INTO t VALUES (1, 'a')")
    run_sql(db, "CREATE INDEX idx_id ON t(id)")
    # New process — index must still work
    r = run_sql(db, "EXPLAIN SELECT * FROM t WHERE id = 1")
    assert_success(r)
    assert "index" in r.stdout.lower()


def test_explain_output_not_empty(db):
    run_sql(db, "CREATE TABLE t (id INTEGER)")
    r = run_sql(db, "EXPLAIN SELECT * FROM t")
    assert_success(r)
    assert r.stdout.strip() != ""


def test_index_name_can_be_reused_after_drop(db):
    """After DROP TABLE, the index name should be free to reuse."""
    run_sql(db, "CREATE TABLE t (id INTEGER)")
    run_sql(db, "CREATE INDEX idx ON t(id)")
    run_sql(db, "DROP TABLE t")
    run_sql(db, "CREATE TABLE t2 (val TEXT)")
    r = run_sql(db, "CREATE INDEX idx ON t2(val)")
    assert_success(r)
