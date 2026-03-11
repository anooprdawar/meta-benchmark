"""
Extension scorer — drives the second-prompt extension round.

When an agent is provided, sends the extension prompt to the agent, waits for it
to update the workspace, then runs the extension test suite against the updated code.

When no agent is provided (e.g. scoring a static submission), returns a zero score
with phase="static" so the caller knows a live re-run is needed.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from scorer.behavioral import _find_mini_git_cmd, _run_pytest_tier


@dataclass
class ExtensionResult:
    passed: int
    failed: int
    total: int
    score: float  # 0-100
    phase: str  # "static", "live_agent", or "live_agent_failed"
    failures: list[dict[str, str]] = field(default_factory=list)
    notes: str = ""


def run_extension(
    submission_path: Path,
    harness_path: Path,
    python: str = sys.executable,
    timeout: int = 300,
    agent=None,  # if provided, calls agent.extend() with extension prompt
) -> ExtensionResult:
    """
    Run the extension test suite, optionally after driving a live agent round.

    If agent is provided:
      - Read harness_path/tests/extension/prompt.md
      - Call agent.extend(submission_path/workspace, extension_prompt_text)
      - Run the extension tests against the now-updated workspace
      - Set phase = "live_agent"

    If agent is None:
      - Return score=0, phase="static" without running any tests.
        The extension dimension requires a live agent second-prompt round.
    """
    submission_path = Path(submission_path)
    harness_path = Path(harness_path)
    tests_root = harness_path / "tests"
    extension_path = tests_root / "extension"

    if not extension_path.exists():
        return ExtensionResult(
            passed=0, failed=0, total=0, score=0.0, phase="static",
            notes="No extension test directory found.",
        )

    if agent is None:
        return ExtensionResult(
            passed=0,
            failed=0,
            total=16,
            score=0.0,
            phase="static",
            notes=(
                "Extension requires live agent (second-prompt flow). "
                "Score is 0 until re-run with --extension-live."
            ),
        )

    # --- Live agent path ---
    extension_prompt_path = extension_path / "prompt.md"
    if not extension_prompt_path.exists():
        return ExtensionResult(
            passed=0, failed=0, total=16, score=0.0, phase="live_agent_failed",
            notes=f"Extension prompt not found at {extension_prompt_path}",
        )

    extension_prompt_text = extension_prompt_path.read_text(encoding="utf-8")
    workspace_path = submission_path / "workspace"

    try:
        agent.extend(workspace_path, extension_prompt_text)
    except Exception as exc:
        return ExtensionResult(
            passed=0, failed=0, total=16, score=0.0, phase="live_agent_failed",
            notes=f"agent.extend() raised: {exc}",
        )

    mini_git_cmd = _find_mini_git_cmd(workspace_path)
    tier_result = _run_pytest_tier(
        tier_path=extension_path,
        tests_root=tests_root,
        mini_git_cmd=mini_git_cmd,
        python=python,
        timeout=timeout,
    )

    return ExtensionResult(
        passed=tier_result.passed,
        failed=tier_result.failed,
        total=tier_result.total,
        score=round(tier_result.score, 2),
        phase="live_agent",
        failures=tier_result.failures,
    )
