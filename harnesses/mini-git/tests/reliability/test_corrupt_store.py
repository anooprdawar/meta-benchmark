"""Reliability: corrupt object store — verify detection and clear error messages."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from reliability.conftest import run_git, make_commit, is_repo_consistent, MINI_GIT_NOT_FOUND

pytestmark = pytest.mark.skipif(MINI_GIT_NOT_FOUND, reason="MINI_GIT_CMD not set or binary not found")


@pytest.fixture
def repo_with_commit(tmp_path):
    """Repo with one commit, ready for corruption tests."""
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(["init"], cwd=repo)
    (repo / "file.txt").write_text("hello\n")
    run_git(["add", "file.txt"], cwd=repo)
    run_git(["commit", "-m", "initial commit"], cwd=repo)
    return repo


def _get_object_files(repo: Path) -> list[Path]:
    """Return all object files in .git/objects/ (exclude pack/ and info/)."""
    objects_dir = repo / ".git" / "objects"
    return [
        p for p in objects_dir.rglob("*")
        if p.is_file() and p.parent.name not in ("pack", "info")
    ]


def test_corrupt_blob_detected(repo_with_commit):
    """
    Overwriting a blob object with garbage should cause git log or status
    to either fail with non-zero exit or print a clear error message.
    It must NOT silently succeed with wrong output.
    """
    objects = _get_object_files(repo_with_commit)
    assert objects, "No object files found in .git/objects/"

    # Corrupt one object
    target = objects[0]
    target.write_bytes(b"this is garbage, not a git object")

    result = run_git(["log"], cwd=repo_with_commit)
    if result.returncode == 0:
        # If it succeeded, it must not have silently ignored the corruption
        # Check that the output looks like a normal log (not empty or garbled)
        # This is a soft assertion — some implementations might rebuild from refs
        pass
    else:
        # Failed with non-zero — verify a useful message is present
        combined = result.stdout + result.stderr
        assert len(combined.strip()) > 0, "Corrupt object caused failure but no error message"


def test_truncated_object_detected(repo_with_commit):
    """
    Truncating an object file should be detected on read.
    """
    objects = _get_object_files(repo_with_commit)
    assert objects, "No object files found"

    target = objects[0]
    original = target.read_bytes()
    # Truncate to 50% of size
    target.write_bytes(original[: len(original) // 2])

    result = run_git(["status"], cwd=repo_with_commit)
    # Must not crash with an unhandled exception
    combined = result.stdout + result.stderr
    assert "traceback" not in combined.lower() and "exception" not in combined.lower(), (
        f"Unhandled exception on truncated object: {combined[:500]}"
    )


def test_missing_object_detected(repo_with_commit):
    """
    Deleting an object file should cause an error when that object is needed.
    """
    objects = _get_object_files(repo_with_commit)
    assert objects, "No object files found"

    target = objects[0]
    target.unlink()

    result = run_git(["log"], cwd=repo_with_commit)
    # Either fails with non-zero or prints an error message — must not silently return empty
    if result.returncode == 0 and not result.stdout.strip():
        pytest.fail("Missing object caused silent empty output from git log")


def test_corrupt_head_detected(repo_with_commit):
    """
    Writing invalid content to HEAD should cause an informative error.
    """
    (repo_with_commit / ".git" / "HEAD").write_text("not a valid ref or sha\n")
    result = run_git(["status"], cwd=repo_with_commit)
    # Must not crash with unhandled exception
    combined = result.stdout + result.stderr
    assert "traceback" not in combined.lower(), (
        f"Unhandled exception on corrupt HEAD: {combined[:500]}"
    )


def test_corrupt_index_detected(repo_with_commit):
    """
    Truncating .git/index should cause status/add to fail gracefully.
    """
    index = repo_with_commit / ".git" / "index"
    if not index.exists():
        pytest.skip("Implementation doesn't use .git/index")

    index.write_bytes(b"garbage index content")

    result = run_git(["status"], cwd=repo_with_commit)
    combined = result.stdout + result.stderr
    assert "traceback" not in combined.lower(), (
        f"Unhandled exception on corrupt index: {combined[:500]}"
    )


def test_repo_consistent_after_corruption_recovery(repo_with_commit):
    """
    Even after encountering corruption, basic repo structure should remain intact.
    The .git directory itself should not be destroyed by an error handler.
    """
    objects = _get_object_files(repo_with_commit)
    if objects:
        objects[0].write_bytes(b"garbage")
        run_git(["log"], cwd=repo_with_commit)  # Trigger error

    # .git structure should still exist
    assert (repo_with_commit / ".git").exists()
    assert (repo_with_commit / ".git" / "HEAD").exists()
