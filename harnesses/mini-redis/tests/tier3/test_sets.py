"""Tier 3: SADD, SREM, SMEMBERS, SISMEMBER."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, assert_stdout, run_redis


def test_sadd_new_members(db):
    r = run_redis(["SADD", "s", "a", "b", "c"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(integer) 3")


def test_sadd_duplicate_not_counted(db):
    run_redis(["SADD", "s", "a", "b"], data_path=db)
    r = run_redis(["SADD", "s", "b", "c"], data_path=db)
    assert_stdout(r, "(integer) 1")  # only "c" is new


def test_srem_removes_member(db):
    run_redis(["SADD", "s", "a", "b", "c"], data_path=db)
    r = run_redis(["SREM", "s", "b"], data_path=db)
    assert_stdout(r, "(integer) 1")


def test_srem_missing_member_returns_0(db):
    run_redis(["SADD", "s", "a"], data_path=db)
    r = run_redis(["SREM", "s", "nosuchmember"], data_path=db)
    assert_stdout(r, "(integer) 0")


def test_smembers_lexicographic_order(db):
    run_redis(["SADD", "s", "banana", "apple", "cherry"], data_path=db)
    r = run_redis(["SMEMBERS", "s"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "apple"', '2) "banana"', '3) "cherry"']


def test_smembers_empty_set(db):
    r = run_redis(["SMEMBERS", "nosuchkey"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(empty set)")


def test_sismember_present(db):
    run_redis(["SADD", "s", "member"], data_path=db)
    r = run_redis(["SISMEMBER", "s", "member"], data_path=db)
    assert_stdout(r, "(integer) 1")


def test_sismember_absent(db):
    run_redis(["SADD", "s", "a"], data_path=db)
    r = run_redis(["SISMEMBER", "s", "notamember"], data_path=db)
    assert_stdout(r, "(integer) 0")
