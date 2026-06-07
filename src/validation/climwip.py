"""
ClimWIP-style ensemble weighting (performance × independence) for comparison.

A faithful re-implementation of the Climate model Weighting by Independence and
Performance scheme (Knutti et al., 2017; Brunner et al., 2020), adapted to the
same in-memory series the Arasense trust engine uses, so the two schemes can be
compared on identical data (Paper 1, E3).

    performance:   w_perf_i  = exp( -(D_i / σ_D)² )           D_i = RMSE(model_i, obs)
    independence:  w_indep_i = 1 / ( 1 + Σ_{j≠i} exp(-(S_ij/σ_S)²) )   S_ij = RMSE(i, j)
    final:         w_i ∝ w_perf_i · w_indep_i

σ_D and σ_S are shape parameters; by default we use the median distance (a common
heuristic) — in a full study they are calibrated via a perfect-model test.

This is for methodological comparison, not a drop-in for the ESMValTool recipe.
"""

from __future__ import annotations

import numpy as np


def _rmse(a, b) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return float(np.sqrt(np.mean((a - b) ** 2)))


def climwip_weights(reference, models, model_names,
                    sigma_d: float | None = None, sigma_s: float | None = None) -> tuple[dict, dict]:
    """Return (weights_by_model, details). Weights sum to 1."""
    n = len(models)
    if n != len(model_names):
        raise ValueError("models and model_names length mismatch.")
    arrs = [np.asarray(m, dtype=float) for m in models]
    ref = np.asarray(reference, dtype=float)

    # performance distance to observations
    D = np.array([_rmse(ref, a) for a in arrs])
    # pairwise inter-model distances (independence)
    S = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            S[i, j] = S[j, i] = _rmse(arrs[i], arrs[j])

    if sigma_d is None:
        sigma_d = float(np.median(D)) or 1.0
    if sigma_s is None:
        off = S[np.triu_indices(n, 1)]
        sigma_s = (float(np.median(off)) if off.size else 1.0) or 1.0

    w_perf = np.exp(-((D / sigma_d) ** 2))
    w_indep = np.array([
        1.0 / (1.0 + np.sum([np.exp(-((S[i, j] / sigma_s) ** 2)) for j in range(n) if j != i]))
        for i in range(n)
    ])
    w = w_perf * w_indep
    w = w / w.sum() if w.sum() > 0 else np.full(n, 1.0 / n)

    weights = {model_names[i]: float(w[i]) for i in range(n)}
    details = {
        "sigma_d": float(sigma_d), "sigma_s": float(sigma_s),
        "performance_distance": {model_names[i]: float(D[i]) for i in range(n)},
        "performance_weight": {model_names[i]: float(w_perf[i]) for i in range(n)},
        "independence_weight": {model_names[i]: float(w_indep[i]) for i in range(n)},
    }
    return weights, details


def compare_weights(weights_a: dict, weights_b: dict) -> dict:
    """Compare two weight dicts (e.g. Aras vs ClimWIP) over their common models."""
    common = [k for k in weights_a if k in weights_b]
    if len(common) < 2:
        return {"n_common": len(common), "correlation": None, "top_model_agree": None}
    a = np.array([weights_a[k] for k in common])
    b = np.array([weights_b[k] for k in common])
    corr = float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else None
    top_a = max(common, key=lambda k: weights_a[k])
    top_b = max(common, key=lambda k: weights_b[k])
    return {
        "n_common": len(common),
        "correlation": corr,
        "top_model_a": top_a, "top_model_b": top_b,
        "top_model_agree": top_a == top_b,
        "l1_distance": float(np.sum(np.abs(a / a.sum() - b / b.sum()))),
    }


def weighted_value(weights: dict, values: dict) -> float:
    """Weighted mean of per-model ``values`` using ``weights`` (renormalised)."""
    common = [k for k in weights if k in values]
    w = np.array([weights[k] for k in common], dtype=float)
    v = np.array([float(values[k]) for k in common], dtype=float)
    if w.sum() <= 0:
        return float(np.mean(v)) if v.size else float("nan")
    return float(np.dot(w / w.sum(), v))


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    n = 120
    obs = rng.normal(0, 1, n)
    # two near-duplicate good models + one independent good model + one poor model
    models = [obs + rng.normal(0, 0.2, n), obs + rng.normal(0, 0.2, n),
              obs + rng.normal(0, 0.25, n) * -1 + 2 * obs, rng.normal(0, 1, n)]
    names = ["dupA", "dupB", "indep", "poor"]
    w, d = climwip_weights(obs, models, names)
    for k in names:
        print(f"{k:<7} weight {w[k]:.3f}  (perf {d['performance_weight'][k]:.2f}, "
              f"indep {d['independence_weight'][k]:.2f})")
