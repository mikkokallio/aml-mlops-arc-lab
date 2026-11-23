"""Strict comparison for the 100-row Arc acceptance request."""

import numpy as np


def compare_predictions(reference: list, actual: list) -> dict:
    for label, values in (("reference", reference), ("response", actual)):
        if not isinstance(values, list) or len(values) != 100:
            raise ValueError(f"{label} must be a flat 100-number JSON array.")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in values):
            raise ValueError(f"{label} contains nonnumeric or nested values.")
    expected = np.asarray(reference, dtype=float)
    observed = np.asarray(actual, dtype=float)
    if not np.isfinite(expected).all() or not np.isfinite(observed).all():
        raise ValueError("Predictions must all be finite.")
    np.testing.assert_allclose(observed, expected, rtol=0.00001, atol=0.00001)
    return {
        "passed": True,
        "rows": 100,
        "rtol": 0.00001,
        "atol": 0.00001,
        "max_absolute_error": float(np.max(np.abs(observed - expected))),
    }
