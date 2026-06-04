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

The result is a defensible "Step 2 hazard layer" output: a projected change with
an honest spread, traceable to which models were trusted and why.
"""

from __future__ import annotations

import numpy as np

from climate.trust_engine import ModelTrustEngine


# ── hazard metrics (intensive: independent of window length) ──────────
def _mean(x):
    return float(np.mean(x))


def _p95(x):
    return float(np.percentile(x, 95))


def _heavy_precip_frac(x, threshold_mm: float = 20.0):
    # fraction of days at/above a heavy-rain threshold (mm/day)
    x = np.asarray(x, dtype=float)
    return float(np.mean(x >= threshold_mm)) if x.size else 0.0


METRICS = {
    "mean":              _mean,              # mean level (mm/day, or K)
    "p95":               _p95,               # 95th percentile (extreme intensity)
    "heavy_precip_frac": _heavy_precip_frac, # fraction of heavy-rain days
}


class ClimateProjection:
    """
    Trust-weighted projection of a hazard metric from a historical to a future
    window, for one location/variable.

    Parameters
    ----------
    reference_hist : 1-D array-like
        Observed historical series (e.g. ERA5-Land) used to score model trust.
    models_hist : list of 1-D array-like
        Each model's historical series, aligned to ``reference_hist``.
    models_future : list of 1-D array-like
        Each model's future-scenario series (same model order; lengths may differ
        from the historical window — metrics are intensive).
    model_names : list of str
    sharpness : float
        Skill-weight sharpness passed to the Model Trust Engine.
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
        """
        Project the change in ``metric`` from historical to future, weighted by
        model trust. Returns the absolute future level, the change, an
        across-model uncertainty band, and the per-model contributions.
        """
        if metric not in METRICS:
            raise ValueError(f"Unknown metric '{metric}'. Options: {sorted(METRICS)}")
        fn = METRICS[metric]

        kept = [r for r in self.engine.reports if r["weight"] > 0]
        if not kept:
            raise ValueError(
                "No model is trustworthy here (all KGE <= -0.41); refusing to "
                "project from an out-of-skill ensemble."
            )

        names = [r["name"] for r in kept]
        weights = np.array([r["weight"] for r in kept], dtype=float)
        weights = weights / weights.sum()  # renormalise over kept models

        per_model = []
        hist_vals, fut_vals, deltas = [], [], []
        for r in kept:
            h = fn(self.hist[r["name"]], **metric_kwargs)
            f = fn(self.future[r["name"]], **metric_kwargs)
            hist_vals.append(h)
            fut_vals.append(f)
            deltas.append(f - h)
            per_model.append({
                "name": r["name"], "weight": r["weight"], "trust_tier": r["trust_tier"],
                "historical": h, "future": f, "change": f - h,
            })

        hist_vals = np.array(hist_vals)
        fut_vals = np.array(fut_vals)
        deltas = np.array(deltas)

        change = float(np.average(deltas, weights=weights))
        change_spread = float(np.sqrt(np.average((deltas - change) ** 2, weights=weights)))
        future_level = float(np.average(fut_vals, weights=weights))
        hist_level = float(np.average(hist_vals, weights=weights))
        pct_change = (change / hist_level * 100.0) if abs(hist_level) > 1e-12 else None

        # Agreement on the sign of change — a simple, communicable confidence cue.
        share_increase = float(np.average((deltas > 0).astype(float), weights=weights))

        return {
            "metric": metric,
            "n_models_trusted": len(kept),
            "n_models_total": len(self.engine.reports),
            "models_used": names,
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
            "trust_summary": self.engine.summary(),
        }


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    n = 120
    obs = np.abs(rng.normal(3, 2, n))                       # historical obs precip (mm/day)
    # 3 good models track the obs; 1 junk is uncorrelated
    hist = [obs * 1.05 + rng.normal(0, 0.3, n),
            obs * 0.95 + rng.normal(0, 0.4, n),
            obs * 1.10 + rng.normal(0, 0.5, n),
            np.abs(rng.normal(3, 2, n))]
    # futures: the 3 good models wetten by ~15-25%, junk does its own thing
    future = [h * 1.2 for h in hist[:3]] + [np.abs(rng.normal(3, 2, n))]
    names = ["EC-Earth3", "MPI-ESM1-2-HR", "MRI-ESM2-0", "JUNK"]

    proj = ClimateProjection(obs, hist, future, names).project("mean")
    print(f"Trusted {proj['n_models_trusted']}/{proj['n_models_total']} models: {proj['models_used']}")
    print(f"Historical {proj['historical_level']:.2f} -> future {proj['future_level']:.2f} mm/day")
    print(f"Change {proj['change']:+.2f} ± {proj['change_spread']:.2f} mm/day "
          f"({proj['pct_change']:+.0f}%), {proj['agreement_on_increase']*100:.0f}% of weight agrees on increase")
