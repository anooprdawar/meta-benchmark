"""Conftest for extension tests — remote operations."""

import sys
from pathlib import Path

# Allow importing from parent tests conftest
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from conftest import run_git, make_commit  # noqa: F401 (re-export for extension tests)


@pytest.fixture
def two_repos(tmp_path):
    """
    Returns (local_repo, remote_repo) — both initialized mini-git repos.
    remote_repo has one commit; local_repo is empty and knows remote_repo as 'origin'.
    """
    local = tmp_path / "local"
    remote = tmp_path / "remote"
    local.mkdir()
    remote.mkdir()

    # Initialize both repos
    run_git(["init"], cwd=local)
    run_git(["init"], cwd=remote)

    # Make a commit in remote
    (remote / "hello.txt").write_text("hello from remote\n")
    run_git(["add", "hello.txt"], cwd=remote)
    run_git(["commit", "-m", "initial commit in remote"], cwd=remote)

    # Make a commit in local
    (local / "local.txt").write_text("local file\n")
    run_git(["add", "local.txt"], cwd=local)
    run_git(["commit", "-m", "initial commit in local"], cwd=local)

    return local, remote
