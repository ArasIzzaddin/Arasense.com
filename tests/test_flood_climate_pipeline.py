"""
Tests for the trust-driven FloodClimatePipeline (src/flood/climate_pipeline.py).

The Earth Engine fetcher is mocked, so these run offline and lock in the
behaviour that the flood signal is a skill-weighted ensemble of *trusted*
precipitation models (rejected models contribute nothing).
"""

from unittest import mock

import numpy as np
import pandas as pd
import pytest

from flood.climate_pipeline import FloodClimatePipeline


def _fake_results(n=60, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2014-05-01", periods=n, freq="D")
    ref = pd.Series(np.linspace(1.0, 10.0, n) + rng.normal(0, 0.3, n), index=idx)

    defs = {
        "GOOD": ref * 1.02 + rng.normal(0, 0.2, n),   # trusted
        "WET-BIAS": ref * 1.30 + rng.normal(0, 0.3, n),  # usable, wet bias
        "JUNK": ref.values[::-1] + rng.normal(0, 0.2, n),  # anti-correlated -> reject
    }
    out = {"reference": ref}
    for name, vals in defs.items():
        df = pd.concat([ref, pd.Series(np.asarray(vals), index=idx)], axis=1)
        df.columns = ["reference", "model"]
        out[name] = df
    return out


def _run_pipeline(results):
    with mock.patch("flood.climate_pipeline.ArasenseDataFetcher") as F:
        F.return_value.get_climate_data.return_value = results
        pipe = FloodClimatePipeline("proj")
        return pipe.get_trusted_precipitation(geometry=None,
                                              start_date="2014-05-01",
                                              end_date="2014-06-29")


def test_rejected_model_excluded_from_ensemble():
    out = _run_pipeline(_fake_results())
    assert "JUNK" not in out["models_used"]
    assert set(out["models_used"]) == {"GOOD", "WET-BIAS"}
    assert out["trust_summary"]["n_kept"] == 2
    assert sum(out["weights"]) == pytest.approx(1.0, abs=1e-9)


def test_ensemble_precip_mean_within_kept_model_range():
    results = _fake_results()
    out = _run_pipeline(results)
    good_mean = float(results["GOOD"]["model"].mean())
    wet_mean = float(results["WET-BIAS"]["model"].mean())
    # weighted blend must sit between the two kept models' means
    assert min(good_mean, wet_mean) <= out["precip_mean"] <= max(good_mean, wet_mean)
    # the better model (GOOD) carries more weight, so the blend leans toward it
    assert abs(out["precip_mean"] - good_mean) < abs(out["precip_mean"] - wet_mean)


def test_spread_and_anomaly_present():
    out = _run_pipeline(_fake_results())
    assert out["precip_spread"] >= 0.0
    assert "precip_anomaly" in out
    assert np.isfinite(out["precip_anomaly"])
    assert isinstance(out["model_series"], pd.Series)
    assert len(out["model_series"]) > 0


def test_all_metrics_carry_trust_fields():
    out = _run_pipeline(_fake_results())
    for m in out["all_metrics"]:
        assert "trust_tier" in m and "weight" in m
        assert "x_E" in m and "y_E" in m  # back-compat geometry preserved
    junk = next(m for m in out["all_metrics"] if m["name"] == "JUNK")
    assert junk["trust_tier"] == "reject"
    assert junk["weight"] == 0.0


def test_backcompat_alias_delegates():
    results = _fake_results()
    with mock.patch("flood.climate_pipeline.ArasenseDataFetcher") as F:
        F.return_value.get_climate_data.return_value = results
        pipe = FloodClimatePipeline("proj")
        a = pipe.get_best_model_precipitation(geometry=None,
                                              start_date="2014-05-01",
                                              end_date="2014-06-29")
    assert a["models_used"] == ["GOOD", "WET-BIAS"] or set(a["models_used"]) == {"GOOD", "WET-BIAS"}
    assert "trust_summary" in a


def test_all_out_of_skill_refuses():
    rng = np.random.default_rng(1)
    n = 40
    idx = pd.date_range("2014-05-01", periods=n, freq="D")
    ref = pd.Series(np.sort(rng.normal(5, 1, n)), index=idx)
    results = {"reference": ref}
    for k in ("A", "B"):
        df = pd.concat([ref, pd.Series(ref.values[::-1], index=idx)], axis=1)  # anti-correlated
        df.columns = ["reference", "model"]
        results[k] = df
    with pytest.raises(RuntimeError, match="out-of-skill"):
        _run_pipeline(results)
