"""Performance test helpers: build pre-populated data files directly."""

import json
import time
import statistics
import os
import subprocess
import shlex
from pathlib import Path
from typing import List
import pytest


def build_string_store(path: Path, n: int) -> None:
    """Write a JSON data file with n string keys directly (fast, no subprocess)."""
    # Agent's JSON schema is unknown, so we call SET via subprocess for one key
    # then read the schema to understand the format, then write directly.
    # Simpler: write n keys via batched MSET subprocess calls.
    import shlex, os
    cmd_str = os.environ.get("MINI_REDIS_CMD", "")
    if not cmd_str:
        pytest.skip("MINI_REDIS_CMD not set")
    cmd = shlex.split(cmd_str)
    env = os.environ.copy()
    env["MINI_REDIS_DATA"] = str(path)
    # MSET all keys at once
    args = []
    for i in range(n):
        args += [f"key{i}", f"value{i}"]
    subprocess.run(cmd + ["MSET"] + args, env=env, capture_output=True)


def time_command(cmd_args: list, data_path: Path, n: int = 7) -> dict:
    """Run a redis command n times and return p50/p95/p99 stats."""
    import shlex, os
    cmd_str = os.environ.get("MINI_REDIS_CMD", "")
    if not cmd_str:
        pytest.skip("MINI_REDIS_CMD not set")
    cmd = shlex.split(cmd_str)
    env = os.environ.copy()
    env["MINI_REDIS_DATA"] = str(data_path)

    samples = []
    for _ in range(n):
        start = time.perf_counter()
        subprocess.run(cmd + cmd_args, env=env, capture_output=True)
        samples.append(time.perf_counter() - start)

    samples.sort()
    def percentile(data, p):
        idx = int(len(data) * p / 100)
        return data[min(idx, len(data) - 1)]

    return {
        "p50": percentile(samples, 50),
        "p95": percentile(samples, 95),
        "p99": percentile(samples, 99),
    }
