"""Reliability: kill process mid-commit, verify repo remains consistent."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

from reliability.conftest import (
    run_git,
    make_commit,
    run_git_async,
    is_repo_consistent,
    MINI_GIT_CMD,
    MINI_GIT_NOT_FOUND,
)

pytestmark = pytest.mark.skipif(MINI_GIT_NOT_FOUND, reason="MINI_GIT_CMD not set or binary not found")


@pytest.fixture
def repo_with_staged_files(tmp_path):
    """Repo with files staged and ready to commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(["init"], cwd=repo)

    # Stage a large number of files to make the commit slow enough to interrupt
    for i in range(200):
        (repo / f"file_{i}.txt").write_text("x" * 4096 + f"\n{i}\n")
    run_git(["add", "."], cwd=repo)
    return repo


def test_sigterm_mid_commit_leaves_repo_consistent(repo_with_staged_files):
    """
    Send SIGTERM to mini-git mid-commit.
    The repo must remain in a consistent state afterward.
    A consistent state means:
    - .git/ exists
    - HEAD is valid
    - No zero-length object files
    The commit may or may not have succeeded — that's acceptable.
    """
    repo = repo_with_staged_files

    proc = run_git_async(["commit", "-m", "test commit"], cwd=repo)

    # Give it a moment to start writing, then interrupt
    time.sleep(0.05)
    try:
        proc.send_signal(signal.SIGTERM)
    except ProcessLookupError:
        pass  # Already finished — that's fine
    proc.wait(timeout=5)

    consistent, reason = is_repo_consistent(repo)
    assert consistent, f"Repo inconsistent after SIGTERM: {reason}"


def test_sigkill_mid_commit_leaves_repo_consistent(repo_with_staged_files):
    """
    Send SIGKILL (unblockable) to mini-git mid-commit.
    The repo must remain in a consistent state afterward.
    This is a stricter test — SIGKILL gives no cleanup opportunity.
    """
    repo = repo_with_staged_files

    proc = run_git_async(["commit", "-m", "test commit"], cwd=repo)

    time.sleep(0.05)
    try:
        proc.send_signal(signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait(timeout=5)

    consistent, reason = is_repo_consistent(repo)
    assert consistent, f"Repo inconsistent after SIGKILL: {reason}"


def test_subsequent_commit_works_after_interruption(repo_with_staged_files):
    """
    After an interrupted commit, the repo should still accept new commits.
    """
    repo = repo_with_staged_files

    # Interrupt first commit
    proc = run_git_async(["commit", "-m", "first attempt"], cwd=repo)
    time.sleep(0.05)
    try:
        proc.send_signal(signal.SIGTERM)
    except ProcessLookupError:
        pass
    proc.wait(timeout=5)

    # Try another commit (re-stage if needed)
    run_git(["add", "."], cwd=repo)
    result = run_git(["commit", "-m", "recovery commit"], cwd=repo)
    # This may fail if the first commit succeeded — check for meaningful error
    if result.returncode != 0:
        # Acceptable: "nothing to commit" because first commit succeeded before kill
        assert "nothing to commit" in result.stdout.lower() or "nothing to commit" in result.stderr.lower(), (
            f"Unexpected commit failure after interruption: {result.stderr}"
        )
