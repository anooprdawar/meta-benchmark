"""Extension: ZADD, ZRANGE, ZRANK, ZSCORE, ZREM — 16 tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_failure, assert_success, assert_stdout, run_redis


def test_zadd_new_member_returns_1(db):
    r = run_redis(["ZADD", "z", "1.0", "a"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(integer) 1")


def test_zadd_multiple_members(db):
    r = run_redis(["ZADD", "z", "1", "a", "2", "b", "3", "c"], data_path=db)
    assert_stdout(r, "(integer) 3")


def test_zadd_update_existing_returns_0(db):
    run_redis(["ZADD", "z", "1", "a"], data_path=db)
    r = run_redis(["ZADD", "z", "5", "a"], data_path=db)
    assert_stdout(r, "(integer) 0")


def test_zrange_ascending_by_score(db):
    run_redis(["ZADD", "z", "3", "c", "1", "a", "2", "b"], data_path=db)
    r = run_redis(["ZRANGE", "z", "0", "-1"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "a"', '2) "b"', '3) "c"']


def test_zrange_partial(db):
    run_redis(["ZADD", "z", "1", "a", "2", "b", "3", "c", "4", "d"], data_path=db)
    r = run_redis(["ZRANGE", "z", "1", "2"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "b"', '2) "c"']


def test_zrange_empty(db):
    r = run_redis(["ZRANGE", "nosuchkey", "0", "-1"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(empty list)")


def test_zrange_tie_broken_lexicographically(db):
    run_redis(["ZADD", "z", "1", "banana", "1", "apple", "1", "cherry"], data_path=db)
    r = run_redis(["ZRANGE", "z", "0", "-1"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "apple"', '2) "banana"', '3) "cherry"']


def test_zrank_found(db):
    run_redis(["ZADD", "z", "1", "a", "2", "b", "3", "c"], data_path=db)
    r = run_redis(["ZRANK", "z", "b"], data_path=db)
    assert_stdout(r, "(integer) 1")


def test_zrank_not_found(db):
    run_redis(["ZADD", "z", "1", "a"], data_path=db)
    r = run_redis(["ZRANK", "z", "nosuchmember"], data_path=db)
    assert_stdout(r, "(nil)")


def test_zscore_found_integer(db):
    run_redis(["ZADD", "z", "5", "a"], data_path=db)
    r = run_redis(["ZSCORE", "z", "a"], data_path=db)
    assert_success(r)
    out = r.stdout.strip()
    assert out == '"5"', f"Got {out!r}  (spec requires f\"{{score:g}}\" format, so 5.0 → '5')"


def test_zscore_found_float(db):
    run_redis(["ZADD", "z", "1.5", "a"], data_path=db)
    r = run_redis(["ZSCORE", "z", "a"], data_path=db)
    assert_stdout(r, '"1.5"')


def test_zscore_not_found(db):
    run_redis(["ZADD", "z", "1", "a"], data_path=db)
    r = run_redis(["ZSCORE", "z", "nosuchmember"], data_path=db)
    assert_stdout(r, "(nil)")


def test_zrem_removes_member(db):
    run_redis(["ZADD", "z", "1", "a", "2", "b"], data_path=db)
    r = run_redis(["ZREM", "z", "a"], data_path=db)
    assert_stdout(r, "(integer) 1")
    r2 = run_redis(["ZRANGE", "z", "0", "-1"], data_path=db)
    lines = r2.stdout.strip().splitlines()
    assert lines == ['1) "b"']


def test_zrem_missing_member_returns_0(db):
    run_redis(["ZADD", "z", "1", "a"], data_path=db)
    r = run_redis(["ZREM", "z", "nosuchmember"], data_path=db)
    assert_stdout(r, "(integer) 0")


def test_zrange_negative_indices(db):
    run_redis(["ZADD", "z", "1", "a", "2", "b", "3", "c"], data_path=db)
    r = run_redis(["ZRANGE", "z", "-2", "-1"], data_path=db)
    lines = r.stdout.strip().splitlines()
    assert lines == ['1) "b"', '2) "c"']


def test_zadd_wrong_type_exits_1(db):
    run_redis(["SET", "k", "string"], data_path=db)
    r = run_redis(["ZADD", "k", "1", "member"], data_path=db)
    assert_failure(r)
    assert "WRONGTYPE" in r.stderr
