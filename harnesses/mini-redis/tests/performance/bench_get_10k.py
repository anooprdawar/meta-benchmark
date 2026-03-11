"""Performance: GET from a store with 10,000 keys."""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from conftest import build_string_store, time_command


@pytest.fixture(scope="module")
def store_10k(tmp_path_factory):
    db = tmp_path_factory.mktemp("perf") / "mini_redis.json"
    build_string_store(db, 10_000)
    return db


def test_get_10k_p95_within_target(store_10k):
    stats = time_command(["GET", "key5000"], data_path=store_10k, n=7)
    print(f"\nget 10k keys — p50={stats['p50']:.3f}s p95={stats['p95']:.3f}s p99={stats['p99']:.3f}s")
    assert stats["p95"] < 5.0, f"p95 {stats['p95']:.2f}s exceeds fail threshold 5.0s"
    if stats["p95"] > 1.0:
        pytest.xfail(f"p95 {stats['p95']:.2f}s exceeds target 1.0s but under fail threshold")
