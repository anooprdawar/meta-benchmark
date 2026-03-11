"""Performance test helpers for mini-sqlite."""

import os
import shlex
import subprocess
import time
from pathlib import Path
import pytest


def run_sql_raw(db_path: Path, statement: str) -> subprocess.CompletedProcess:
    cmd_str = os.environ.get("MINI_SQLITE_CMD", "")
    if not cmd_str:
        pytest.skip("MINI_SQLITE_CMD not set")
    cmd = shlex.split(cmd_str)
    return subprocess.run(cmd + [str(db_path), statement], capture_output=True, text=True)


def time_sql(db_path: Path, statement: str, n: int = 5) -> dict:
    samples = []
    for _ in range(n):
        start = time.perf_counter()
        run_sql_raw(db_path, statement)
        samples.append(time.perf_counter() - start)
    samples.sort()
    def p(pct): return samples[min(int(len(samples) * pct / 100), len(samples) - 1)]
    return {"p50": p(50), "p95": p(95), "p99": p(99)}
