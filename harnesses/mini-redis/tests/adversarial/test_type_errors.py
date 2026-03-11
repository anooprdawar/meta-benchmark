"""Adversarial: operations on keys holding wrong type."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_failure, run_redis


def _setup_string(db, key="k"):
    run_redis(["SET", key, "value"], data_path=db)

def _setup_list(db, key="k"):
    run_redis(["RPUSH", key, "item"], data_path=db)

def _setup_hash(db, key="k"):
    run_redis(["HSET", key, "field", "value"], data_path=db)

def _setup_set(db, key="k"):
    run_redis(["SADD", key, "member"], data_path=db)


def test_lpush_on_string_exits_1(db):
    _setup_string(db)
    r = run_redis(["LPUSH", "k", "item"], data_path=db)
    assert_failure(r)
    assert "WRONGTYPE" in r.stderr

def test_rpush_on_string_exits_1(db):
    _setup_string(db)
    r = run_redis(["RPUSH", "k", "item"], data_path=db)
    assert_failure(r)

def test_get_on_list_exits_1(db):
    _setup_list(db)
    r = run_redis(["GET", "k"], data_path=db)
    assert_failure(r)
    assert "WRONGTYPE" in r.stderr

def test_hset_on_list_exits_1(db):
    _setup_list(db)
    r = run_redis(["HSET", "k", "f", "v"], data_path=db)
    assert_failure(r)

def test_sadd_on_string_exits_1(db):
    _setup_string(db)
    r = run_redis(["SADD", "k", "member"], data_path=db)
    assert_failure(r)

def test_incr_on_list_exits_1(db):
    _setup_list(db)
    r = run_redis(["INCR", "k"], data_path=db)
    assert_failure(r)

def test_lrange_on_hash_exits_1(db):
    _setup_hash(db)
    r = run_redis(["LRANGE", "k", "0", "-1"], data_path=db)
    assert_failure(r)

def test_smembers_on_list_exits_1(db):
    _setup_list(db)
    r = run_redis(["SMEMBERS", "k"], data_path=db)
    assert_failure(r)

def test_hget_on_set_exits_1(db):
    _setup_set(db)
    r = run_redis(["HGET", "k", "field"], data_path=db)
    assert_failure(r)
