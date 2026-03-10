"""Reliability test helpers."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import run_git, make_commit, MINI_GIT_CMD, MINI_GIT_NOT_FOUND  # noqa: F401


def run_git_async(cmd: list[str], cwd: Path) -> subprocess.Popen:
    """Start a mini-git command asynchronously, return the Popen object."""
    full_cmd = MINI_GIT_CMD + cmd
    return subprocess.Popen(
        full_cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def is_repo_consistent(repo: Path) -> tuple[bool, str]:
    """
    Check basic repo consistency:
    - .git/ directory exists
    - HEAD is readable and valid
    - No zero-length object files
    """
    git_dir = repo / ".git"
    if not git_dir.exists():
        return False, ".git directory missing"

    head = git_dir / "HEAD"
    if not head.exists():
        return False, "HEAD missing"

    head_content = head.read_text().strip()
    if not head_content:
        return False, "HEAD is empty"

    # Check for zero-length object files (sign of interrupted write)
    objects_dir = git_dir / "objects"
    if objects_dir.exists():
        for obj_file in objects_dir.rglob("*"):
            if obj_file.is_file() and obj_file.stat().st_size == 0:
                return False, f"Zero-length object file: {obj_file}"

    return True, "ok"
