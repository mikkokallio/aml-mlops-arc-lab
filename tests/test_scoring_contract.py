import pytest

from scripts.compare_predictions import compare_predictions


def test_scoring_tolerance_rejects_real_prediction_difference():
    assert compare_predictions([1.0] * 100, [1.000001] * 100)["passed"]
    with pytest.raises(AssertionError):
        compare_predictions([1.0] * 100, [1.01] * 100)


@pytest.mark.parametrize("actual", [[[1.0]] * 100, [float("nan")] * 100, [1.0] * 99])
def test_scoring_rejects_invalid_response_shape_or_values(actual):
    with pytest.raises(ValueError):
        compare_predictions([1.0] * 100, actual)
