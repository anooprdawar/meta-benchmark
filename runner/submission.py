"""Submission directory creation and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runner.agents.claude_code import AgentResult
from runner.environment import EnvironmentResult

_REQUIRED_METADATA_FIELDS = [
    "model",
    "agent_framework",
    "date",
    "harness",
    "harness_version",
]


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]


class Submission:
    """Creates and validates benchmark submission directories."""

    def __init__(self, submissions_root: Path | None = None) -> None:
        self.submissions_root = Path(submissions_root or "submissions")

    def create(
        self,
        harness: str,
        model: str,
        agent_framework: str,
        workspace_path: Path,
        agent_result: AgentResult,
        env_result: EnvironmentResult,
        harness_version: str = "1.0.0",
        scaffolding_config: dict[str, Any] | None = None,
        notes: str = "",
    ) -> Path:
        """
        Create a submission directory and write metadata.json.

        Returns the path to the submission directory.
        """
        # The workspace is already inside the submission dir (output_dir/workspace),
        # so the submission path is the workspace's parent.
        submission_path = Path(workspace_path).parent
        submission_path.mkdir(parents=True, exist_ok=True)

        metadata: dict[str, Any] = {
            "model": model,
            "agent_framework": agent_framework,
            "agent_framework_version": "unknown",
            "scaffolding_config": scaffolding_config or {},
            "date": datetime.now(timezone.utc).isoformat(),
            "harness": harness,
            "harness_version": harness_version,
            "wall_clock_seconds": env_result.duration_seconds,
            "tokens_input": agent_result.tokens_input,
            "tokens_output": agent_result.tokens_output,
            "cost_usd": agent_result.cost_estimate_usd,
            "exit_code": agent_result.exit_code,
            "notes": notes,
        }

        (submission_path / "metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )

        return submission_path

    def validate(self, submission_path: Path) -> ValidationResult:
        """
        Validate a submission directory structure and metadata.

        Returns a ValidationResult with any errors found.
        """
        submission_path = Path(submission_path)
        errors: list[str] = []

        if not submission_path.exists():
            return ValidationResult(valid=False, errors=[f"Path does not exist: {submission_path}"])

        metadata_path = submission_path / "metadata.json"
        if not metadata_path.exists():
            errors.append("Missing metadata.json")
        else:
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                for field in _REQUIRED_METADATA_FIELDS:
                    if field not in metadata:
                        errors.append(f"metadata.json missing required field: '{field}'")
            except json.JSONDecodeError as e:
                errors.append(f"metadata.json is not valid JSON: {e}")

        workspace_path = submission_path / "workspace"
        if not workspace_path.exists():
            errors.append("Missing workspace/ directory")
        elif not any(workspace_path.rglob("*")):
            errors.append("workspace/ directory is empty")

        return ValidationResult(valid=len(errors) == 0, errors=errors)
