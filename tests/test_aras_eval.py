"""
Regression tests for the Aras Diagram engine (src/climate/aras_eval.py).

These lock the implementation to the canonical definitions in the published
reference (ArasIzzaddin/Aras_diagram, Izzaddin et al. 2024):

    alpha (variability ratio) = sigma_model / sigma_obs        -> y-axis is alpha-1
    beta  (bias ratio)        = mu_model    / mu_obs           -> x-axis is beta-1
    r                         = Pearson correlation
    E_alpha_beta              = sqrt((beta-1)^2 + (alpha-1)^2)  (circle distance)
    E_total                   = sqrt((1-r)^2 + (beta-1)^2 + (alpha-1)^2)  (triangle distance)
    KGE                       = 1 - E_total

The engine stores alpha/beta already in the "-1" form, so res['alpha'] == alpha-1
and res['beta'] == beta-1 in the notation above.
"""

import math

import numpy as np
import pytest

from climate.aras_eval import ArasDiagram


def _canonical(ref, model):
    """Independent reference computation straight from the paper formulas."""
    ref = np.asarray(ref, dtype=float)
    model = np.asarray(model, dtype=float)
    alpha = model.std(ddof=0) / ref.std(ddof=0)        # variability ratio
    beta = model.mean() / ref.mean()                   # bias ratio
    r = np.corrcoef(ref, model)[0, 1]
    e_ab = math.sqrt((beta - 1) ** 2 + (alpha - 1) ** 2)
    e_total = math.sqrt((1 - r) ** 2 + (beta - 1) ** 2 + (alpha - 1) ** 2)
    kge = 1 - e_total
    return alpha, beta, r, e_ab, e_total, kge


def test_metrics_match_canonical_formulas():
    rng = np.random.default_rng(0)
    obs = rng.normal(285, 4, 80)                        # Kelvin-like
    model = obs * 1.03 + rng.normal(0.4, 0.6, 80)

    res = ArasDiagram(obs, [model], ["M"]).results[0]
    alpha, beta, r, e_ab, e_total, kge = _canonical(obs, model)

    assert res["alpha"] == pytest.approx(alpha - 1, rel=1e-9)
    assert res["beta"] == pytest.approx(beta - 1, rel=1e-9)
    assert res["r"] == pytest.approx(r, rel=1e-9)
    assert res["el"] == pytest.approx(e_ab, rel=1e-9)       # circle distance
    assert res["mkge"] == pytest.approx(e_total, rel=1e-9)  # triangle distance
    assert res["kge"] == pytest.approx(kge, rel=1e-9)
    assert res["e_pct"] == pytest.approx(e_total * 100, rel=1e-9)


def test_total_error_point_is_radial_and_outward():
    """The E_total triangle lies on the same ray as E_alpha_beta, farther out."""
    rng = np.random.default_rng(1)
    obs = rng.normal(290, 5, 60)
    model = obs * 0.95 + rng.normal(-0.5, 0.7, 60)

    res = ArasDiagram(obs, [model], ["M"]).results[0]
    bx, ay = res["beta"], res["alpha"]
    xE, yE = res["x_E"], res["y_E"]

    # distance of the triangle from origin == total error
    assert math.hypot(xE, yE) == pytest.approx(res["mkge"], rel=1e-9)
    # same direction as the circle point (collinear with origin)
    assert xE * ay - yE * bx == pytest.approx(0.0, abs=1e-9)
    # correlation error pushes it strictly outward (E_total >= E_alpha_beta)
    assert res["mkge"] >= res["el"] - 1e-12


def test_perfect_model_sits_at_origin():
    obs = np.linspace(280, 300, 50)
    res = ArasDiagram(obs, [obs.copy()], ["perfect"]).results[0]
    assert res["alpha"] == pytest.approx(0.0, abs=1e-9)
    assert res["beta"] == pytest.approx(0.0, abs=1e-9)
    assert res["r"] == pytest.approx(1.0, abs=1e-9)
    assert res["kge"] == pytest.approx(1.0, abs=1e-9)
    assert res["e_pct"] == pytest.approx(0.0, abs=1e-7)


def test_negative_correlation_is_preserved():
    obs = np.linspace(280, 300, 40)
    res = ArasDiagram(obs, [obs[::-1].copy()], ["mirror"]).results[0]
    assert res["r"] < 0


def test_zero_mean_reference_raises():
    """Bias ratio undefined (the Celsius / anomaly case) -> clear ValueError."""
    rng = np.random.default_rng(2)
    anom = rng.normal(0, 2, 50)
    anom = anom - anom.mean()                           # mean exactly ~0
    with pytest.raises(ValueError, match="bias ratio"):
        ArasDiagram(anom, [anom * 1.1 + 0.2], ["A"])


def test_constant_reference_raises():
    """Variability ratio undefined when the reference has no variance."""
    obs = np.full(40, 285.0)
    with pytest.raises(ValueError, match="variability ratio"):
        ArasDiagram(obs, [np.linspace(280, 290, 40)], ["C"])


def test_clean_kelvin_data_does_not_raise():
    rng = np.random.default_rng(3)
    obs = rng.normal(285, 4, 60)
    ArasDiagram(obs, [obs * 1.01 + 0.5], ["ok"])        # must not raise
