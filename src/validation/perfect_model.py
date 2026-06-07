"""
Perfect-model (model-as-truth) validation for the trust-weighting scheme.

The standard test reviewers ask of any performance-weighting method: does weighting
models by *historical* skill actually improve the *future* projection, versus an
equal-weight ensemble?

Procedure (leave-one-out):
    For each model treated as "truth":
        • score the OTHER models against that model's historical series with the
          Model Trust Engine (the same scoring used in production),
        • predict the truth model's future value as the skill-weighted mean of the
          others' future values, and also as their equal-weight mean,
        • record the error of each against the held-out truth.
    Aggregate across all truth models. If weighting helps, its RMSE is lower.

Pure/offline: takes in-memory arrays so it is unit-tested without Earth Engine.
"""

from __future__ import annotations

import numpy as np

from climate.trust_engine import ModelTrustEngine


def perfect_model_test(hist_by_model: dict, future_by_model: dict,
                       sharpness: float = 1.0) -> dict:
    """
    Parameters
    ----------
    hist_by_model : dict[str, 1-D array]
        Each model's historical series (used to score trust). All same length.
    future_by_model : dict[str, float]
        Each model's future quantity to predict (e.g. a projected hazard metric).
    sharpness : float
        Skill-weight sharpness passed to the Model Trust Engine.
    """
    names = [n for n in hist_by_model if n in future_by_model]
    if len(names) < 3:
        raise ValueError("Perfect-model test needs at least 3 models.")

    per_truth = []
    for truth in names:
        others = [n for n in names if n != truth]
        ref = np.asarray(hist_by_model[truth], dtype=float)
        engine = ModelTrustEngine(ref, [np.asarray(hist_by_model[n], dtype=float) for n in others],
                                  others, sharpness=sharpness)
        weight = {r["name"]: r["weight"] for r in engine.reports}
        fut = {n: float(future_by_model[n]) for n in others}

        kept = [n for n in others if weight[n] > 0]
        if kept:
            wsum = sum(weight[n] for n in kept)
            pred_w = sum(weight[n] * fut[n] for n in kept) / wsum
        else:                                   # no model trusted -> fall back to equal
            pred_w = float(np.mean([fut[n] for n in others]))
        pred_e = float(np.mean([fut[n] for n in others]))
        truth_f = float(future_by_model[truth])

        per_truth.append({
            "truth": truth, "truth_future": truth_f,
            "pred_weighted": pred_w, "pred_equal": pred_e,
            "err_weighted": abs(pred_w - truth_f), "err_equal": abs(pred_e - truth_f),
            "n_kept": len(kept),
        })

    ew = np.array([p["err_weighted"] for p in per_truth])
    ee = np.array([p["err_equal"] for p in per_truth])
    rmse_w = float(np.sqrt(np.mean(ew ** 2)))
    rmse_e = float(np.sqrt(np.mean(ee ** 2)))
    return {
        "n_models": len(names),
        "rmse_weighted": rmse_w,
        "rmse_equal": rmse_e,
        "mae_weighted": float(np.mean(ew)),
        "mae_equal": float(np.mean(ee)),
        "rmse_improvement_pct": ((rmse_e - rmse_w) / rmse_e * 100.0) if rmse_e > 0 else 0.0,
        "n_truth_weighting_better": int(np.sum(ew < ee)),
        "per_truth": per_truth,
    }


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    n = 120
    signal = rng.normal(0, 1, n)
    hist, future = {}, {}
    for i in range(6):                          # skilful cluster: track +signal, future ~5
        hist[f"G{i}"] = signal + rng.normal(0, 0.3, n)
        future[f"G{i}"] = 5.0 + rng.normal(0, 0.2)
    for i in range(3):                          # outliers: anti-correlated, future ~12
        hist[f"B{i}"] = -signal + rng.normal(0, 0.3, n)
        future[f"B{i}"] = 12.0 + rng.normal(0, 1)
    res = perfect_model_test(hist, future)
    print(f"RMSE  weighted {res['rmse_weighted']:.2f}  vs equal {res['rmse_equal']:.2f}  "
          f"-> improvement {res['rmse_improvement_pct']:+.0f}%")
    print(f"weighting better for {res['n_truth_weighting_better']}/{res['n_models']} truth models")
