#!/usr/bin/env python3
"""
Regenerate the Results section in README.md from leaderboard/data/runs.json.

Usage:
    python update_readme.py          # update README.md in place
    python update_readme.py --check  # exit 1 if README is out of date
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
RUNS_FILE = PROJECT_ROOT / "leaderboard" / "data" / "runs.json"
README_FILE = PROJECT_ROOT / "README.md"

BEGIN_MARKER = "<!-- BEGIN RESULTS -->"
END_MARKER = "<!-- END RESULTS -->"


def load_runs() -> list[dict]:
    return json.loads(RUNS_FILE.read_text())


def best_per_harness_model(runs: list[dict]) -> dict[str, list[dict]]:
    """Group runs by harness. For each (harness, model), keep only the latest."""
    latest: dict[tuple[str, str], dict] = {}
    for r in runs:
        key = (r["harness"], r["model"])
        existing = latest.get(key)
        if existing is None or r.get("date", "") > existing.get("date", ""):
            latest[key] = r

    by_harness: dict[str, list[dict]] = defaultdict(list)
    for (harness, _), run in sorted(latest.items()):
        by_harness[harness].append(run)

    # Sort each harness's runs by total_score descending
    for harness in by_harness:
        by_harness[harness].sort(key=lambda r: r["total_score"], reverse=True)

    return dict(by_harness)


def _fmt_score(score: float) -> str:
    return f"**{score:.2f}**"


def _fmt_pct(passed: int, total: int) -> str:
    pct = int(passed / total * 100) if total else 0
    return f"{passed}/{total} ({pct}%)"


def _fmt_quality(run: dict) -> str:
    q = run["scores"]["quality"]
    if q.get("detail", {}).get("plumbing_porcelain_separation", {}).get("reasoning", "") == "[dry_run: LLM not called]":
        return "—"
    # Check all dimensions for dry_run
    for dim_data in q.get("detail", {}).values():
        if isinstance(dim_data, dict) and dim_data.get("reasoning", "") == "[dry_run: LLM not called]":
            return "—"
    return f"{q['score']:.1f}"


def _fmt_cost(run: dict) -> str:
    cost = run.get("cost_usd", 0)
    if cost >= 1.0:
        return f"${cost:.2f}"
    return f"${cost:.2f}"


def generate_harness_table(harness: str, runs: list[dict]) -> str:
    """Generate a markdown table for one harness."""
    lines = [f"### {harness}\n"]

    # Determine which columns to show based on available data
    has_extension = any(
        r["scores"].get("extension", {}).get("detail", {}).get("passed", 0) > 0
        for r in runs
    )

    if has_extension:
        lines.append("| Model | Score | Functional | Adversarial | Extension | Performance | Quality | Cost |")
        lines.append("|-------|-------|-----------|-------------|-----------|-------------|---------|------|")
    else:
        lines.append("| Model | Score | Functional | Adversarial | Reliability | Quality | Cost |")
        lines.append("|-------|-------|-----------|-------------|-------------|---------|------|")

    for r in runs:
        func = r["scores"]["functional"]
        func_detail = func.get("detail", {})
        func_passed = func_detail.get("total_passed", 0)
        func_total = func_detail.get("total_tests", 0)

        adv = r["scores"]["adversarial"]
        adv_detail = adv.get("detail", {})
        adv_passed = adv_detail.get("passed", 0)
        adv_total = adv_detail.get("total", 0)

        if has_extension:
            ext = r["scores"].get("extension", {})
            ext_detail = ext.get("detail", {})
            ext_passed = ext_detail.get("passed", 0)
            ext_total = ext_detail.get("total", 0)
            perf = r["scores"]["performance"]["score"]
            lines.append(
                f"| {r['model']} | {_fmt_score(r['total_score'])} "
                f"| {_fmt_pct(func_passed, func_total)} "
                f"| {_fmt_pct(adv_passed, adv_total)} "
                f"| {ext_passed}/{ext_total} "
                f"| {perf:.0f} "
                f"| {_fmt_quality(r)} "
                f"| {_fmt_cost(r)} |"
            )
        else:
            rel = r["scores"]["reliability"]
            rel_detail = rel.get("detail", {})
            rel_passed = rel_detail.get("passed", 0)
            rel_total = rel_detail.get("total", 0)
            lines.append(
                f"| {r['model']} | {_fmt_score(r['total_score'])} "
                f"| {_fmt_pct(func_passed, func_total)} "
                f"| {_fmt_pct(adv_passed, adv_total)} "
                f"| {_fmt_pct(rel_passed, rel_total)} "
                f"| {_fmt_quality(r)} "
                f"| {_fmt_cost(r)} |"
            )

    return "\n".join(lines)


def generate_cross_harness_table(by_harness: dict[str, list[dict]]) -> str:
    """Generate the cross-harness average table."""
    # Collect per-model scores across harnesses
    model_scores: dict[str, dict[str, float]] = defaultdict(dict)
    for harness, runs in sorted(by_harness.items()):
        for r in runs:
            model_scores[r["model"]][harness] = r["total_score"]

    harnesses = sorted(by_harness.keys())
    lines = ["### Cross-harness average\n"]

    header = "| Model |"
    sep = "|-------|"
    for h in harnesses:
        header += f" {h} |"
        sep += "------|"
    header += " Average |"
    sep += "---------|"
    lines.append(header)
    lines.append(sep)

    rows = []
    for model, scores in model_scores.items():
        vals = [scores.get(h) for h in harnesses]
        present = [v for v in vals if v is not None]
        avg = statistics.mean(present) if present else 0
        rows.append((avg, model, vals))

    rows.sort(key=lambda x: -x[0])

    for avg, model, vals in rows:
        row = f"| {model} |"
        for v in vals:
            row += f" {v:.2f} |" if v is not None else " — |"
        row += f" **{avg:.2f}** |"
        lines.append(row)

    return "\n".join(lines)


def generate_results_section(runs: list[dict]) -> str:
    """Generate the full results section from runs.json."""
    by_harness = best_per_harness_model(runs)

    parts = [
        "## Results\n",
        "Generated from `leaderboard/data/runs.json` by `python update_readme.py`.",
        "Single runs, not best-of-N.\n",
    ]

    for harness in sorted(by_harness.keys()):
        parts.append(generate_harness_table(harness, by_harness[harness]))
        parts.append("")

    if len(by_harness) > 1:
        parts.append(generate_cross_harness_table(by_harness))
        parts.append("")

    parts.append(
        "All three frontier models are within ~1.5 points of each other on average. "
        "The ranking changes by harness — there's no single winner. "
        "mini-sqlite (the hardest harness) shows the widest spread."
    )

    return "\n".join(parts)


def update_readme(check_only: bool = False) -> int:
    readme = README_FILE.read_text()

    if BEGIN_MARKER not in readme or END_MARKER not in readme:
        print(f"error: README.md missing {BEGIN_MARKER} / {END_MARKER} markers", file=sys.stderr)
        return 1

    runs = load_runs()
    new_section = generate_results_section(runs)

    before = readme.split(BEGIN_MARKER)[0]
    after = readme.split(END_MARKER)[1]
    new_readme = f"{before}{BEGIN_MARKER}\n{new_section}\n{END_MARKER}{after}"

    if check_only:
        if new_readme != readme:
            print("README.md results are out of date. Run: python update_readme.py")
            return 1
        print("README.md results are up to date.")
        return 0

    README_FILE.write_text(new_readme)
    print(f"Updated README.md results section from {len(runs)} runs.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Update README.md results from runs.json")
    parser.add_argument("--check", action="store_true", help="Check if README is up to date (exit 1 if not)")
    args = parser.parse_args()
    return update_readme(check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())
