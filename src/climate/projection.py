"""
Arasense forward-looking climate projection.

This is the money/impact core of the trust layer: for a location and a
hazard-relevant variable, it answers

    "How will this hazard change by <future period>, using only the climate
     models that earned trust here, and how confident can I be?"

It is the scientifically correct use of the Aras Diagram / Model Trust Engine.
Unlike a single flood event (where free-running models have no timing skill),
*climatological* statistics are where CMIP6 models genuinely have skill — so we:

    1. Score each model against an observed historical CLIMATOLOGY (trust engine).
    2. Keep only trusted models (KGE > -0.41), weighted by skill.
    3. Compute each kept model's change in a hazard metric from its historical to
       its future window, then form a SKILL-WEIGHTED projected change with an
       across-model uncertainty band.

The weighting/aggregation (``weighted_projection``) is shared by two paths:
metrics computed client-side from in-memory series (``ClimateProjection``), and
extreme metrics computed server-side from daily data (the projection endpoint).
"""

from __future__ import annotations

import numpy as np

from climate.trust_engine import ModelTrustEngine


# ── hazard metrics (intensive: independent of window length) ──────────
def _mean(x):
    return float(np.mean(x))


def _p95(x):
    return float(np.percentile(x, 95))


def _rx1day(x):
    return float(np.max(x))


def _heavy_precip_frac(x, threshold_mm: float = 20.0):
    # fraction of days at/above a heavy-rain threshold (mm/day)
    x = np.asarray(x, dtype=float)
    return float(np.mean(x >= threshold_mm)) if x.size else 0.0


def _hot_day_frac(x, threshold_k: float = 303.15):
    # fraction of days at/above a hot-day threshold (default 30 C, in Kelvin)
    x = np.asarray(x, dtype=float)
    return float(np.mean(x >= threshold_k)) if x.size else 0.0


def _dry_day_frac(x, threshold_mm: float = 1.0):
    # fraction of dry days (precip below ~1 mm)
    x = np.asarray(x, dtype=float)
    return float(np.mean(x < threshold_mm)) if x.size else 0.0


def _cdd(x, threshold_mm: float = 1.0):
    # maximum run of consecutive dry days (standard drought index, ETCCDI CDD)
    best = cur = 0
    for v in np.asarray(x, dtype=float):
        cur = cur + 1 if v < threshold_mm else 0
        best = max(best, cur)
    return float(best)


METRICS = {
    "mean":              _mean,              # mean level (mm/day, or K)
    "p95":               _p95,               # 95th percentile (extreme intensity)
    "rx1day":            _rx1day,            # max 1-day precipitation
    "heavy_precip_frac": _heavy_precip_frac, # fraction of heavy-rain days
    "tx_max":            _rx1day,            # max daily temperature over the window
    "hot_day_frac":      _hot_day_frac,      # fraction of hot days (Tmax >= 30 C)
    "dry_day_frac":      _dry_day_frac,      # fraction of dry days (drought)
    "cdd":               _cdd,               # max consecutive dry days (drought)
}


