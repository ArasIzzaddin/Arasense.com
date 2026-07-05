"""Extreme-plausibility screen: models with physically impossible window
levels must be excluded before trust weighting, and reported.

Motivated by the Mexico City case (docs/mexico-city-rx1day-investigation.md):
NEX-GDDP-CMIP6 models with corrupted daily extremes survive mean-climate
trust screening because their monthly climatology still tracks observations.
"""

import pytest

from climate.projection import PLAUSIBILITY_RATIO, weighted_projection


def _model(name, hist, fut, weight=0.03):
    return {"name": name, "weight": weight, "trust_tier": "usable",
            "historical": hist, "future": fut}


SANE = [
    _model("CESM2", 38.8, 46.4),
    _model("MIROC6", 48.5, 53.5),
    _model("UKESM1-0-LL", 44.2, 44.6),
    _model("IPSL-CM6A-LR", 46.1, 44.0),
]
REF = 50.0


def test_corrupted_baseline_and_future_are_excluded_and_reported():
    corrupted = [
        _model("BCC-CSM2-MR", 1512.8, 163.8),   # impossible baseline
        _model("TaiESM1", 49.4, 621.9),          # impossible future window
    ]
    result = weighted_projection(SANE + corrupted, "rx1day", n_total=6,
                                 variable="precipitation",
                                 reference_historical_level=REF)
    screen = result["plausibility_screen"]
    assert screen["n_excluded"] == 2
    assert {m["name"] for m in screen["excluded_models"]} == {"BCC-CSM2-MR", "TaiESM1"}
    assert screen["reference_level"] == REF
    assert screen["ratio_bound"] == PLAUSIBILITY_RATIO
    assert set(result["models_used"]) == {m["name"] for m in SANE}
    assert result["n_models_trusted"] == 4
    # the corrupted models must not touch the aggregate
    assert result["historical_level"] < REF * 1.5


def test_implausibly_low_values_are_excluded_too():
    result = weighted_projection(SANE + [_model("BROKEN-LOW", 0.9, 1.1)],
                                 "rx1day", n_total=5,
                                 variable="precipitation",
                                 reference_historical_level=REF)
    assert result["plausibility_screen"]["n_excluded"] == 1
    assert "BROKEN-LOW" not in result["models_used"]


def test_no_reference_means_no_screen():
    corrupted = [_model("BCC-CSM2-MR", 1512.8, 163.8)]
    result = weighted_projection(SANE + corrupted, "rx1day", n_total=5,
                                 variable="precipitation",
                                 reference_historical_level=None)
    assert "plausibility_screen" not in result
    assert "BCC-CSM2-MR" in result["models_used"]


def test_screen_only_applies_to_precipitation_level_metrics():
    # Kelvin temperatures: ratios to a reference are meaningless, screen off
    hot = [_model("HOT", 300.0, 304.0), _model("HOTTER", 302.0, 306.0)]
    result = weighted_projection(hot, "tx_max", n_total=2,
                                 variable="temperature",
                                 reference_historical_level=55.0)
    assert "plausibility_screen" not in result
    # bounded fraction metrics: screen off as well
    frac = [_model("F1", 0.10, 0.12), _model("F2", 0.60, 0.62)]
    result = weighted_projection(frac, "dry_day_frac", n_total=2,
                                 variable="precipitation",
                                 reference_historical_level=0.5)
    assert "plausibility_screen" not in result


def test_all_models_implausible_refuses_to_project():
    corrupted = [_model("A", 1000.0, 900.0), _model("B", 800.0, 700.0)]
    with pytest.raises(ValueError, match="plausibility"):
        weighted_projection(corrupted, "rx1day", n_total=2,
                            variable="precipitation",
                            reference_historical_level=REF)


def test_clean_ensemble_is_untouched():
    result = weighted_projection(list(SANE), "rx1day", n_total=4,
                                 variable="precipitation",
                                 reference_historical_level=REF)
    assert "plausibility_screen" not in result
    assert result["n_models_trusted"] == 4
