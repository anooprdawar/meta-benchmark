"""
Scorecard aggregator — combines all scorer outputs into a final JSON scorecard.

Output schema:
{
  "harness": "mini-git",
  "harness_version": "1.0.0",
  "submission_id": "...",
  "model": "claude-sonnet-4-6",
  "agent_framework": "claude-code",
  "date": "...",
  "scores": {
    "functional": {"score": 85.2, "weight": 0.30, "detail": {...}},
    "adversarial": {"score": 72.0, "weight": 0.15, "detail": {...}},
    "extension": {"score": 60.0, "weight": 0.10, "detail": {...}},
    "mutation": {"score": 45.0, "weight": 0.10, "detail": {...}},
    "performance": {"score": 90.0, "weight": 0.15, "detail": {...}},
    "reliability": {"score": 80.0, "weight": 0.10, "detail": {...}},
    "quality": {"score": 78.0, "weight": 0.10, "detail": {...}}
  },
  "total_score": 78.3,
  "metadata": {...},
  "report": "..."  // human-readable summary
}
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scorer.behavioral import BehavioralResult
from scorer.adversarial import AdversarialResult
from scorer.extension import ExtensionResult
from scorer.mutation import MutationResult
from scorer.performance import PerformanceResult
from scorer.reliability import ReliabilityResult
from scorer.judge import JudgeResult


DIMENSION_WEIGHTS = {
    "functional": 0.30,
    "adversarial": 0.15,
    "extension": 0.10,
    "mutation": 0.10,
    "performance": 0.15,
    "reliability": 0.10,
    "quality": 0.10,
}


@dataclass
class Scorecard:
    harness: str
    harness_version: str
    submission_id: str
    model: str
    agent_framework: str
    date: str
    scores: dict[str, dict[str, Any]]
    total_score: float
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        d = {
            "harness": self.harness,
            "harness_version": self.harness_version,
            "submission_id": self.submission_id,
            "model": self.model,
            "agent_framework": self.agent_framework,
            "date": self.date,
            "scores": self.scores,
            "total_score": self.total_score,
            "metadata": self.metadata,
            "report": self.generate_report(),
        }
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def generate_report(self) -> str:
        """Generate a human-readable summary of the scorecard."""
        lines = [
            f"# Scorecard: {self.harness} — {self.model}",
            f"Date: {self.date}",
            f"Agent framework: {self.agent_framework}",
            "",
            f"## Total Score: {self.total_score:.1f}/100",
            "",
            "## Dimension Scores",
            "",
            f"{'Dimension':<25} {'Score':>6}  {'Weight':>7}  {'Weighted':>8}",
            f"{'─' * 25} {'─' * 6}  {'─' * 7}  {'─' * 8}",
        ]
        for dim, data in self.scores.items():
            score = data.get("score", 0.0)
            weight = data.get("weight", 0.0)
            weighted = score * weight
            lines.append(
                f"{dim:<25} {score:>6.1f}  {weight:>6.0%}  {weighted:>8.1f}"
            )
        lines.extend([
            "",
            "## Notes",
        ])
        for dim, data in self.scores.items():
            notes = data.get("notes", "")
            if notes:
                lines.append(f"- **{dim}**: {notes}")
        return "\n".join(lines)


def _redistribute_na_weight(
    weights: dict[str, float],
    na_dim: str,
    target_dims: list[str],
) -> None:
    """
    Redistribute the weight of an N/A dimension proportionally to target_dims.
    Modifies weights in-place. The total weight sum is preserved.
    """
    na_weight = weights[na_dim]
    if na_weight == 0.0:
        return
    target_sum = sum(weights[d] for d in target_dims)
    if target_sum == 0.0:
        return
    for d in target_dims:
        weights[d] += na_weight * weights[d] / target_sum
    weights[na_dim] = 0.0


def build_scorecard(
    submission_path: Path,
    harness_path: Path,
    behavioral: BehavioralResult,
    adversarial: AdversarialResult,
    extension: ExtensionResult,
    mutation: MutationResult,
    performance: PerformanceResult,
    reliability: ReliabilityResult,
    judge: JudgeResult,
    metadata: dict[str, Any] | None = None,
) -> Scorecard:
    """Assemble all scorer results into a Scorecard."""
    submission_path = Path(submission_path)

    # Load metadata from submission if available
    meta_file = submission_path / "metadata.json"
    submission_meta: dict[str, Any] = {}
    if meta_file.exists():
        try:
            submission_meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    if metadata:
        submission_meta.update(metadata)

    # Handle N/A redistribution: if mutation has no tests, redistribute its weight
    weights = dict(DIMENSION_WEIGHTS)
    if mutation.total == 0:
        # Redistribute mutation weight proportionally to functional, adversarial, extension
        # per rubric.md Section 8: "redistributed proportionally to D1, D2, D3"
        _redistribute_na_weight(
            weights,
            na_dim="mutation",
            target_dims=["functional", "adversarial", "extension"],
        )

    scores = {
        "functional": {
            "score": behavioral.weighted_score,
            "weight": weights["functional"],
            "detail": {
                "total_passed": behavioral.total_passed,
                "total_tests": behavioral.total_tests,
                "tiers": {
                    name: {
                        "passed": r.passed,
                        "total": r.total,
                        "score": r.score,
                    }
                    for name, r in behavioral.tier_results.items()
                },
            },
            "notes": (
                f"{behavioral.total_passed}/{behavioral.total_tests} tests passing"
                if behavioral.total_tests > 0 else "No tests run"
            ),
        },
        "adversarial": {
            "score": adversarial.score,
            "weight": weights["adversarial"],
            "detail": {
                "passed": adversarial.passed,
                "total": adversarial.total,
                "survival_rate": adversarial.survival_rate,
                "held_out_passed": adversarial.held_out_passed,
                "held_out_total": adversarial.held_out_total,
                "verified": adversarial.verified,
            },
            "notes": (
                f"{adversarial.passed}/{adversarial.total} edge cases survived"
                + (" [maintainer-verified]" if adversarial.verified else "")
                if adversarial.total > 0 else "No adversarial tests run"
            ),
        },
        "extension": {
            "score": extension.score,
            "weight": weights["extension"],
            "detail": {
                "passed": extension.passed,
                "total": extension.total,
                "phase": extension.phase,
            },
            "notes": f"{extension.passed}/{extension.total} extension tests passing" if extension.total > 0 else "",
        },
        "mutation": {
            "score": mutation.score,
            "weight": weights["mutation"],
            "detail": {
                "killed": mutation.killed,
                "survived": mutation.survived,
                "total": mutation.total,
                "method": mutation.method,
            },
            "notes": mutation.notes if mutation.notes else f"{mutation.kill_rate:.0f}% mutation kill rate",
        },
        "performance": {
            "score": performance.weighted_score,
            "weight": weights["performance"],
            "detail": {
                name: {
                    "p50": r.p50,
                    "p95": r.p95,
                    "target_p95": r.target_p95,
                    "score": r.score,
                    "skipped": r.skipped,
                }
                for name, r in performance.benchmark_results.items()
            },
            "notes": performance.notes if performance.notes else "",
        },
        "reliability": {
            "score": reliability.score,
            "weight": weights["reliability"],
            "detail": {
                "passed": reliability.passed,
                "total": reliability.total,
            },
            "notes": reliability.notes if reliability.notes else f"{reliability.passed}/{reliability.total} reliability scenarios passing",
        },
        "quality": {
            "score": judge.aggregate_score,
            "weight": weights["quality"],
            "detail": {
                dim: {"score": ds.score, "reasoning": ds.reasoning}
                for dim, ds in judge.dimension_scores.items()
            },
            "notes": judge.notes if judge.notes else f"LLM judge score (models: {', '.join(judge.models_used[:1])}...)",
        },
    }

    # Compute weighted total
    total = sum(
        data["score"] * data["weight"]
        for data in scores.values()
    )

    return Scorecard(
        harness=submission_meta.get("harness", harness_path.name),
        harness_version=submission_meta.get("harness_version", "1.0.0"),
        submission_id=submission_path.name,
        model=submission_meta.get("model", "unknown"),
        agent_framework=submission_meta.get("agent_framework", "unknown"),
        date=submission_meta.get("date", datetime.now(timezone.utc).isoformat()),
        scores=scores,
        total_score=round(total, 2),
        metadata=submission_meta,
    )


def score_submission(
    submission_path: Path,
    harness_path: Path,
    output_path: Path | None = None,
    dry_run: bool = False,
    python: str | None = None,
    agent=None,
) -> Scorecard:
    """
    Full scoring pipeline: run all scorers and produce a Scorecard.

    Parameters:
        submission_path: Path to the submission directory
        harness_path: Path to the harness directory
        output_path: If provided, write scorecard JSON here
        dry_run: Skip LLM judge calls
        python: Python interpreter path (defaults to sys.executable)
        agent: If provided, drives the live extension round (second-prompt flow)
    """
    import sys
    python = python or sys.executable

    print(f"Scoring submission: {submission_path}")
    print(f"Harness: {harness_path}")
    print()

    print("Running behavioral tests...")
    from scorer.behavioral import run_behavioral
    behavioral = run_behavioral(submission_path, harness_path, python=python)
    print(f"  Functional: {behavioral.weighted_score:.1f}/100 "
          f"({behavioral.total_passed}/{behavioral.total_tests} tests)")

    print("Running adversarial tests...")
    from scorer.adversarial import run_adversarial
    adversarial = run_adversarial(submission_path, harness_path, python=python)
    print(f"  Adversarial: {adversarial.score:.1f}/100 "
          f"({adversarial.passed}/{adversarial.total} survived)")

    print("Running extension tests...")
    from scorer.extension import run_extension
    extension = run_extension(submission_path, harness_path, python=python, agent=agent)
    print(f"  Extension: {extension.score:.1f}/100 "
          f"({extension.passed}/{extension.total}) [{extension.phase}]")

    print("Running mutation testing...")
    from scorer.mutation import run_mutation
    mutation = run_mutation(submission_path, python=python)
    print(f"  Mutation: {mutation.score:.1f}/100 ({mutation.method})")

    print("Running performance benchmarks...")
    from scorer.performance import run_performance
    performance = run_performance(submission_path, harness_path, python=python)
    print(f"  Performance: {performance.weighted_score:.1f}/100")

    print("Running reliability tests...")
    from scorer.reliability import run_reliability
    reliability = run_reliability(submission_path, harness_path, python=python)
    print(f"  Reliability: {reliability.score:.1f}/100 "
          f"({reliability.passed}/{reliability.total})")

    print("Running LLM judge...")
    from scorer.judge import run_judge
    judge = run_judge(submission_path, harness_path, dry_run=dry_run)
    print(f"  Quality: {judge.aggregate_score:.1f}/100")

    scorecard = build_scorecard(
        submission_path=submission_path,
        harness_path=harness_path,
        behavioral=behavioral,
        adversarial=adversarial,
        extension=extension,
        mutation=mutation,
        performance=performance,
        reliability=reliability,
        judge=judge,
    )

    print()
    print(f"Total score: {scorecard.total_score:.1f}/100")

    if output_path:
        Path(output_path).write_text(scorecard.to_json(), encoding="utf-8")
        print(f"Scorecard written to: {output_path}")

    return scorecard


def main() -> None:
    """CLI entry point for scorer."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Score a meta-benchmark submission")
    parser.add_argument("--submission", required=True, help="Path to submission directory")
    parser.add_argument("--harness", required=True, help="Harness name or path")
    parser.add_argument("--output", default=None, help="Output JSON path")
    parser.add_argument("--dry-run", action="store_true", help="Skip LLM judge calls")
    args = parser.parse_args()

    harness_path = Path(args.harness)
    if not harness_path.is_absolute():
        # Try as name relative to harnesses/
        from scorer.scorecard import _find_project_root
        harness_path = _find_project_root() / "harnesses" / args.harness

    scorecard = score_submission(
        submission_path=Path(args.submission),
        harness_path=harness_path,
        output_path=Path(args.output) if args.output else None,
        dry_run=args.dry_run,
    )

    print()
    print(scorecard.generate_report())


def _find_project_root() -> Path:
    here = Path(__file__).resolve().parent
    for candidate in [here.parent, here]:
        if (candidate / "harnesses").exists():
            return candidate
    return here.parent


if __name__ == "__main__":
    main()
