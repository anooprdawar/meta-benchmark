"""Extension tests: push and pull between local repos."""

import pytest
from conftest import run_git, assert_success, assert_failure


def test_fetch_from_local_remote(two_repos):
    """fetch downloads objects from local path remote."""
    local, remote = two_repos
    run_git(["remote", "add", "origin", str(remote)], cwd=local)
    result = run_git(["fetch", "origin"], cwd=local)
    assert_success(result)


def test_fetch_creates_remote_ref(two_repos):
    """After fetch, refs/remotes/origin/<branch> exists locally."""
    local, remote = two_repos
    run_git(["remote", "add", "origin", str(remote)], cwd=local)
    run_git(["fetch", "origin"], cwd=local)
    # Check refs/remotes/origin/ directory or similar
    remote_refs = local / ".git" / "refs" / "remotes" / "origin"
    # Accept either refs/remotes/origin/ structure or FETCH_HEAD
    fetch_head = local / ".git" / "FETCH_HEAD"
    assert remote_refs.exists() or fetch_head.exists(), (
        "After fetch, either refs/remotes/origin/ or FETCH_HEAD should exist"
    )


def test_pull_merges_remote_commits(two_repos):
    """pull fetches and merges remote commits into local branch."""
    local, remote = two_repos
    run_git(["remote", "add", "origin", str(remote)], cwd=local)

    # Determine remote's default branch
    head_content = (remote / ".git" / "HEAD").read_text().strip()
    branch = head_content.split("/")[-1] if "/" in head_content else "main"

    result = run_git(["pull", "origin", branch], cwd=local)
    assert_success(result)

    # After pull, local should have remote's hello.txt
    assert (local / "hello.txt").exists(), "hello.txt from remote should be present after pull"


def test_push_to_local_remote(two_repos):
    """push sends local commits to local path remote."""
    local, remote = two_repos
    run_git(["remote", "add", "origin", str(remote)], cwd=local)

    # Determine local's default branch
    head_content = (local / ".git" / "HEAD").read_text().strip()
    branch = head_content.split("/")[-1] if "/" in head_content else "main"

    # Add a new file and commit
    (local / "new_feature.txt").write_text("new feature\n")
    run_git(["add", "new_feature.txt"], cwd=local)
    run_git(["commit", "-m", "add new feature"], cwd=local)

    result = run_git(["push", "origin", branch], cwd=local)
    assert_success(result)


def test_push_updates_remote_branch(two_repos):
    """After push, remote has the new commit."""
    local, remote = two_repos
    run_git(["remote", "add", "origin", str(remote)], cwd=local)

    head_content = (local / ".git" / "HEAD").read_text().strip()
    branch = head_content.split("/")[-1] if "/" in head_content else "main"

    # Get remote SHA before push
    remote_ref = remote / ".git" / "refs" / "heads" / branch
    sha_before = remote_ref.read_text().strip() if remote_ref.exists() else ""

    # Push a new commit
    (local / "pushed.txt").write_text("pushed content\n")
    run_git(["add", "pushed.txt"], cwd=local)
    run_git(["commit", "-m", "pushed commit"], cwd=local)
    run_git(["push", "origin", branch], cwd=local)

    sha_after = remote_ref.read_text().strip() if remote_ref.exists() else ""
    assert sha_after != sha_before, "Remote branch SHA should change after push"


def test_fetch_nonexistent_remote_fails(repo):
    """fetch on an unregistered remote should fail."""
    result = run_git(["fetch", "nonexistent"], cwd=repo)
    assert_failure(result)


def test_push_nonexistent_remote_fails(repo):
    """push to an unregistered remote should fail."""
    result = run_git(["push", "nonexistent", "main"], cwd=repo)
    assert_failure(result)
