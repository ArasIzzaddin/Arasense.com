"""Tests for the Arasense Model Trust Engine (src/climate/trust_engine.py)."""

import numpy as np
import pytest

from climate.trust_engine import KGE_BENCHMARK, ModelTrustEngine


def _ensemble(seed=42, n=80):
    rng = np.random.default_rng(seed)
    obs = rng.normal(285, 4, n)  # Kelvin-like reference
    models = [
        obs * 1.01 + rng.normal(0.2, 0.4, n),   # excellent
        obs * 1.10 + rng.normal(0.5, 0.6, n),   # clear warm bias
        obs * 1.00 + rng.normal(0.0, 2.5, n),   # right mean, weak phase
        rng.normal(285, 4, n),                  # uncorrelated junk
    ]
    names = ["GOOD", "WARM-BIAS", "NOISY", "JUNK"]
    return obs, models, names


def test_weights_sum_to_one_and_reject_gets_zero():
    obs, models, names = _ensemble()
    eng = ModelTrustEngine(obs, models, names)
    weights = {r["name"]: r["weight"] for r in eng.reports}

    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-9)
    # The uncorrelated model must not earn weight.
    assert weights["JUNK"] == 0.0
    # The excellent model must carry the most.
    assert max(weights, key=weights.get) == "GOOD"


def test_reject_tier_for_below_benchmark_or_negative_corr():
    obs = np.linspace(280, 300, 50)
    eng = ModelTrustEngine(obs, [obs[::-1].copy()], ["MIRROR"])
    rep = eng.reports[0]
    assert rep["correlation"] < 0
    assert rep["trust_tier"] == "reject"
    assert rep["weight"] == 0.0


def test_error_attribution_identifies_bias():
    # A pure warm-bias model: mean shifted, variability & phase intact.
    rng = np.random.default_rng(0)
    obs = rng.normal(285, 4, 100)
    biased = obs + 6.0  # +6 K offset only
    eng = ModelTrustEngine(obs, [biased], ["BIAS-ONLY"])
    attr = eng.reports[0]["error_attribution"]
    assert attr["dominant"] == "bias"
    assert attr["bias"] > 0.9


def test_attribution_fractions_normalised():
    obs, models, names = _ensemble()
    eng = ModelTrustEngine(obs, models, names)
    for rep in eng.reports:
        a = rep["error_attribution"]
        if a["dominant"] != "none":
            assert a["bias"] + a["variability"] + a["phase"] == pytest.approx(1.0, abs=1e-9)


def test_summary_effective_size_within_bounds():
    obs, models, names = _ensemble()
    eng = ModelTrustEngine(obs, models, names)
    s = eng.summary()
    assert 1.0 <= s["effective_ensemble_size"] <= s["n_kept"] + 1e-9
    assert s["best_model"] == "GOOD"


def test_weighted_ensemble_matches_manual_weighted_mean():
    obs, models, names = _ensemble()
    eng = ModelTrustEngine(obs, models, names)

    # Fake "future" projections (constant per model for an easy check).
    future = {"GOOD": np.full(5, 2.0), "WARM-BIAS": np.full(5, 4.0),
              "NOISY": np.full(5, 6.0), "JUNK": np.full(5, 99.0)}
    out = eng.weighted_ensemble(future)

    kept = [r for r in eng.reports if r["weight"] > 0]
    w = np.array([r["weight"] for r in kept]); w = w / w.sum()
    vals = np.array([float(future[r["name"]][0]) for r in kept])
    expected = float(np.dot(w, vals))

    assert out["central"][0] == pytest.approx(expected, rel=1e-9)
    assert "JUNK" not in out["models_used"]  # rejected model excluded


def test_weighted_ensemble_requires_kept_series():
    obs, models, names = _ensemble()
    eng = ModelTrustEngine(obs, models, names)
    with pytest.raises(ValueError, match="Missing series"):
        eng.weighted_ensemble({"GOOD": np.zeros(5)})  # drop other kept models


def test_all_junk_ensemble_gives_no_recommendation_weight():
    # Anti-correlated models (model gets the temporal pattern backwards) are
    # the genuine out-of-skill case -> all rejected, nothing to project from.
    rng = np.random.default_rng(7)
    obs = np.sort(rng.normal(285, 4, 60))
    junk = [obs[::-1] + rng.normal(0, 0.5, 60) for _ in range(3)]
    eng = ModelTrustEngine(obs, junk, ["J1", "J2", "J3"])
    s = eng.summary()
    assert s["n_kept"] == 0
    assert "out-of-skill" in s["recommendation"]
    with pytest.raises(ValueError, match="positive weight"):
        eng.weighted_ensemble({"J1": np.zeros(5), "J2": np.zeros(5), "J3": np.zeros(5)})
