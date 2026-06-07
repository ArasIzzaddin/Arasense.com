"""Tests for the ClimWIP-style weighting (comparison baseline)."""

import numpy as np
import pytest

from validation.climwip import climwip_weights, compare_weights, weighted_value


def test_weights_sum_to_one():
    rng = np.random.default_rng(0)
    obs = rng.normal(0, 1, 100)
    models = [obs + rng.normal(0, s, 100) for s in (0.2, 0.5, 1.0)]
    w, _ = climwip_weights(obs, models, ["a", "b", "c"])
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-9)


def test_better_performance_gets_more_weight():
    rng = np.random.default_rng(1)
    obs = rng.normal(0, 1, 200)
    good = obs + rng.normal(0, 0.1, 200)     # close to obs
    poor = obs + rng.normal(0, 1.5, 200)     # far from obs
    distinct = -obs + rng.normal(0, 0.1, 200)  # keep independence comparable-ish
    w, _ = climwip_weights(obs, [good, poor, distinct], ["good", "poor", "distinct"])
    assert w["good"] > w["poor"]


def test_independence_downweights_duplicates():
    rng = np.random.default_rng(2)
    obs = rng.normal(0, 1, 200)
    nx = rng.normal(0, 0.2, 200)
    ny = rng.normal(0, 0.2, 200)
    dupA = obs + nx
    dupB = obs + nx                          # identical to dupA
    indep = obs + ny                         # equally good, but distinct
    w, _ = climwip_weights(obs, [dupA, dupB, indep], ["dupA", "dupB", "indep"])
    assert w["dupA"] == pytest.approx(w["dupB"], abs=1e-9)   # identical -> equal
    assert w["indep"] > w["dupA"]                            # distinct -> more weight


def test_compare_and_weighted_value():
    a = {"m1": 0.5, "m2": 0.3, "m3": 0.2}
    b = {"m1": 0.2, "m2": 0.3, "m3": 0.5}
    cmp = compare_weights(a, b)
    assert cmp["n_common"] == 3
    assert cmp["top_model_a"] == "m1" and cmp["top_model_b"] == "m3"
    assert cmp["top_model_agree"] is False
    # weighted_value: renormalises over common keys
    assert weighted_value({"m1": 0.5, "m2": 0.5}, {"m1": 10.0, "m2": 20.0}) == pytest.approx(15.0)
