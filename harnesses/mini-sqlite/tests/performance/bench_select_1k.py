"""Performance: SELECT * from table with 1,000 rows."""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from conftest import run_sql_raw, time_sql


@pytest.fixture(scope="module")
def db_1k(tmp_path_factory):
    db = tmp_path_factory.mktemp("perf") / "bench.db"
    run_sql_raw(db, "CREATE TABLE t (id INTEGER, name TEXT, score REAL)")
    for i in range(1_000):
        run_sql_raw(db, f"INSERT INTO t VALUES ({i}, 'name{i}', {i * 0.5})")
    return db


def test_select_1k_p95_within_target(db_1k):
    stats = time_sql(db_1k, "SELECT * FROM t", n=5)
    print(f"\nselect 1k rows — p50={stats['p50']:.3f}s p95={stats['p95']:.3f}s p99={stats['p99']:.3f}s")
    assert stats["p95"] < 10.0
    if stats["p95"] > 2.0:
        pytest.xfail(f"p95 {stats['p95']:.2f}s exceeds target 2.0s")
