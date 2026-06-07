"""Tests for the perfect-model validation harness."""

import numpy as np
import pytest

from validation.perfect_model import perfect_model_test


def _structured_ensemble(seed=0, n=120):
    """An ensemble with a skilful cluster (track +signal) and anti-correlated
    outliers, where future values follow the historical clustering — so
    skill-weighting SHOULD beat equal weighting."""
    rng = np.random.default_rng(seed)
    signal = rng.normal(0, 1, n)
    hist, future = {}, {}
    for i in range(6):
        hist[f"G{i}"] = signal + rng.normal(0, 0.3, n)
        future[f"G{i}"] = 5.0 + rng.normal(0, 0.2)
    for i in range(3):
        hist[f"B{i}"] = -signal + rng.normal(0, 0.3, n)
        future[f"B{i}"] = 12.0 + rng.normal(0, 1)
    return hist, future


def test_weighting_beats_equal_on_structured_ensemble():
    res = perfect_model_test(*_structured_ensemble())
    assert res["rmse_weighted"] < res["rmse_equal"]
    assert res["rmse_improvement_pct"] > 0
    assert res["n_truth_weighting_better"] >= res["n_models"] // 2


def test_homogeneous_ensemble_no_worse_than_equal():
    # All models equally good (track one signal); weighting should not hurt.
    rng = np.random.default_rng(3)
    n = 150
    signal = rng.normal(0, 1, n)
    hist = {f"M{i}": signal + rng.normal(0, 0.3, n) for i in range(8)}
    future = {f"M{i}": 4.0 + rng.normal(0, 0.05) for i in range(8)}
    res = perfect_model_test(hist, future)
    # within noise; weighting must not be materially worse than equal
    assert res["rmse_weighted"] <= res["rmse_equal"] * 1.25


def test_outputs_are_consistent():
    res = perfect_model_test(*_structured_ensemble())
    assert res["n_models"] == 9
    assert len(res["per_truth"]) == 9
    for p in res["per_truth"]:
        assert p["err_weighted"] == pytest.approx(abs(p["pred_weighted"] - p["truth_future"]))


def test_too_few_models_raises():
    with pytest.raises(ValueError, match="at least 3"):
        perfect_model_test({"A": np.zeros(10), "B": np.ones(10)},
                           {"A": 1.0, "B": 2.0})
