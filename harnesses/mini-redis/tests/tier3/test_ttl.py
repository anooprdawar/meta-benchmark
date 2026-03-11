"""Tier 3: EXPIRE, TTL, PERSIST."""

import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, assert_stdout, run_redis


def test_expire_existing_key_returns_1(db):
    run_redis(["SET", "k", "v"], data_path=db)
    r = run_redis(["EXPIRE", "k", "60"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(integer) 1")


def test_expire_missing_key_returns_0(db):
    r = run_redis(["EXPIRE", "nosuchkey", "60"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(integer) 0")


def test_ttl_returns_remaining_seconds(db):
    run_redis(["SET", "k", "v"], data_path=db)
    run_redis(["EXPIRE", "k", "100"], data_path=db)
    r = run_redis(["TTL", "k"], data_path=db)
    assert_success(r)
    out = r.stdout.strip()
    assert out.startswith("(integer) ")
    secs = int(out.split()[-1])
    assert 95 <= secs <= 100, f"Expected ~100 seconds remaining, got {secs}"


def test_ttl_no_expiry_returns_minus_1(db):
    run_redis(["SET", "k", "v"], data_path=db)
    r = run_redis(["TTL", "k"], data_path=db)
    assert_stdout(r, "(integer) -1")


def test_ttl_missing_key_returns_minus_2(db):
    r = run_redis(["TTL", "nosuchkey"], data_path=db)
    assert_stdout(r, "(integer) -2")


def test_persist_removes_ttl(db):
    run_redis(["SET", "k", "v"], data_path=db)
    run_redis(["EXPIRE", "k", "60"], data_path=db)
    r = run_redis(["PERSIST", "k"], data_path=db)
    assert_stdout(r, "(integer) 1")
    r2 = run_redis(["TTL", "k"], data_path=db)
    assert_stdout(r2, "(integer) -1")


def test_persist_no_ttl_returns_0(db):
    run_redis(["SET", "k", "v"], data_path=db)
    r = run_redis(["PERSIST", "k"], data_path=db)
    assert_stdout(r, "(integer) 0")


def test_expire_zero_seconds_exits_1(db):
    run_redis(["SET", "k", "v"], data_path=db)
    r = run_redis(["EXPIRE", "k", "0"], data_path=db)
    assert r.returncode == 1
    assert r.stdout.strip() == ""


def test_expire_negative_seconds_exits_1(db):
    run_redis(["SET", "k", "v"], data_path=db)
    r = run_redis(["EXPIRE", "k", "-5"], data_path=db)
    assert r.returncode == 1


def test_expired_key_returns_nil_on_get(db):
    """Key expired in a previous invocation returns (nil) in next invocation."""
    import time
    run_redis(["SET", "k", "v"], data_path=db)
    run_redis(["EXPIRE", "k", "1"], data_path=db)
    time.sleep(1.1)
    r = run_redis(["GET", "k"], data_path=db)
    assert_stdout(r, "(nil)")
