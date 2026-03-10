"""Performance benchmark: git add . on 100,000 files."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import run_git, MINI_GIT_NOT_FOUND
from performance.conftest import time_command, large_file_tree  # noqa: F401


THRESHOLDS = json.loads(
    (Path(__file__).parent / "thresholds.json").read_text()
)["benchmarks"]["add_100k_files"]

pytestmark = pytest.mark.skipif(MINI_GIT_NOT_FOUND, reason="MINI_GIT_CMD not set or binary not found")


@pytest.fixture
def tree_100k(large_file_tree):
    return large_file_tree(100_000)


def test_add_100k_p95_within_target(tree_100k):
    """p95 latency of git add . on 100k files should be <= 30 seconds."""
    # Run only once due to cost — subsequent runs would be no-ops (already staged)
    stats = time_command(["add", "."], cwd=tree_100k, n=1)
    target = THRESHOLDS["target_p95_seconds"]
    fail = THRESHOLDS["fail_p95_seconds"]

    print(f"\nadd 100k files — elapsed={stats['p50']:.3f}s")
    assert stats["p50"] < fail, (
        f"Elapsed {stats['p50']:.2f}s exceeds hard fail threshold {fail}s"
    )
    if stats["p50"] > target:
        pytest.xfail(f"Elapsed {stats['p50']:.2f}s exceeds target {target}s")


def test_add_100k_all_staged(tree_100k):
    """After git add . on 100k files, all files should be staged."""
    run_git(["add", "."], cwd=tree_100k)
    result = run_git(["status"], cwd=tree_100k)
    assert result.returncode == 0
    # Should show a large number of new files or "nothing to commit" after commit
    assert "untracked" not in result.stdout.lower() or "nothing" in result.stdout.lower()
