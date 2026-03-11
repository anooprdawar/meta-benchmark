"""Adversarial: unicode keys and values, special characters."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, assert_stdout, run_redis


def test_unicode_value(db):
    run_redis(["SET", "greeting", "こんにちは"], data_path=db)
    r = run_redis(["GET", "greeting"], data_path=db)
    assert_success(r)
    assert '"こんにちは"' in r.stdout


def test_emoji_value(db):
    run_redis(["SET", "k", "🎉"], data_path=db)
    r = run_redis(["GET", "k"], data_path=db)
    assert_success(r)
    assert '"🎉"' in r.stdout


def test_unicode_key(db):
    run_redis(["SET", "キー", "value"], data_path=db)
    r = run_redis(["GET", "キー"], data_path=db)
    assert_stdout(r, '"value"')


def test_backslash_in_value(db):
    run_redis(["SET", "k", "back\\slash"], data_path=db)
    r = run_redis(["GET", "k"], data_path=db)
    assert_success(r)
    # Output must have escaped backslash: "back\\slash" (the spec rule escapes \ as \\)
    assert r.stdout.strip() == '"back\\\\slash"'


def test_double_quote_in_value(db):
    run_redis(["SET", "k", 'say "hello"'], data_path=db)
    r = run_redis(["GET", "k"], data_path=db)
    assert_success(r)
    # Intentionally flexible: only checks the output is wrapped in quotes.
    # The spec does not mandate a specific escaping strategy for inner double-quotes.
    out = r.stdout.strip()
    assert out.startswith('"') and out.endswith('"')


def test_hash_with_unicode_fields(db):
    run_redis(["HSET", "h", "名前", "Alice", "年齢", "30"], data_path=db)
    r = run_redis(["HKEYS", "h"], data_path=db)
    assert_success(r)
    assert "名前" in r.stdout
    assert "年齢" in r.stdout


def test_set_member_unicode(db):
    run_redis(["SADD", "tags", "python", "Ω大", "αβγ"], data_path=db)
    r = run_redis(["SMEMBERS", "tags"], data_path=db)
    assert_success(r)
    assert "python" in r.stdout
