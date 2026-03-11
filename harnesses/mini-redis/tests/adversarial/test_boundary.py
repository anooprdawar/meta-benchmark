"""Adversarial: boundary conditions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, assert_stdout, run_redis


def test_incr_to_large_number(db):
    run_redis(["SET", "k", "9999999999"], data_path=db)
    r = run_redis(["INCR", "k"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(integer) 10000000000")


def test_decr_below_zero(db):
    run_redis(["SET", "k", "0"], data_path=db)
    r = run_redis(["DECR", "k"], data_path=db)
    assert_stdout(r, "(integer) -1")


def test_lrange_single_element_list(db):
    run_redis(["RPUSH", "mylist", "only"], data_path=db)
    r = run_redis(["LRANGE", "mylist", "0", "0"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "only"']


def test_sadd_many_members(db):
    members = [str(i) for i in range(50)]
    run_redis(["SADD", "s"] + members, data_path=db)
    r = run_redis(["SMEMBERS", "s"], data_path=db)
    assert_success(r)
    lines = r.stdout.strip().splitlines()
    assert len(lines) == 50


def test_hset_many_fields(db):
    args = []
    for i in range(50):
        args += [f"field{i:03d}", f"value{i}"]
    run_redis(["HSET", "h"] + args, data_path=db)
    r = run_redis(["HKEYS", "h"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert len(lines) == 50


def test_mget_many_keys(db):
    keys = [f"k{i}" for i in range(20)]
    for k in keys:
        run_redis(["SET", k, k + "_val"], data_path=db)
    r = run_redis(["MGET"] + keys, data_path=db)
    lines = r.stdout.strip().splitlines()
    assert len(lines) == 20


def test_del_all_keys_leaves_empty_store(db):
    run_redis(["SET", "a", "1"], data_path=db)
    run_redis(["SET", "b", "2"], data_path=db)
    run_redis(["DEL", "a", "b"], data_path=db)
    r = run_redis(["EXISTS", "a"], data_path=db)
    assert_stdout(r, "(integer) 0")
    r2 = run_redis(["EXISTS", "b"], data_path=db)
    assert_stdout(r2, "(integer) 0")


def test_lpop_until_empty(db):
    run_redis(["RPUSH", "mylist", "a", "b"], data_path=db)
    run_redis(["LPOP", "mylist"], data_path=db)
    run_redis(["LPOP", "mylist"], data_path=db)
    r = run_redis(["LRANGE", "mylist", "0", "-1"], data_path=db)
    assert_stdout(r, "(empty list)")


def test_persist_on_key_without_ttl_returns_0(db):
    run_redis(["SET", "k", "v"], data_path=db)
    r = run_redis(["PERSIST", "k"], data_path=db)
    assert_stdout(r, "(integer) 0")