def weighted_projection(per_model: list[dict], metric: str, n_total: int,
                        trust_summary: dict | None = None) -> dict:
    """
    Aggregate per-model (historical, future) hazard-metric values into a
    skill-weighted projected change with an uncertainty band.

    Parameters
    ----------
    per_model : list of dicts, each with keys name, weight, trust_tier,
        historical, future. ``weight`` is the raw trust weight (renormalised here).
    metric : str
    n_total : int — number of models scored (trusted + rejected).
    trust_summary : dict, optional
    """
    if not per_model:
        raise ValueError(
            "No model is trustworthy here (all KGE <= -0.41); refusing to "
            "project from an out-of-skill ensemble."
        )

    weights = np.array([m["weight"] for m in per_model], dtype=float)
    weights = weights / weights.sum()
    hist = np.array([float(m["historical"]) for m in per_model])
    fut = np.array([float(m["future"]) for m in per_model])
    deltas = fut - hist
    for m, d in zip(per_model, deltas):
        m["change"] = float(d)

    change = float(np.average(deltas, weights=weights))
    change_spread = float(np.sqrt(np.average((deltas - change) ** 2, weights=weights)))
    future_level = float(np.average(fut, weights=weights))
    hist_level = float(np.average(hist, weights=weights))
    pct_change = (change / hist_level * 100.0) if abs(hist_level) > 1e-12 else None
    share_increase = float(np.average((deltas > 0).astype(float), weights=weights))

    return {
        "metric": metric,
        "n_models_trusted": len(per_model),
        "n_models_total": n_total,
        "models_used": [m["name"] for m in per_model],
        "weights": weights.tolist(),
        "historical_level": hist_level,
        "future_level": future_level,
        "change": change,
        "change_spread": change_spread,
        "change_low": change - change_spread,
        "change_high": change + change_spread,
        "pct_change": pct_change,
        "agreement_on_increase": share_increase,
        "per_model": per_model,
        "trust_summary": trust_summary,
    }


class ClimateProjection:
    """
    Trust-weighted projection of a hazard metric from a historical to a future
    window, for one location/variable, with metrics computed from in-memory
    series. (The API uses ``weighted_projection`` directly for server-side
    daily-extreme metrics.)

    Parameters
    ----------
    reference_hist : 1-D array-like
        Observed historical series (e.g. ERA5-Land) used to score model trust.
    models_hist : list of 1-D array-like
        Each model's historical series, aligned to ``reference_hist``.
    models_future : list of 1-D array-like
        Each model's future-scenario series (same model order; lengths may differ).
    model_names : list of str
    sharpness : float
    """

    def __init__(self, reference_hist, models_hist, models_future,
                 model_names=None, sharpness: float = 1.0):
        self.engine = ModelTrustEngine(reference_hist, models_hist, model_names,
                                       sharpness=sharpness)
        names = self.engine.aras.model_names
        if len(models_future) != len(names):
            raise ValueError("models_future must have one series per model.")
        self.hist = dict(zip(names, [np.asarray(m, dtype=float) for m in self.engine.aras.models]))
        self.future = dict(zip(names, [np.asarray(m, dtype=float) for m in models_future]))

    def project(self, metric: str = "mean", **metric_kwargs) -> dict:
        """Project the trust-weighted change in ``metric`` (historical → future)."""
        if metric not in METRICS:
            raise ValueError(f"Unknown metric '{metric}'. Options: {sorted(METRICS)}")
        fn = METRICS[metric]

        per_model = [
            {
                "name": r["name"], "weight": r["weight"], "trust_tier": r["trust_tier"],
                "historical": fn(self.hist[r["name"]], **metric_kwargs),
                "future": fn(self.future[r["name"]], **metric_kwargs),
            }
            for r in self.engine.reports if r["weight"] > 0
        ]
        return weighted_projection(per_model, metric, len(self.engine.reports),
                                   self.engine.summary())


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    n = 120
    obs = np.abs(rng.normal(3, 2, n))
    hist = [obs * 1.05 + rng.normal(0, 0.3, n),
            obs * 0.95 + rng.normal(0, 0.4, n),
            obs * 1.10 + rng.normal(0, 0.5, n),
            np.abs(rng.normal(3, 2, n))]
    future = [h * 1.2 for h in hist[:3]] + [np.abs(rng.normal(3, 2, n))]
    names = ["EC-Earth3", "MPI-ESM1-2-HR", "MRI-ESM2-0", "JUNK"]

    proj = ClimateProjection(obs, hist, future, names).project("mean")
    print(f"Trusted {proj['n_models_trusted']}/{proj['n_models_total']}: {proj['models_used']}")
    print(f"Change {proj['change']:+.2f} ± {proj['change_spread']:.2f} ({proj['pct_change']:+.0f}%)")
