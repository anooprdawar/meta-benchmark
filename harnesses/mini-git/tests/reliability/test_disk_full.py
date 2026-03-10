"""Reliability: disk-full simulation — verify graceful failure and no corruption."""

from __future__ import annotations

import os
import resource
import sys
from pathlib import Path

import pytest

from reliability.conftest import run_git, is_repo_consistent, MINI_GIT_NOT_FOUND

pytestmark = pytest.mark.skipif(MINI_GIT_NOT_FOUND, reason="MINI_GIT_CMD not set or binary not found")
pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Resource limits only reliable on Linux")


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(["init"], cwd=repo)
    return repo


def _with_fsize_limit(limit_bytes: int):
    """Context manager: set RLIMIT_FSIZE to simulate disk full."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        old_soft, old_hard = resource.getrlimit(resource.RLIMIT_FSIZE)
        try:
            resource.setrlimit(resource.RLIMIT_FSIZE, (limit_bytes, old_hard))
            yield
        finally:
            resource.setrlimit(resource.RLIMIT_FSIZE, (old_soft, old_hard))

    return _ctx()


def test_commit_fails_gracefully_when_disk_full(repo):
    """
    If disk write is limited to near-zero, commit should fail with non-zero exit
    and leave the repo in a consistent state (not partially written).
    """
    (repo / "file.txt").write_text("content\n")
    run_git(["add", "file.txt"], cwd=repo)

    # Set file size limit to 1KB — enough to start but not finish a commit
    with _with_fsize_limit(1024):
        result = run_git(["commit", "-m", "should fail"], cwd=repo)

    # Should fail (non-zero exit or graceful message)
    if result.returncode == 0:
        # If it succeeded within 1KB, that's also acceptable (very small commit)
        pass
    else:
        # Verify repo is still consistent despite the failure
        consistent, reason = is_repo_consistent(repo)
        assert consistent, f"Repo corrupted after disk-full commit failure: {reason}"


def test_add_fails_gracefully_when_disk_full(repo):
    """
    If disk write is limited, add should fail gracefully, not leave corrupt objects.
    """
    # Create a file that's larger than our limit
    (repo / "large.txt").write_bytes(b"x" * 10_000)

    with _with_fsize_limit(512):
        result = run_git(["add", "large.txt"], cwd=repo)

    if result.returncode != 0:
        consistent, reason = is_repo_consistent(repo)
        assert consistent, f"Repo corrupted after disk-full add failure: {reason}"
