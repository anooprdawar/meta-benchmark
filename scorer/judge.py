"""
LLM Judge scorer — qualitative code quality assessment.

Reads judge/rubric.md and calibration samples, then queries 3 LLM models
to score the submission on 5 qualitative dimensions. Aggregates scores.

In this implementation, the actual LLM calls are stubbed with clear
integration points. The judge infrastructure (calibration loading,
aggregation, JSON output) is fully implemented.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


JUDGE_DIMENSIONS = [
    "plumbing_porcelain_separation",
    "object_model_abstraction",
    "naming_consistency",
    "test_quality",
    "scope_discipline",
]

# Default judge models — override via judge_models parameter
DEFAULT_JUDGE_MODELS = [
    "claude-sonnet-4-6",
    "claude-opus-4-6",
    "claude-sonnet-4-6",  # Third vote from same model family for now
]


@dataclass
class DimensionScore:
    dimension: str
    score: float  # 0-100
    reasoning: str
    model_scores: list[float] = field(default_factory=list)
    std_dev: float = 0.0


@dataclass
class JudgeResult:
    dimension_scores: dict[str, DimensionScore]
    aggregate_score: float  # 0-100 (mean across dimensions)
    models_used: list[str]
    calibration_anchored: bool
    notes: str = ""


def run_judge(
    submission_path: Path,
    harness_path: Path,
    judge_models: list[str] | None = None,
    dry_run: bool = False,
) -> JudgeResult:
    """
    Run the LLM judge against the submission.

    Parameters:
        submission_path: Path to the submission directory
        harness_path: Path to the harness directory (for rubric + calibration)
        judge_models: List of model IDs to use as judges (default: 3 models)
        dry_run: If True, return placeholder scores without calling any LLMs.
                 Use for testing the scoring pipeline.
    """
    submission_path = Path(submission_path)
    harness_path = Path(harness_path)
    judge_models = judge_models or DEFAULT_JUDGE_MODELS

    rubric_path = harness_path / "judge" / "rubric.md"
    calibration_path = harness_path / "judge" / "calibration"

    rubric = rubric_path.read_text(encoding="utf-8") if rubric_path.exists() else ""
    calibration = _load_calibration(calibration_path)
    code_context = _build_code_context(submission_path / "workspace")

    if dry_run or not _llm_available():
        return _dry_run_result(judge_models)

    # Run judge for each model
    all_scores: dict[str, list[float]] = {dim: [] for dim in JUDGE_DIMENSIONS}
    all_reasonings: dict[str, list[str]] = {dim: [] for dim in JUDGE_DIMENSIONS}

    for model in judge_models:
        model_scores = _call_judge_model(
            model=model,
            rubric=rubric,
            calibration=calibration,
            code_context=code_context,
        )
        for dim in JUDGE_DIMENSIONS:
            all_scores[dim].append(model_scores.get(dim, {}).get("score", 0.0))
            all_reasonings[dim].append(model_scores.get(dim, {}).get("reasoning", ""))

    # Aggregate: mean across models, with std dev
    dimension_scores: dict[str, DimensionScore] = {}
    for dim in JUDGE_DIMENSIONS:
        scores = all_scores[dim]
        mean_score = statistics.mean(scores) if scores else 0.0
        std = statistics.stdev(scores) if len(scores) > 1 else 0.0
        # Pick the reasoning from the median-scoring model
        best_idx = min(range(len(scores)), key=lambda i: abs(scores[i] - mean_score))
        reasoning = all_reasonings[dim][best_idx] if all_reasonings[dim] else ""

        dimension_scores[dim] = DimensionScore(
            dimension=dim,
            score=round(mean_score, 1),
            reasoning=reasoning,
            model_scores=scores,
            std_dev=round(std, 2),
        )

    aggregate = statistics.mean(d.score for d in dimension_scores.values())

    return JudgeResult(
        dimension_scores=dimension_scores,
        aggregate_score=round(aggregate, 2),
        models_used=judge_models,
        calibration_anchored=bool(calibration),
    )


def _dry_run_result(judge_models: list[str]) -> JudgeResult:
    """Return placeholder scores for dry runs and testing."""
    dimension_scores = {
        dim: DimensionScore(
            dimension=dim,
            score=0.0,
            reasoning="[dry_run: LLM not called]",
            model_scores=[0.0] * len(judge_models),
        )
        for dim in JUDGE_DIMENSIONS
    }
    return JudgeResult(
        dimension_scores=dimension_scores,
        aggregate_score=0.0,
        models_used=judge_models,
        calibration_anchored=False,
        notes="dry_run=True: no LLM calls made. Run with dry_run=False for real scoring.",
    )


def _llm_available() -> bool:
    """Check if an LLM API is available for judge calls."""
    import os
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"))


def _load_calibration(calibration_path: Path) -> dict[str, Any]:
    """Load calibration scores from calibration/scores.json."""
    scores_file = calibration_path / "scores.json"
    if not scores_file.exists():
        return {}
    try:
        return json.loads(scores_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _build_code_context(workspace: Path) -> str:
    """
    Build a code context string from the agent's implementation.
    Includes key source files (up to ~10,000 tokens), plus test files
    so the judge can score test_quality.
    """
    if not workspace.exists():
        return "[workspace not found]"

    parts: list[str] = []
    total_chars = 0
    max_chars = 40_000  # ~10k tokens

    # Exclude mutation artifacts directory entirely
    def _is_source(p: Path) -> bool:
        return "mutants" not in p.parts and "test" not in p.name.lower()

    def _is_test(p: Path) -> bool:
        return "mutants" not in p.parts and "test" in p.name.lower()

    # Source files first (sorted by size descending — largest is usually the main impl)
    src_files = sorted(
        [p for p in workspace.rglob("*.py") if _is_source(p)],
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    # Test files second
    test_files = sorted(
        [p for p in workspace.rglob("*.py") if _is_test(p)],
        key=lambda p: p.stat().st_size,
        reverse=True,
    )

    src_budget = int(max_chars * 0.70)  # 28k chars for source
    test_budget = max_chars - src_budget  # 12k chars for tests

    for f in src_files[:10]:
        if total_chars >= src_budget:
            break
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            relative = f.relative_to(workspace)
            excerpt = content[:src_budget - total_chars]
            parts.append(f"=== {relative} ===\n{excerpt}")
            total_chars += len(excerpt)
        except OSError:
            continue

    test_chars = 0
    for f in test_files[:10]:
        if test_chars >= test_budget:
            break
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            relative = f.relative_to(workspace)
            excerpt = content[:test_budget - test_chars]
            parts.append(f"=== {relative} (tests) ===\n{excerpt}")
            test_chars += len(excerpt)
        except OSError:
            continue

    return "\n\n".join(parts) if parts else "[no Python source files found in workspace]"


def _call_judge_model(
    model: str,
    rubric: str,
    calibration: dict[str, Any],
    code_context: str,
) -> dict[str, dict[str, Any]]:
    """
    Call a judge LLM model and return per-dimension scores.

    Returns dict: {dimension_name: {"score": float, "reasoning": str}}

    This is the integration point for actual LLM API calls.
    Current implementation uses the Anthropic SDK if available.
    """
    prompt = _build_judge_prompt(rubric, calibration, code_context)

    # Try Anthropic SDK
    try:
        import anthropic
        client = anthropic.Anthropic()
        message = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_judge_response(message.content[0].text)
    except (ImportError, Exception):
        pass

    # Return zeros if no LLM available
    return {dim: {"score": 0.0, "reasoning": "LLM unavailable"} for dim in JUDGE_DIMENSIONS}


def _build_judge_prompt(rubric: str, calibration: dict, code_context: str) -> str:
    """Build the judge prompt with rubric, calibration anchors, and code."""
    cal_examples = ""
    for sample in calibration.get("samples", []):
        cal_examples += f"\nExample '{sample['id']}' ({sample['label']}):\n"
        for dim, data in sample.get("human_scores", {}).items():
            cal_examples += f"  {dim}: {data['score']}/100 — {data['reasoning']}\n"

    return f"""You are an expert code quality judge evaluating a mini-git implementation.

