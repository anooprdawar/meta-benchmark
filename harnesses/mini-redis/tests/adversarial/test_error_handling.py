"""Adversarial: wrong arity, unknown commands, malformed input."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_failure, run_redis


def test_unknown_command_exits_1(db):
    r = run_redis(["XREAD", "k"], data_path=db)
    assert_failure(r)
    assert "ERR unknown command" in r.stderr

def test_set_no_args_exits_1(db):
    r = run_redis(["SET"], data_path=db)
    assert_failure(r)

def test_set_one_arg_exits_1(db):
    r = run_redis(["SET", "onlykey"], data_path=db)
    assert_failure(r)

def test_get_no_args_exits_1(db):
    r = run_redis(["GET"], data_path=db)
    assert_failure(r)

def test_del_no_args_exits_1(db):
    r = run_redis(["DEL"], data_path=db)
    assert_failure(r)

def test_mset_odd_args_exits_1(db):
    r = run_redis(["MSET", "k1", "v1", "k2"], data_path=db)
    assert_failure(r)

def test_expire_no_seconds_exits_1(db):
    run_redis(["SET", "k", "v"], data_path=db)
    r = run_redis(["EXPIRE", "k"], data_path=db)
    assert_failure(r)

def test_expire_non_integer_seconds_exits_1(db):
    run_redis(["SET", "k", "v"], data_path=db)
    r = run_redis(["EXPIRE", "k", "notanint"], data_path=db)
    assert_failure(r)

def test_hset_odd_field_value_args_exits_1(db):
    r = run_redis(["HSET", "h", "field_only"], data_path=db)
    assert_failure(r)

def test_no_command_exits_1(db):
    r = run_redis([], data_path=db)
    assert_failure(r)

def test_empty_string_command_exits_1(db):
    r = run_redis([""], data_path=db)
    assert_failure(r)
