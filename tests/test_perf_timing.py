"""Unit tests for performance timing extraction."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scorer.performance import _extract_timing


def test_extract_full_format():
    """Standard p50/p95/p99 line is extracted correctly."""
    output = "log 10k commits — p50=0.312s p95=0.345s p99=0.401s"
    p50, p95, p99 = _extract_timing(output, fallback=99.0)
    assert p50 == 0.312
    assert p95 == 0.345
    assert p99 == 0.401


def test_extract_ignores_elapsed_only_format():
    """Old 'elapsed=Xs' format should NOT be silently parsed as p50."""
    output = "add 100k files — elapsed=1.234s"
    p50, p95, p99 = _extract_timing(output, fallback=99.0)
    assert p50 == 99.0
    assert p95 == 99.0
    assert p99 == 99.0


def test_extract_fallback_when_no_match():
    """Missing timing line returns fallback for all three values."""
    output = "no timing here"
    p50, p95, p99 = _extract_timing(output, fallback=5.5)
    assert p50 == 5.5
    assert p95 == 5.5
    assert p99 == 5.5


def test_extract_multiline_output():
    """Finds timing line anywhere in multi-line output."""
    output = (
        "PASSED test_diff_1k_p95_within_target\n"
        "\ndiff 1k files — p50=0.250s p95=0.310s p99=0.350s\n"
        "1 passed in 12.34s"
    )
    p50, p95, p99 = _extract_timing(output, fallback=99.0)
    assert p50 == 0.250
    assert p95 == 0.310
    assert p99 == 0.350
