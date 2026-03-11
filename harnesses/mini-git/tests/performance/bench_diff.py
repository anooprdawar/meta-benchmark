"""Performance benchmark: git diff across 1,000 changed files."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import run_git, MINI_GIT_NOT_FOUND
from performance.conftest import time_command  # noqa: F401


THRESHOLDS = json.loads(
    (Path(__file__).parent / "thresholds.json").read_text()
)["benchmarks"]["diff_1k_changed_files"]

pytestmark = pytest.mark.skipif(MINI_GIT_NOT_FOUND, reason="MINI_GIT_CMD not set or binary not found")


@pytest.fixture
def repo_1k_changes(tmp_path):
    """Repo with 1,000 files all modified since last commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(["init"], cwd=repo)

    # Create and commit 1,000 files
    for i in range(1_000):
        (repo / f"file_{i:04d}.txt").write_text(f"original content {i}\n")
    run_git(["add", "."], cwd=repo)
    run_git(["commit", "-m", "initial commit"], cwd=repo)

    # Modify all 1,000 files
    for i in range(1_000):
        (repo / f"file_{i:04d}.txt").write_text(f"modified content {i}\n")

    return repo


def test_diff_1k_p95_within_target(repo_1k_changes):
    """p95 latency of git diff across 1k changed files should be <= 1 second."""
    stats = time_command(["diff"], cwd=repo_1k_changes, n=5)
    target = THRESHOLDS["target_p95_seconds"]
    fail = THRESHOLDS["fail_p95_seconds"]

    print(f"\ndiff 1k files — p50={stats['p50']:.3f}s p95={stats['p95']:.3f}s p99={stats['p99']:.3f}s")
    assert stats["p95"] < fail, (
        f"p95 latency {stats['p95']:.2f}s exceeds hard fail threshold {fail}s"
    )
    if stats["p95"] > target:
        pytest.xfail(f"p95 {stats['p95']:.2f}s exceeds target {target}s")


def test_diff_1k_output_coverage(repo_1k_changes):
    """git diff on 1k changed files must mention all 1k files."""
    result = run_git(["diff"], cwd=repo_1k_changes)
    assert result.returncode == 0
    # Each modified file should appear in the diff
    output = result.stdout
    missing = [f"file_{i:04d}.txt" for i in range(1_000) if f"file_{i:04d}.txt" not in output]
    assert not missing, f"{len(missing)} files missing from diff output"
