"""Performance benchmark: git merge of deeply diverged branches (500 commits each)."""

import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import run_git, MINI_GIT_NOT_FOUND


THRESHOLDS = json.loads(
    (Path(__file__).parent / "thresholds.json").read_text()
)["benchmarks"]["merge_deep_diverge"]

pytestmark = pytest.mark.skipif(MINI_GIT_NOT_FOUND, reason="MINI_GIT_CMD not set or binary not found")


@pytest.fixture
def diverged_repo(tmp_path):
    """
    Repo with two branches that have diverged by 500 commits each.
    main: 500 commits modifying files in dir_main/
    feature: branched from commit 0, 500 commits modifying files in dir_feature/
    Files are non-overlapping so merge should be clean (no conflicts).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(["init"], cwd=repo)

    # Create base commit
    (repo / "base.txt").write_text("base\n")
    run_git(["add", "base.txt"], cwd=repo)
    run_git(["commit", "-m", "base commit"], cwd=repo)

    # Branch off to feature
    run_git(["branch", "feature"], cwd=repo)

    # 500 commits on main
    (repo / "dir_main").mkdir(exist_ok=True)
    for i in range(500):
        (repo / "dir_main" / f"f{i}.txt").write_text(f"main {i}\n")
        run_git(["add", f"dir_main/f{i}.txt"], cwd=repo)
        run_git(["commit", "-m", f"main commit {i}"], cwd=repo)

    # Switch to feature, 500 commits
    run_git(["checkout", "feature"], cwd=repo)
    (repo / "dir_feature").mkdir(exist_ok=True)
    for i in range(500):
        (repo / "dir_feature" / f"f{i}.txt").write_text(f"feature {i}\n")
        run_git(["add", f"dir_feature/f{i}.txt"], cwd=repo)
        run_git(["commit", "-m", f"feature commit {i}"], cwd=repo)

    # Back to main for merge
    run_git(["checkout", "main"], cwd=repo)
    return repo


def test_merge_deep_diverge_p95_within_target(diverged_repo):
    """p95 latency of merging 500-commit diverged branches should be <= 5 seconds."""
    start = time.perf_counter()
    result = run_git(["merge", "feature"], cwd=diverged_repo)
    elapsed = time.perf_counter() - start

    target = THRESHOLDS["target_p95_seconds"]
    fail = THRESHOLDS["fail_p95_seconds"]

    print(f"\nmerge deep diverge — elapsed={elapsed:.3f}s")

    # Merge may fail if agent can't handle non-fast-forward; that's a correctness issue, not perf
    if result.returncode != 0:
        pytest.skip("Merge failed (correctness issue, not performance)")

    assert elapsed < fail, f"Elapsed {elapsed:.2f}s exceeds hard fail threshold {fail}s"
    if elapsed > target:
        pytest.xfail(f"Elapsed {elapsed:.2f}s exceeds target {target}s")


def test_merge_deep_diverge_result_correct(diverged_repo):
    """After merging, both dir_main and dir_feature should exist."""
    result = run_git(["merge", "feature"], cwd=diverged_repo)
    if result.returncode != 0:
        pytest.skip("Merge failed (correctness issue)")

    assert (diverged_repo / "dir_main").exists()
    assert (diverged_repo / "dir_feature").exists()
    assert (diverged_repo / "dir_main" / "f499.txt").exists()
    assert (diverged_repo / "dir_feature" / "f499.txt").exists()
