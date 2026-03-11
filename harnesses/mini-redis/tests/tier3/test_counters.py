"""Tier 3: INCR, DECR."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_failure, assert_success, assert_stdout, run_redis


def test_incr_missing_key_starts_at_1(db):
    r = run_redis(["INCR", "counter"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(integer) 1")


def test_incr_existing_integer(db):
    run_redis(["SET", "counter", "5"], data_path=db)
    r = run_redis(["INCR", "counter"], data_path=db)
    assert_stdout(r, "(integer) 6")


def test_decr_missing_key_starts_at_minus_1(db):
    r = run_redis(["DECR", "counter"], data_path=db)
    assert_stdout(r, "(integer) -1")


def test_decr_existing_integer(db):
    run_redis(["SET", "counter", "10"], data_path=db)
    r = run_redis(["DECR", "counter"], data_path=db)
    assert_stdout(r, "(integer) 9")


def test_incr_on_non_integer_exits_1(db):
    run_redis(["SET", "k", "notanumber"], data_path=db)
    r = run_redis(["INCR", "k"], data_path=db)
    assert_failure(r, code=1)
    assert r.stdout.strip() == ""
    assert "ERR" in r.stderr


def test_decr_on_non_integer_exits_1(db):
    run_redis(["SET", "k", "notanumber"], data_path=db)
    r = run_redis(["DECR", "k"], data_path=db)
    assert_failure(r, code=1)


def test_incr_survives_restart(db):
    run_redis(["INCR", "counter"], data_path=db)
    run_redis(["INCR", "counter"], data_path=db)
    r = run_redis(["GET", "counter"], data_path=db)
    assert_stdout(r, '"2"')
