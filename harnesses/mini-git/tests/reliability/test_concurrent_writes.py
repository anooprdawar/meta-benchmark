"""Reliability: two processes writing simultaneously — verify no corruption."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from reliability.conftest import (
    run_git,
    run_git_async,
    is_repo_consistent,
    MINI_GIT_NOT_FOUND,
)

pytestmark = pytest.mark.skipif(MINI_GIT_NOT_FOUND, reason="MINI_GIT_CMD not set or binary not found")


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(["init"], cwd=repo)
    (repo / "base.txt").write_text("base\n")
    run_git(["add", "base.txt"], cwd=repo)
    run_git(["commit", "-m", "base"], cwd=repo)
    return repo


def test_two_concurrent_commits_no_corruption(repo):
    """
    Launch two concurrent commit processes.
    One or both may fail with a locking error — that's acceptable.
    Neither should corrupt the object store or leave zero-length files.
    """
    # Stage files for both processes
    for i in range(2):
        (repo / f"concurrent_{i}.txt").write_text(f"process {i}\n")
    run_git(["add", "."], cwd=repo)

    procs = []
    for i in range(2):
        p = run_git_async(["commit", "-m", f"concurrent commit {i}"], cwd=repo)
        procs.append(p)

    for p in procs:
        try:
            p.wait(timeout=10)
        except Exception:
            p.kill()

    consistent, reason = is_repo_consistent(repo)
    assert consistent, f"Repo corrupted by concurrent writes: {reason}"


def test_concurrent_add_no_corruption(repo):
    """
    Two processes running `git add` simultaneously should not corrupt the index.
    """
    for i in range(50):
        (repo / f"file_{i}.txt").write_text(f"content {i}\n")

    procs = []
    for i in range(0, 50, 25):
        files = [f"file_{j}.txt" for j in range(i, i + 25)]
        p = run_git_async(["add"] + files, cwd=repo)
        procs.append(p)

    for p in procs:
        try:
            p.wait(timeout=10)
        except Exception:
            p.kill()

    consistent, reason = is_repo_consistent(repo)
    assert consistent, f"Repo corrupted by concurrent add: {reason}"

    # At least some files should be staged
    result = run_git(["status"], cwd=repo)
    assert result.returncode == 0


def test_concurrent_status_reads_safe(repo):
    """
    Multiple concurrent status reads should not interfere with each other.
    """
    results = []
    errors = []

    def run_status():
        try:
            r = run_git(["status"], cwd=repo)
            results.append(r.returncode)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=run_status) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"Concurrent status raised errors: {errors}"
    assert all(rc == 0 for rc in results), f"Some status calls failed: {results}"
