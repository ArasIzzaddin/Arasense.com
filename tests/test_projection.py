"""Tests for the trust-weighted climate projection engine."""

import numpy as np
import pytest

from climate.projection import METRICS, ClimateProjection, weighted_projection


def test_weighted_projection_from_precomputed_values():
    # Server-side path: per-model historical/future scalars already computed.
    per_model = [
        {"name": "A", "weight": 0.6, "trust_tier": "trusted", "historical": 10.0, "future": 13.0},
        {"name": "B", "weight": 0.4, "trust_tier": "usable", "historical": 20.0, "future": 22.0},
    ]
    out = weighted_projection(per_model, "rx1day", n_total=3)
    # weighted change = 0.6*3 + 0.4*2 = 2.6
    assert out["change"] == pytest.approx(2.6)
    assert out["n_models_trusted"] == 2
    assert out["n_models_total"] == 3
    assert out["agreement_on_increase"] == pytest.approx(1.0)
    assert out["per_model"][0]["change"] == pytest.approx(3.0)


def test_weighted_projection_empty_raises():
    with pytest.raises(ValueError, match="out-of-skill"):
        weighted_projection([], "mean", n_total=4)


def _ensemble(seed=0, n=120):
    rng = np.random.default_rng(seed)
    obs = np.abs(rng.normal(3, 2, n))
    hist = [
        obs * 1.03 + rng.normal(0, 0.3, n),   # trusted
        obs * 0.97 + rng.normal(0, 0.4, n),   # trusted
        obs * 1.10 + rng.normal(0, 0.5, n),   # trusted
        np.abs(rng.normal(3, 2, n)),          # uncorrelated junk
    ]
    names = ["A", "B", "C", "JUNK"]
    return obs, hist, names


def test_uniform_shift_recovered_regardless_of_weights():
    # If every trusted model warms by exactly +2, the weighted change is +2.
    obs, hist, names = _ensemble()
    future = [h + 2.0 for h in hist]
    out = ClimateProjection(obs, hist, future, names).project("mean")
    assert out["change"] == pytest.approx(2.0, abs=1e-9)
    assert out["change_spread"] == pytest.approx(0.0, abs=1e-9)
    assert out["agreement_on_increase"] == pytest.approx(1.0)


def test_junk_model_excluded_from_projection():
    obs, hist, names = _ensemble()
    future = [h * 1.2 for h in hist]
    out = ClimateProjection(obs, hist, future, names).project("mean")
    assert "JUNK" not in out["models_used"]
    assert out["n_models_trusted"] == 3
    assert out["n_models_total"] == 4
    assert sum(out["weights"]) == pytest.approx(1.0, abs=1e-9)


def test_weights_bias_change_toward_better_models():
    # Two trusted models with very different changes; the better-scoring model
    # should pull the weighted change toward its value.
    rng = np.random.default_rng(1)
    n = 150
    obs = np.abs(rng.normal(5, 1.5, n))
    good = obs + rng.normal(0, 0.2, n)          # near-perfect -> high weight
    okay = obs * 1.2 + rng.normal(0, 1.2, n)    # decent -> lower weight
    hist = [good, okay]
    future = [good + 1.0, okay + 5.0]           # good:+1, okay:+5
    out = ClimateProjection(obs, hist, future, ["GOOD", "OKAY"]).project("mean")
    # weighted change must lie between the two, closer to GOOD's +1
    assert 1.0 <= out["change"] <= 5.0
    assert abs(out["change"] - 1.0) < abs(out["change"] - 5.0)


def test_pct_change_and_levels():
    obs, hist, names = _ensemble()
    future = [h * 1.5 for h in hist]            # +50%
    out = ClimateProjection(obs, hist, future, names).project("mean")
    assert out["future_level"] > out["historical_level"]
    assert out["pct_change"] == pytest.approx(50.0, rel=0.05)


def test_metric_heavy_precip_frac():
    # Future doubles the number of heavy-rain days -> positive change in fraction.
    rng = np.random.default_rng(2)
    n = 200
    obs = np.abs(rng.normal(5, 4, n))
    hist = [obs + rng.normal(0, 0.3, n) for _ in range(3)]
    future = [np.where(rng.random(n) < 0.3, h + 25.0, h) for h in hist]  # inject heavy days
    out = ClimateProjection(obs, hist, future, ["A", "B", "C"]).project(
        "heavy_precip_frac", threshold_mm=20.0)
    assert out["change"] > 0
    assert 0.0 <= out["future_level"] <= 1.0


def test_temperature_extreme_metrics():
    # Kelvin daily temps ~22 C mean; future warms by +3 K.
    rng = np.random.default_rng(5)
    n = 250
    obs = rng.normal(295.0, 5.0, n)
    hist = [obs + rng.normal(0, 0.5, n) for _ in range(3)]
    future = [h + 3.0 for h in hist]
    proj = ClimateProjection(obs, hist, future, ["A", "B", "C"])

    tx = proj.project("tx_max")
    assert tx["change"] == pytest.approx(3.0, abs=0.5)        # max temp rises ~+3 K

    hot = proj.project("hot_day_frac")                        # threshold 303.15 K (30 C)
    assert 0.0 <= hot["future_level"] <= 1.0
    assert hot["change"] >= 0                                 # warming -> more hot days


def test_all_out_of_skill_refuses():
    rng = np.random.default_rng(3)
    n = 80
    obs = np.sort(np.abs(rng.normal(5, 1, n)))
    hist = [obs[::-1] + rng.normal(0, 0.2, n) for _ in range(2)]  # anti-correlated
    future = [h + 1 for h in hist]
    with pytest.raises(ValueError, match="out-of-skill"):
        ClimateProjection(obs, hist, future, ["X", "Y"]).project("mean")


def test_unknown_metric_raises():
    obs, hist, names = _ensemble()
    future = [h + 1 for h in hist]
    with pytest.raises(ValueError, match="Unknown metric"):
        ClimateProjection(obs, hist, future, names).project("nonsense")


def test_future_count_mismatch_raises():
    obs, hist, names = _ensemble()
    with pytest.raises(ValueError, match="one series per model"):
        ClimateProjection(obs, hist, future_models_missing := hist[:2], names)
