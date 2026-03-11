"""
Behavioral scorer — runs tier 1-3 pytest tests against a submission.

Returns a weighted score (tier1=40%, tier2=35%, tier3=25%) in [0, 100].
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


TIER_WEIGHTS = {
    "tier1": 0.40,
    "tier2": 0.35,
    "tier3": 0.25,
}


@dataclass
class TierResult:
    tier: str
    passed: int
    failed: int
    errors: int
    skipped: int
    total: int
    score: float  # 0-100
    failures: list[dict[str, str]] = field(default_factory=list)


@dataclass
class BehavioralResult:
    tier_results: dict[str, TierResult]
    weighted_score: float  # 0-100
    total_passed: int
    total_tests: int
    raw_json: dict[str, Any] = field(default_factory=dict)


def _harness_cmd_var(harness_name: str) -> str:
    """Derive env var name from harness name. 'mini-redis' -> 'MINI_REDIS_CMD'."""
    return harness_name.upper().replace("-", "_") + "_CMD"


def _find_cmd(workspace: Path, harness_name: str) -> list[str]:
    """Find the CLI entry point for any harness in the workspace directory."""
    workspace = workspace.resolve()
    stem = harness_name.replace("-", "_")  # e.g. "mini_redis"
    candidates = [
        workspace / f"{stem}.py",
        workspace / f"{harness_name}.py",
        workspace / stem / "__main__.py",
        workspace / "src" / f"{stem}.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return [sys.executable, str(candidate)]
    for name in [stem, harness_name]:
        binary = workspace / name
        if binary.exists() and binary.stat().st_mode & 0o111:
            return [str(binary)]
    return [sys.executable, str(workspace / f"{stem}.py")]


def _find_mini_git_cmd(workspace: Path) -> list[str]:
    """Backwards-compat alias -- delegates to _find_cmd."""
    return _find_cmd(workspace, "mini-git")


def run_behavioral(
    submission_path: Path,
    harness_path: Path,
    python: str = sys.executable,
    timeout: int = 300,
) -> BehavioralResult:
    """
    Run tier 1-3 behavioral tests against the implementation in submission_path.

    The implementation is located via a harness-specific env var (e.g. MINI_GIT_CMD,
    MINI_REDIS_CMD), derived from harness_path.name.
    """
    submission_path = Path(submission_path)
    harness_path = Path(harness_path)
    tests_root = harness_path / "tests"
    harness_name = harness_path.name
    cmd_var = _harness_cmd_var(harness_name)
    impl_cmd = _find_cmd(submission_path / "workspace", harness_name)

    tier_results: dict[str, TierResult] = {}

    for tier_name, weight in TIER_WEIGHTS.items():
        tier_path = tests_root / tier_name
        if not tier_path.exists():
            continue

        result = _run_pytest_tier(
            tier_path=tier_path,
            tests_root=tests_root,
            impl_cmd=impl_cmd,
            cmd_var=cmd_var,
            python=python,
            timeout=timeout,
        )
        tier_results[tier_name] = result

    weighted_score = sum(
        r.score * TIER_WEIGHTS.get(name, 0)
        for name, r in tier_results.items()
    )

    total_passed = sum(r.passed for r in tier_results.values())
    total_tests = sum(r.total for r in tier_results.values())

    return BehavioralResult(
        tier_results=tier_results,
        weighted_score=round(weighted_score, 2),
        total_passed=total_passed,
        total_tests=total_tests,
    )


def _run_pytest_tier(
    tier_path: Path,
    tests_root: Path,
    impl_cmd: list[str],
    cmd_var: str = "MINI_GIT_CMD",
    python: str = sys.executable,
    timeout: int = 300,
    # Keep old kwarg name as alias for callers that haven't updated yet
    mini_git_cmd: list[str] | None = None,
) -> TierResult:
    """Run pytest for one tier and parse results."""
    if mini_git_cmd is not None:
        impl_cmd = mini_git_cmd  # backwards compat
    tier_name = tier_path.name

    cmd = [
        python, "-m", "pytest",
        str(tier_path),
        "--tb=short",
        "--json-report",
        f"--json-report-file=/tmp/bench_{tier_name}.json",
        "-q",
        "--timeout=30",
        f"--rootdir={tests_root}",
    ]

    import os
    env_extra = {cmd_var: " ".join(impl_cmd)}
    env = {**os.environ, **env_extra}

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env,
        )
    except subprocess.TimeoutExpired:
        return TierResult(
            tier=tier_name, passed=0, failed=0, errors=1, skipped=0,
            total=0, score=0.0,
            failures=[{"test": "timeout", "message": f"Tier timed out after {timeout}s"}],
        )

    # Parse JSON report if available
    report_file = Path(f"/tmp/bench_{tier_name}.json")
    if report_file.exists():
        try:
            report = json.loads(report_file.read_text())
            return _parse_json_report(tier_name, report)
        except (json.JSONDecodeError, KeyError):
            pass

    # Fall back: parse pytest stdout
    return _parse_pytest_stdout(tier_name, proc.stdout)


def _parse_json_report(tier_name: str, report: dict) -> TierResult:
    """Parse pytest-json-report output."""
    summary = report.get("summary", {})
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    error = summary.get("error", 0)
    skipped = summary.get("skipped", 0)
    total = summary.get("total", passed + failed + error + skipped)

    failures = []
    for test in report.get("tests", []):
        if test.get("outcome") in ("failed", "error"):
            failures.append({
                "test": test.get("nodeid", ""),
                "message": test.get("call", {}).get("longrepr", "")[:500],
            })

    score = (passed / total * 100) if total > 0 else 0.0
    return TierResult(
        tier=tier_name,
        passed=passed, failed=failed, errors=error, skipped=skipped,
        total=total, score=round(score, 2), failures=failures,
    )


def _parse_pytest_stdout(tier_name: str, stdout: str) -> TierResult:
    """Minimal fallback parser for pytest plain output."""
    passed = failed = errors = skipped = 0
    for line in stdout.splitlines():
        if " passed" in line:
            try:
                passed = int(line.strip().split()[0])
            except (ValueError, IndexError):
                pass
        if " failed" in line:
            try:
                failed = int(line.strip().split()[0])
            except (ValueError, IndexError):
                pass

    total = passed + failed + errors + skipped
    score = (passed / total * 100) if total > 0 else 0.0
    return TierResult(
        tier=tier_name, passed=passed, failed=failed,
        errors=errors, skipped=skipped, total=total, score=round(score, 2),
    )
