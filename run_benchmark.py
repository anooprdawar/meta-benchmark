#!/usr/bin/env python3
"""
Run a full benchmark pass against one or more models and produce real scorecards.

Usage:
    python run_benchmark.py                           # all default models
    python run_benchmark.py --models claude-opus-4-6
    python run_benchmark.py --models gpt-5.4 gpt-5.3-codex gemini-2.5-pro
    python run_benchmark.py --dry-run                 # skip LLM judge API calls in scoring
    python run_benchmark.py --no-extension            # skip live extension round

Required environment variables (depending on models run):
    ANTHROPIC_API_KEY          Claude models
    GEMINI_API_KEY             Gemini models
    OPENAI_META_BENCHMARK_KEY  OpenAI models
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

HARNESS = "mini-git"
HARNESS_PATH = PROJECT_ROOT / "harnesses" / HARNESS

RUNS = [
    {"agent": "claude-api",  "model": "claude-opus-4-6"},
    {"agent": "gemini-api",  "model": "gemini-2.5-pro"},
    {"agent": "openai-api",  "model": "gpt-5.4"},
    {"agent": "openai-api",  "model": "gpt-5.3-codex"},
]


def run_one(agent_name: str, model: str, dry_run: bool, run_extension_live: bool = True) -> dict:
    from runner.agents import get_agent
    from runner.environment import Environment
    from scorer.scorecard import score_submission

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    model_slug = model.replace("/", "-").replace(":", "-").replace(".", "-")
    output_dir = PROJECT_ROOT / "submissions" / f"{HARNESS}-{model_slug}-{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Model:  {model}")
    print(f"  Agent:  {agent_name}")
    print(f"  Output: {output_dir}")
    print(f"{'='*60}\n")

    env = Environment(harness_path=HARNESS_PATH, output_dir=output_dir)
    workspace = env.prepare()

    agent = get_agent(agent_name, model=model, harness_path=HARNESS_PATH)
    agent_result = agent.run(workspace)
    env_result = env.capture_result(workspace)

    print(f"\n  Duration:  {env_result.duration_seconds:.1f}s")
    print(f"  Files:     {env_result.file_count}")
    print(f"  Tokens:    {agent_result.tokens_input:,} in / {agent_result.tokens_output:,} out")
    print(f"  Est. cost: ${agent_result.cost_estimate_usd:.4f}")

    # Write metadata.json into output_dir (which already contains workspace/)
    metadata = {
        "model": model,
        "agent_framework": agent_name,
        "agent_framework_version": "unknown",
        "scaffolding_config": {},
        "date": datetime.now(timezone.utc).isoformat(),
        "harness": HARNESS,
        "harness_version": "1.0.0",
        "wall_clock_seconds": env_result.duration_seconds,
        "tokens_input": agent_result.tokens_input,
        "tokens_output": agent_result.tokens_output,
        "cost_usd": agent_result.cost_estimate_usd,
        "exit_code": agent_result.exit_code,
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    submission_path = output_dir

    print(f"\nScoring {model}...")
    scorecard = score_submission(
        submission_path=submission_path,
        harness_path=HARNESS_PATH,
        output_path=submission_path / "scorecard.json",
        dry_run=dry_run,
        python=sys.executable,
        agent=agent if run_extension_live else None,
    )

    return scorecard.to_dict()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", help="Override models to run")
    parser.add_argument("--dry-run", action="store_true", help="Skip LLM judge API calls")
    parser.add_argument(
        "--no-extension",
        action="store_true",
        help="Skip the live extension round (second-prompt flow); extension score will be 0",
    )
    args = parser.parse_args()

    run_extension_live = not args.no_extension

    runs_to_execute = RUNS
    if args.models:
        # Map model name to agent
        model_agent_map = {r["model"]: r["agent"] for r in RUNS}
        runs_to_execute = [
            {"model": m, "agent": model_agent_map.get(m, _infer_agent(m))}
            for m in args.models
        ]

    results = []
    for run in runs_to_execute:
        try:
            scorecard = run_one(
                run["agent"], run["model"],
                dry_run=args.dry_run,
                run_extension_live=run_extension_live,
            )
            results.append(scorecard)
            print(f"\n✓ {run['model']}: {scorecard['total_score']:.1f}/100")
        except Exception as e:
            print(f"\n✗ {run['model']} failed: {e}", file=sys.stderr)
            import traceback; traceback.print_exc()

    if not results:
        print("\nNo successful runs.", file=sys.stderr)
        return 1

    # Update leaderboard data
    leaderboard_file = PROJECT_ROOT / "leaderboard" / "data" / "runs.json"
    existing = json.loads(leaderboard_file.read_text()) if leaderboard_file.exists() else []

    # Convert scorecards to leaderboard format, replace synthetic samples for same model
    new_ids = {r["model"] for r in results}
    kept = [r for r in existing if not _is_synthetic(r) and r.get("model") not in new_ids]

    leaderboard_entries = []
    for sc in results:
        entry = {
            "id": sc["submission_id"],
            "harness": sc["harness"],
            "harness_version": sc["harness_version"],
            "model": sc["model"],
            "agent_framework": sc["agent_framework"],
            "date": sc["date"],
            "wall_clock_seconds": sc["metadata"].get("wall_clock_seconds", 0),
            "tokens_input": sc["metadata"].get("tokens_input", 0),
            "tokens_output": sc["metadata"].get("tokens_output", 0),
            "cost_usd": sc["metadata"].get("cost_usd", 0),
            "total_score": sc["total_score"],
            "scores": sc["scores"],
            "_real": True,
        }
        leaderboard_entries.append(entry)

    all_entries = kept + leaderboard_entries
    all_entries.sort(key=lambda r: r.get("total_score", 0), reverse=True)

    leaderboard_file.write_text(json.dumps(all_entries, indent=2), encoding="utf-8")
    print(f"\nLeaderboard updated: {leaderboard_file}")

    print("\n" + "="*60)
    print("  FINAL RESULTS")
    print("="*60)
    for sc in sorted(results, key=lambda r: r["total_score"], reverse=True):
        print(f"  {sc['model']:<30} {sc['total_score']:>6.1f}/100")
    print()

    return 0


def _infer_agent(model: str) -> str:
    """Infer agent type from model name."""
    if "claude" in model:
        return "claude-api"
    if "gemini" in model:
        return "gemini-api"
    if any(x in model for x in ["gpt", "o1", "o3", "o4"]):
        return "openai-api"
    return "claude-api"


def _is_synthetic(entry: dict) -> bool:
    """Identify the hand-written sample data entries."""
    return not entry.get("_real", False)


if __name__ == "__main__":
    sys.exit(main())
