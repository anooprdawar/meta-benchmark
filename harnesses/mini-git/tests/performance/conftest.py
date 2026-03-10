"""Performance test helpers — statistical timing utilities."""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import run_git  # noqa: F401


def time_command(cmd: list[str], cwd: Path, n: int = 5) -> dict:
    """
    Run a command N times and return timing statistics.

    Returns:
        dict with keys: min, max, mean, median (p50), p95, p99, samples
    """
    times = []
    for _ in range(n):
        start = time.perf_counter()
        run_git(cmd, cwd=cwd)
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    times.sort()
    n_samples = len(times)

    def percentile(p: float) -> float:
        idx = (p / 100) * (n_samples - 1)
        lo, hi = int(idx), min(int(idx) + 1, n_samples - 1)
        return times[lo] + (idx - lo) * (times[hi] - times[lo])

    return {
        "min": times[0],
        "max": times[-1],
        "mean": statistics.mean(times),
        "p50": percentile(50),
        "p95": percentile(95),
        "p99": percentile(99),
        "samples": times,
        "n": n_samples,
    }


@pytest.fixture
def repo_with_commits(tmp_path):
    """
    Factory fixture: returns a function that creates a repo with N commits.
    Usage: repo = repo_with_commits(10_000)
    """
    def _make(n: int, files_per_commit: int = 1) -> Path:
        repo = tmp_path / f"repo_{n}"
        repo.mkdir()
        run_git(["init"], cwd=repo)

        for i in range(n):
            (repo / f"file_{i % 100}.txt").write_text(f"content {i}\n")
            run_git(["add", f"file_{i % 100}.txt"], cwd=repo)
            run_git(["commit", "-m", f"commit {i}"], cwd=repo)

        return repo

    return _make


@pytest.fixture
def large_file_tree(tmp_path):
    """
    Factory: creates a directory with N small files.
    Usage: tree = large_file_tree(100_000)
    """
    def _make(n: int, file_size_bytes: int = 64) -> Path:
        tree = tmp_path / f"tree_{n}"
        tree.mkdir()
        run_git(["init"], cwd=tree)

        # Create files in batches of 1000 per subdirectory to avoid FS limits
        batch = 1000
        for batch_i in range(0, n, batch):
            subdir = tree / f"dir_{batch_i // batch:04d}"
            subdir.mkdir(exist_ok=True)
            for j in range(batch_i, min(batch_i + batch, n)):
                (subdir / f"f{j}.txt").write_bytes(b"x" * file_size_bytes)

        return tree

    return _make
