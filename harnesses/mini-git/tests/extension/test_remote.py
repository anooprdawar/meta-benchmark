"""Extension tests: remote add/list/remove operations."""

import pytest
from conftest import run_git, assert_success, assert_failure


# ---------------------------------------------------------------------------
# remote add
# ---------------------------------------------------------------------------

def test_remote_add_succeeds(repo):
    """remote add with a valid name and URL should exit 0."""
    result = run_git(["remote", "add", "origin", "https://example.com/repo.git"], cwd=repo)
    assert_success(result)


def test_remote_add_persisted(repo):
    """After remote add, the remote should appear in remote list."""
    run_git(["remote", "add", "origin", "https://example.com/repo.git"], cwd=repo)
    result = run_git(["remote", "-v"], cwd=repo)
    assert_success(result)
    assert "origin" in result.stdout
    assert "example.com" in result.stdout


def test_remote_add_local_path(repo, tmp_path):
    """remote add works with a local path as URL."""
    bare = tmp_path / "bare"
    bare.mkdir()
    run_git(["init"], cwd=bare)
    result = run_git(["remote", "add", "origin", str(bare)], cwd=repo)
    assert_success(result)


def test_remote_add_multiple(repo):
    """Can add more than one remote."""
    run_git(["remote", "add", "origin", "https://github.com/user/repo.git"], cwd=repo)
    run_git(["remote", "add", "upstream", "https://github.com/org/repo.git"], cwd=repo)
    result = run_git(["remote", "-v"], cwd=repo)
    assert "origin" in result.stdout
    assert "upstream" in result.stdout


def test_remote_add_duplicate_name_fails(repo):
    """Adding a remote with an existing name should fail."""
    run_git(["remote", "add", "origin", "https://first.com/repo.git"], cwd=repo)
    result = run_git(["remote", "add", "origin", "https://second.com/repo.git"], cwd=repo)
    assert_failure(result)


# ---------------------------------------------------------------------------
# remote list
# ---------------------------------------------------------------------------

def test_remote_list_empty(repo):
    """remote -v with no remotes shows nothing (empty output is fine)."""
    result = run_git(["remote", "-v"], cwd=repo)
    assert_success(result)


def test_remote_list_shows_url(repo):
    """remote -v shows the URL for each remote."""
    url = "https://example.com/repo.git"
    run_git(["remote", "add", "origin", url], cwd=repo)
    result = run_git(["remote", "-v"], cwd=repo)
    assert url in result.stdout


# ---------------------------------------------------------------------------
# remote remove
# ---------------------------------------------------------------------------

def test_remote_remove(repo):
    """remote remove deletes an existing remote."""
    run_git(["remote", "add", "origin", "https://example.com/repo.git"], cwd=repo)
    result = run_git(["remote", "remove", "origin"], cwd=repo)
    assert_success(result)
    listing = run_git(["remote", "-v"], cwd=repo)
    assert "origin" not in listing.stdout


def test_remote_remove_nonexistent_fails(repo):
    """Removing a remote that doesn't exist should fail."""
    result = run_git(["remote", "remove", "nonexistent"], cwd=repo)
    assert_failure(result)
