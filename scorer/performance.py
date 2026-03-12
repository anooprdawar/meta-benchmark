"""
Performance scorer — runs latency benchmarks and scores against thresholds.

Computes p50/p95/p99 per operation, scores each against thresholds.json.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from scorer.behavioral import _find_cmd, _harness_cmd_var


@dataclass
class BenchmarkResult:
    name: str
    p50: float
    p95: float
    p99: float
    target_p95: float
    fail_p95: float
    score: float  # 0-100 (piecewise linear)
    samples: list[float] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class PerformanceResult:
    benchmark_results: dict[str, BenchmarkResult]
    weighted_score: float  # 0-100
    notes: str = ""


def run_performance(
    submission_path: Path,
    harness_path: Path,
    python: str = sys.executable,
    timeout: int = 600,
) -> PerformanceResult:
    submission_path = Path(submission_path)
    harness_path = Path(harness_path)
    harness_name = harness_path.name
    cmd_var = _harness_cmd_var(harness_name)
    tests_root = harness_path / "tests"
    perf_path = tests_root / "performance"
    thresholds_file = perf_path / "thresholds.json"

    if not perf_path.exists() or not thresholds_file.exists():
        return PerformanceResult(
            benchmark_results={}, weighted_score=0.0,
            notes="Performance test directory not found.",
        )

    thresholds = json.loads(thresholds_file.read_text())["benchmarks"]
    impl_cmd = _find_cmd(submission_path / "workspace", harness_name)

    # Discover bench files from thresholds.json "file" field
    bench_files = {
        key: perf_path / thresh["file"]
        for key, thresh in thresholds.items()
        if "file" in thresh
    }

    results: dict[str, BenchmarkResult] = {}
    total_weight = 0.0
    weighted_sum = 0.0

    for bench_name, bench_file in bench_files.items():
        thresh = thresholds[bench_name]
        weight = thresh["weight"]
        if not bench_file.exists():
            result = BenchmarkResult(
                name=bench_name, p50=0, p95=0, p99=0,
                target_p95=thresh["target_p95_seconds"],
                fail_p95=thresh["fail_p95_seconds"],
                score=0.0, skipped=True, skip_reason="Benchmark file not found",
            )
        else:
            result = _run_benchmark(
                bench_file=bench_file,
                bench_name=bench_name,
                harness_tests_root=tests_root,
                impl_cmd=impl_cmd,
                cmd_var=cmd_var,
                thresh=thresh,
                python=python,
                timeout=timeout,
            )
        results[bench_name] = result
        total_weight += weight
        weighted_sum += result.score * weight

    weighted_score = (weighted_sum / total_weight) if total_weight > 0 else 0.0
    return PerformanceResult(
        benchmark_results=results,
        weighted_score=round(weighted_score, 2),
    )


def _run_benchmark(
    bench_file: Path,
    bench_name: str,
    harness_tests_root: Path,
    impl_cmd: list[str],
    cmd_var: str,
    thresh: dict,
    python: str,
    timeout: int,
) -> BenchmarkResult:
    import os, time
    cmd = [
        python, "-m", "pytest", str(bench_file),
        "-v", "--tb=short",
        f"--rootdir={harness_tests_root}",
        "--timeout=300", "-s",
    ]
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, cmd_var: " ".join(impl_cmd)},
        )
        elapsed = time.perf_counter() - start
    except subprocess.TimeoutExpired:
        return BenchmarkResult(
            name=bench_name, p50=timeout, p95=timeout, p99=timeout,
            target_p95=thresh["target_p95_seconds"],
            fail_p95=thresh["fail_p95_seconds"],
            score=0.0, skipped=True, skip_reason=f"Timed out after {timeout}s",
        )
    p50, p95, p99 = _extract_timing(proc.stdout + proc.stderr, elapsed)
    score = _compute_score(p95, thresh["target_p95_seconds"], thresh["fail_p95_seconds"])
    return BenchmarkResult(
        name=bench_name, p50=round(p50, 3), p95=round(p95, 3), p99=round(p99, 3),
        target_p95=thresh["target_p95_seconds"],
        fail_p95=thresh["fail_p95_seconds"],
        score=round(score, 2),
    )


def _extract_timing(output: str, fallback: float) -> tuple[float, float, float]:
    """Extract p50/p95/p99 from test output. Falls back to total elapsed time."""
    import re
    for line in output.splitlines():
        match = re.search(r"p50=([\d.]+)s.*p95=([\d.]+)s.*p99=([\d.]+)s", line)
        if match:
            return float(match.group(1)), float(match.group(2)), float(match.group(3))
    return fallback, fallback, fallback


def _compute_score(p95: float, target: float, fail: float) -> float:
    """
    Piecewise linear score:
    - p95 <= target → 100
    - p95 >= fail → 0
    - target < p95 < fail → linear interpolation
    """
    if p95 <= target:
        return 100.0
    if p95 >= fail:
        return 0.0
    # Linear interpolation: 100 at target, 0 at fail
    return 100.0 * (fail - p95) / (fail - target)
