"""Adversarial: edge cases — empty values, large values, key edge cases."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, assert_stdout, run_redis


def test_empty_string_value(db):
    r = run_redis(["SET", "k", ""], data_path=db)
    assert_success(r)
    r2 = run_redis(["GET", "k"], data_path=db)
    assert_stdout(r2, '""')


def test_value_with_spaces(db):
    run_redis(["SET", "k", "hello world"], data_path=db)
    r = run_redis(["GET", "k"], data_path=db)
    assert_stdout(r, '"hello world"')


def test_numeric_string_value(db):
    run_redis(["SET", "k", "42"], data_path=db)
    r = run_redis(["GET", "k"], data_path=db)
    assert_stdout(r, '"42"')


def test_large_value(db):
    big = "x" * 100_000
    run_redis(["SET", "big", big], data_path=db)
    r = run_redis(["GET", "big"], data_path=db)
    assert_success(r)
    # Value should be returned quoted
    assert r.stdout.strip() == f'"{big}"'


def test_key_with_colon(db):
    run_redis(["SET", "user:1:name", "Alice"], data_path=db)
    r = run_redis(["GET", "user:1:name"], data_path=db)
    assert_stdout(r, '"Alice"')


def test_del_multiple_some_missing(db):
    run_redis(["SET", "exists", "v"], data_path=db)
    r = run_redis(["DEL", "exists", "missing1", "missing2"], data_path=db)
    assert_stdout(r, "(integer) 1")


def test_lrange_out_of_bounds_returns_available(db):
    run_redis(["RPUSH", "mylist", "a", "b"], data_path=db)
    r = run_redis(["LRANGE", "mylist", "0", "100"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "a"', '2) "b"']


def test_lrange_empty_range(db):
    run_redis(["RPUSH", "mylist", "a", "b", "c"], data_path=db)
    r = run_redis(["LRANGE", "mylist", "5", "10"], data_path=db)
    assert_stdout(r, "(empty list)")


def test_incr_persists_across_restart(db):
    run_redis(["INCR", "ctr"], data_path=db)
    run_redis(["INCR", "ctr"], data_path=db)
    run_redis(["INCR", "ctr"], data_path=db)
    r = run_redis(["GET", "ctr"], data_path=db)
    assert_stdout(r, '"3"')


def test_hgetall_single_field(db):
    run_redis(["HSET", "h", "onlyfield", "onlyvalue"], data_path=db)
    r = run_redis(["HGETALL", "h"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ["onlyfield", "onlyvalue"]
