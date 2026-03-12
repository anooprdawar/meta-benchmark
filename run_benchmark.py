#!/usr/bin/env python3
"""
Run a full benchmark pass against one or more models across one or more harnesses.

Usage:
    python run_benchmark.py                                          # all models, all harnesses
    python run_benchmark.py --models claude-opus-4-6                 # one model, all harnesses
    python run_benchmark.py --harnesses mini-redis mini-sqlite       # all models, specific harnesses
    python run_benchmark.py --models gpt-5.4 --harnesses mini-git   # one model, one harness
    python run_benchmark.py --dry-run                                # skip LLM judge API calls
    python run_benchmark.py --no-extension                           # skip live extension round

Required environment variables (depending on models run):
    ANTHROPIC_META_BENCHMARK_KEY   Claude models (fallback: ANTHROPIC_API_KEY)
    GEMINI_META_BENCHMARK_KEY      Gemini models (fallback: GEMINI_API_KEY)
    OPENAI_META_BENCHMARK_KEY      OpenAI models (fallback: OPENAI_API_KEY)
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

DEFAULT_RUNS = [
    {"agent": "claude-api",  "model": "claude-opus-4-6"},
    {"agent": "gemini-api",  "model": "gemini-2.5-pro"},
    {"agent": "openai-api",  "model": "gpt-5.4"},
    {"agent": "openai-api",  "model": "gpt-5.3-codex"},
]


def _discover_harnesses() -> list[str]:
    """Return sorted list of harness names found in harnesses/."""
    harnesses_dir = PROJECT_ROOT / "harnesses"
    return sorted(p.name for p in harnesses_dir.iterdir() if p.is_dir() and (p / "prompt.md").exists())


def run_one(
    harness: str,
    agent_name: str,
    model: str,
    dry_run: bool,
    run_extension_live: bool = True,
) -> dict:
    from runner.agents import get_agent
    from runner.environment import Environment
    from scorer.scorecard import score_submission

    harness_path = PROJECT_ROOT / "harnesses" / harness

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    model_slug = model.replace("/", "-").replace(":", "-").replace(".", "-")
    output_dir = PROJECT_ROOT / "submissions" / f"{harness}-{model_slug}-{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Harness: {harness}")
    print(f"  Model:   {model}")
    print(f"  Agent:   {agent_name}")
    print(f"  Output:  {output_dir}")
    print(f"{'='*60}\n")

    env = Environment(harness_path=harness_path, output_dir=output_dir)
    workspace = env.prepare()

    agent = get_agent(agent_name, model=model, harness_path=harness_path)
    agent_result = agent.run(workspace)
    env_result = env.capture_result(workspace)

    print(f"\n  Duration:  {env_result.duration_seconds:.1f}s")
    print(f"  Files:     {env_result.file_count}")
    print(f"  Tokens:    {agent_result.tokens_input:,} in / {agent_result.tokens_output:,} out")
    print(f"  Est. cost: ${agent_result.cost_estimate_usd:.4f}")

    metadata = {
        "model": model,
        "agent_framework": agent_name,
        "agent_framework_version": "unknown",
        "scaffolding_config": {},
        "date": datetime.now(timezone.utc).isoformat(),
        "harness": harness,
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

    print(f"\nScoring {model} on {harness}...")
    scorecard = score_submission(
        submission_path=output_dir,
        harness_path=harness_path,
        output_path=output_dir / "scorecard.json",
        dry_run=dry_run,
        python=sys.executable,
        agent=agent if run_extension_live else None,
    )

    return scorecard.to_dict()


def main():
    parser = argparse.ArgumentParser(
        description="Run a full benchmark pass across harnesses and models.",
    )
    parser.add_argument("--models", nargs="+", help="Models to run (default: all)")
    parser.add_argument("--harnesses", nargs="+", help="Harnesses to run (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Skip LLM judge API calls")
    parser.add_argument(
        "--no-extension",
        action="store_true",
        help="Skip the live extension round (second-prompt flow); extension score will be 0",
    )
    args = parser.parse_args()

    run_extension_live = not args.no_extension

    # Resolve harnesses
    available_harnesses = _discover_harnesses()
    harnesses = args.harnesses or available_harnesses
    for h in harnesses:
        if h not in available_harnesses:
            print(f"error: harness '{h}' not found. Available: {available_harnesses}", file=sys.stderr)
            return 1

    # Resolve models
    runs_to_execute = DEFAULT_RUNS
    if args.models:
        model_agent_map = {r["model"]: r["agent"] for r in DEFAULT_RUNS}
        runs_to_execute = [
            {"model": m, "agent": model_agent_map.get(m, _infer_agent(m))}
            for m in args.models
        ]

    results = []
    for harness in harnesses:
        for run in runs_to_execute:
            try:
                scorecard = run_one(
                    harness=harness,
                    agent_name=run["agent"],
                    model=run["model"],
                    dry_run=args.dry_run,
                    run_extension_live=run_extension_live,
                )
                results.append(scorecard)
                print(f"\n  {run['model']} on {harness}: {scorecard['total_score']:.1f}/100")
            except Exception as e:
                print(f"\n  {run['model']} on {harness} failed: {e}", file=sys.stderr)
                import traceback; traceback.print_exc()

    if not results:
        print("\nNo successful runs.", file=sys.stderr)
        return 1

    # Update leaderboard data
    leaderboard_file = PROJECT_ROOT / "leaderboard" / "data" / "runs.json"
    existing = json.loads(leaderboard_file.read_text()) if leaderboard_file.exists() else []

    # Replace entries for same (harness, model) pair
    new_keys = {(r["harness"], r["model"]) for r in results}
    kept = [
        r for r in existing
        if r.get("_scored", False)
        and (r.get("harness"), r.get("model")) not in new_keys
    ]

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
            "_scored": True,
        }
        leaderboard_entries.append(entry)

    all_entries = kept + leaderboard_entries
    all_entries.sort(key=lambda r: r.get("total_score", 0), reverse=True)

    leaderboard_file.write_text(json.dumps(all_entries, indent=2), encoding="utf-8")
    print(f"\nLeaderboard updated: {leaderboard_file}")

    print("\n" + "="*60)
    print("  FINAL RESULTS")
    print("="*60)
    for sc in sorted(results, key=lambda r: (-r["total_score"],)):
        print(f"  {sc['harness']:<16} {sc['model']:<30} {sc['total_score']:>6.1f}/100")
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


if __name__ == "__main__":
    sys.exit(main())