## Scoring Rubric

{rubric}

## Calibration Examples (ground truth — anchor your scores to these)

{cal_examples if cal_examples else "No calibration examples available."}

## Implementation to Score

{code_context}

## Task

Score this implementation on each of the 5 dimensions using the rubric above.
Respond with ONLY a JSON object in this exact format:

{{
  "plumbing_porcelain_separation": {{"score": <0-100>, "reasoning": "<1-2 sentences>"}},
  "object_model_abstraction": {{"score": <0-100>, "reasoning": "<1-2 sentences>"}},
  "naming_consistency": {{"score": <0-100>, "reasoning": "<1-2 sentences>"}},
  "test_quality": {{"score": <0-100>, "reasoning": "<1-2 sentences>"}},
  "scope_discipline": {{"score": <0-100>, "reasoning": "<1-2 sentences>"}}
}}"""


def _parse_judge_response(response: str) -> dict[str, dict[str, Any]]:
    """Parse the judge's JSON response."""
    import re
    # Extract JSON block
    match = re.search(r"\{.*\}", response, re.DOTALL)
    if not match:
        return {dim: {"score": 0.0, "reasoning": "Parse error"} for dim in JUDGE_DIMENSIONS}
    try:
        data = json.loads(match.group())
        return {
            dim: {
                "score": float(data.get(dim, {}).get("score", 0)),
                "reasoning": str(data.get(dim, {}).get("reasoning", "")),
            }
            for dim in JUDGE_DIMENSIONS
        }
    except (json.JSONDecodeError, TypeError, ValueError):
        return {dim: {"score": 0.0, "reasoning": "Parse error"} for dim in JUDGE_DIMENSIONS}
