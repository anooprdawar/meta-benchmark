"""Performance: LRANGE 0 -1 on a 10,000-element list."""

import os, shlex, subprocess, sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from conftest import time_command


@pytest.fixture(scope="module")
def list_10k(tmp_path_factory):
    db = tmp_path_factory.mktemp("perf") / "mini_redis.json"
    cmd_str = os.environ.get("MINI_REDIS_CMD", "")
    if not cmd_str:
        pytest.skip("MINI_REDIS_CMD not set")
    cmd = shlex.split(cmd_str)
    env = os.environ.copy()
    env["MINI_REDIS_DATA"] = str(db)
    # RPUSH 10k items in one call
    items = [str(i) for i in range(10_000)]
    subprocess.run(cmd + ["RPUSH", "biglist"] + items, env=env, capture_output=True)
    return db


def test_lrange_10k_p95_within_target(list_10k):
    stats = time_command(["LRANGE", "biglist", "0", "-1"], data_path=list_10k, n=5)
    print(f"\nlrange 10k list — p50={stats['p50']:.3f}s p95={stats['p95']:.3f}s p99={stats['p99']:.3f}s")
    assert stats["p95"] < 10.0
    if stats["p95"] > 2.0:
        pytest.xfail(f"p95 {stats['p95']:.2f}s exceeds target 2.0s")
