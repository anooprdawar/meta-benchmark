"""Unit tests for N/A weight redistribution in build_scorecard."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scorer.scorecard import DIMENSION_WEIGHTS, _redistribute_na_weight


def test_mutation_na_redistributes_proportionally_to_d1_d2_d3():
    """When mutation is N/A, weight goes to functional+adversarial+extension proportionally."""
    weights = dict(DIMENSION_WEIGHTS)
    _redistribute_na_weight(weights, na_dim="mutation",
                            target_dims=["functional", "adversarial", "extension"])

    assert weights["mutation"] == 0.0
    # Total should still be 1.0
    assert abs(sum(weights.values()) - 1.0) < 1e-9

    # Proportions of the three recipient dims should be preserved
    base = DIMENSION_WEIGHTS
    base_sum = base["functional"] + base["adversarial"] + base["extension"]
    expected_functional = base["functional"] + base["mutation"] * base["functional"] / base_sum
    assert abs(weights["functional"] - expected_functional) < 1e-9

    expected_adversarial = base["adversarial"] + base["mutation"] * base["adversarial"] / base_sum
    assert abs(weights["adversarial"] - expected_adversarial) < 1e-9

    expected_extension = base["extension"] + base["mutation"] * base["extension"] / base_sum
    assert abs(weights["extension"] - expected_extension) < 1e-9


def test_weights_sum_to_one_after_redistribution():
    """Redistributed weights always sum to 1.0."""
    weights = dict(DIMENSION_WEIGHTS)
    _redistribute_na_weight(weights, na_dim="mutation",
                            target_dims=["functional", "adversarial", "extension"])
    assert abs(sum(weights.values()) - 1.0) < 1e-9
