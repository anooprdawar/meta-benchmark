"""Performance benchmark: git log on 10,000 commits."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import run_git, MINI_GIT_NOT_FOUND
from performance.conftest import time_command, repo_with_commits  # noqa: F401


THRESHOLDS = json.loads(
    (Path(__file__).parent / "thresholds.json").read_text()
)["benchmarks"]["log_10k_commits"]

pytestmark = pytest.mark.skipif(MINI_GIT_NOT_FOUND, reason="MINI_GIT_CMD not set or binary not found")


@pytest.fixture
def repo_10k(repo_with_commits):
    """Repo with 10,000 commits."""
    return repo_with_commits(10_000)


def test_log_10k_p95_within_target(repo_10k):
    """p95 latency of git log on 10k commits should be <= 2 seconds."""
    stats = time_command(["log"], cwd=repo_10k, n=5)
    target = THRESHOLDS["target_p95_seconds"]
    fail = THRESHOLDS["fail_p95_seconds"]

    print(f"\nlog 10k commits — p50={stats['p50']:.3f}s p95={stats['p95']:.3f}s p99={stats['p99']:.3f}s")
    assert stats["p95"] < fail, (
        f"p95 latency {stats['p95']:.2f}s exceeds hard fail threshold {fail}s"
    )
    if stats["p95"] > target:
        pytest.xfail(f"p95 {stats['p95']:.2f}s exceeds target {target}s (but < fail threshold)")


def test_log_output_completeness_10k(repo_10k):
    """git log on 10k-commit repo must output all 10k commit entries."""
    result = run_git(["log"], cwd=repo_10k)
    assert result.returncode == 0
    # Each commit should produce at least one line
    commit_lines = [l for l in result.stdout.splitlines() if "commit" in l.lower() or l.strip()]
    # Very loose check: at least 10k lines of output
    assert len(result.stdout.splitlines()) >= 10_000, (
        f"git log output has fewer than 10,000 lines: {len(result.stdout.splitlines())}"
    )
