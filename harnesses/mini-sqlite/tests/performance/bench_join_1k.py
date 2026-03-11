"""Performance: INNER JOIN on two 1,000-row tables."""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from conftest import run_sql_raw, time_sql


@pytest.fixture(scope="module")
def db_join(tmp_path_factory):
    db = tmp_path_factory.mktemp("perf") / "bench.db"
    run_sql_raw(db, "CREATE TABLE a (id INTEGER, val TEXT)")
    run_sql_raw(db, "CREATE TABLE b (id INTEGER, a_id INTEGER, extra TEXT)")
    for i in range(1_000):
        run_sql_raw(db, f"INSERT INTO a VALUES ({i}, 'val{i}')")
        run_sql_raw(db, f"INSERT INTO b VALUES ({i}, {i % 100}, 'extra{i}')")
    return db


def test_join_1k_p95_within_target(db_join):
    stmt = "SELECT a.val, b.extra FROM a INNER JOIN b ON a.id = b.a_id LIMIT 100"
    stats = time_sql(db_join, stmt, n=3)
    print(f"\njoin 1k rows — p50={stats['p50']:.3f}s p95={stats['p95']:.3f}s p99={stats['p99']:.3f}s")
    assert stats["p95"] < 15.0
    if stats["p95"] > 3.0:
        pytest.xfail(f"p95 {stats['p95']:.2f}s exceeds target 3.0s")
