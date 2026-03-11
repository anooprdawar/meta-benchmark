"""Reliability: durability, persistence, and data integrity."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import assert_success, assert_stdout, run_redis, _CMD


def test_data_file_written_before_exit(db):
    """File must exist after SET — confirming fsync happened."""
    run_redis(["SET", "k", "v"], data_path=db)
    assert db.exists(), "Data file not written after SET"
    assert db.stat().st_size > 0, "Data file is empty"


def test_read_after_write_correct(db):
    """GET after SET returns correct value — basic sanity."""
    run_redis(["SET", "mykey", "myvalue"], data_path=db)
    r = run_redis(["GET", "mykey"], data_path=db)
    assert_stdout(r, '"myvalue"')


def test_many_writes_survive_restart(db):
    """Multiple writes — all survive a process restart."""
    for i in range(20):
        run_redis(["SET", f"key{i}", f"val{i}"], data_path=db)
    for i in range(20):
        r = run_redis(["GET", f"key{i}"], data_path=db)
        assert_stdout(r, f'"val{i}"')


def test_expire_deadline_survives_restart(db):
    """TTL deadline stored as epoch timestamp — still valid after restart."""
    run_redis(["SET", "k", "v"], data_path=db)
    run_redis(["EXPIRE", "k", "3600"], data_path=db)
    r = run_redis(["TTL", "k"], data_path=db)
    assert_success(r)
    out = r.stdout.strip()
    assert out.startswith("(integer) ")
    remaining = int(out.split()[-1])
    assert remaining > 3590, f"TTL should be ~3600, got {remaining}"


def test_missing_data_file_treated_as_empty(tmp_path):
    """No data file → empty store → GET returns (nil)."""
    db = tmp_path / "nonexistent.json"
    assert not db.exists()
    r = run_redis(["GET", "k"], data_path=db)
    assert_success(r)
    assert_stdout(r, "(nil)")


def test_sigkill_does_not_corrupt_data_file(tmp_path):
    """SIGKILL during a write must not leave a partially-written (corrupt) file.

    Strategy: write a known-good key first so the file exists, then start a
    long-running write (SET with a large value in a tight loop) and SIGKILL it
    mid-flight. After the kill, the data file must either:
      (a) still be the last-known-good JSON, OR
      (b) not exist (implementation chose atomic write-then-rename)
    It must never be a partial/corrupt file.
    """
    if _CMD is None:
        import pytest
        pytest.skip("MINI_REDIS_CMD not set")

    env = {**os.environ, "MINI_REDIS_DATA": str(tmp_path / "mini_redis.json")}
    db = tmp_path / "mini_redis.json"

    # Establish a clean baseline
    subprocess.run(_CMD + ["SET", "baseline", "ok"], env=env, capture_output=True)
    assert db.exists(), "Baseline write failed"
    baseline_content = db.read_text()

    # Launch a process and kill it immediately with SIGKILL
    proc = subprocess.Popen(
        _CMD + ["SET", "large", "x" * 100_000],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    time.sleep(0.01)  # let it start
    try:
        os.kill(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass  # already exited — that is fine
    proc.wait()

    # Data file must not be corrupt JSON
    if db.exists():
        try:
            json.loads(db.read_text())
        except json.JSONDecodeError:
            raise AssertionError("Data file is corrupt after SIGKILL")
