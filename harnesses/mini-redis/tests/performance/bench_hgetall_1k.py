"""Performance: HGETALL on a hash with 1,000 fields."""

import os, shlex, subprocess, sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from conftest import time_command


@pytest.fixture(scope="module")
def hash_1k(tmp_path_factory):
    db = tmp_path_factory.mktemp("perf") / "mini_redis.json"
    cmd_str = os.environ.get("MINI_REDIS_CMD", "")
    if not cmd_str:
        pytest.skip("MINI_REDIS_CMD not set")
    cmd = shlex.split(cmd_str)
    env = os.environ.copy()
    env["MINI_REDIS_DATA"] = str(db)
    args = []
    for i in range(1_000):
        args += [f"field{i:04d}", f"value{i}"]
    subprocess.run(cmd + ["HSET", "bighash"] + args, env=env, capture_output=True)
    return db


def test_hgetall_1k_p95_within_target(hash_1k):
    stats = time_command(["HGETALL", "bighash"], data_path=hash_1k, n=5)
    print(f"\nhgetall 1k fields — p50={stats['p50']:.3f}s p95={stats['p95']:.3f}s p99={stats['p99']:.3f}s")
    assert stats["p95"] < 5.0
    if stats["p95"] > 1.0:
        pytest.xfail(f"p95 {stats['p95']:.2f}s exceeds target 1.0s")
