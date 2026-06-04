"""
Arasense Model Trust Engine
===========================

Turns the Aras Diagram error decomposition (Izzaddin et al., 2024) into a
decision layer: for a given location and variable it answers

    "Which climate models should I trust here, why, and how much weight
     should each get when I project local risk?"

It consumes :class:`climate.aras_eval.ArasDiagram` results and produces, per model:

    • a trust tier         (trusted / usable / weak / reject)
    • an error attribution (how much of the total error is bias vs.
                            variability vs. phase) and the dominant mode
    • a skill weight       (>= 0, normalised across kept models)

and an ensemble-level summary plus a skill-weighted projection helper.

Design choices grounded in hydrology:
    • KGE is the headline skill score (Gupta et al., 2009).
    • The reject threshold is KGE = -0.41, the "mean-flow benchmark" of
      Knoben, Freer & Woods (2019): a model below it does not even beat
      predicting the observed mean, so it earns zero weight.
"""

from __future__ import annotations

import numpy as np

from climate.aras_eval import ArasDiagram

# KGE of the mean benchmark (Knoben et al., 2019). Below this a model is useless.
KGE_BENCHMARK = -0.41

# (tier name, inclusive KGE lower bound) in descending order.
TRUST_TIERS = (
    ("trusted", 0.75),
    ("usable", 0.50),
    ("weak", KGE_BENCHMARK),
    ("reject", float("-inf")),
)

_ERROR_MODE_LABEL = {
    "bias": "systematic mean offset (β)",
    "variability": "variability / amplitude mismatch (α)",
    "phase": "timing / correlation mismatch (r)",
}


def _classify(kge: float, r: float) -> str:
    """Map a KGE (and correlation sign) to a trust tier."""
    if r < 0:
        # Anti-correlated: the model gets the temporal pattern backwards.
        return "reject"
    for name, lower in TRUST_TIERS:
        if kge >= lower:
            return name
    return "reject"


def _error_attribution(res: dict) -> dict:
    """
    Split the total squared error into its three Aras components and report
    the dominant one. Uses res['beta']=β-1, res['alpha']=α-1, res['r']=r,
    so E_total² = (β-1)² + (α-1)² + (1-r)².
    """
    bias = res["beta"] ** 2
    variability = res["alpha"] ** 2
    phase = (1.0 - res["r"]) ** 2
    total = bias + variability + phase
    if total <= 1e-15:
        # Perfect model — no error to attribute.
        return {
            "bias": 0.0,
            "variability": 0.0,
            "phase": 0.0,
            "dominant": "none",
            "dominant_label": "no significant error",
        }
    fractions = {
        "bias": bias / total,
        "variability": variability / total,
        "phase": phase / total,
    }
    dominant = max(fractions, key=fractions.get)
    return {
        **fractions,
        "dominant": dominant,
        "dominant_label": _ERROR_MODE_LABEL[dominant],
    }


class ModelTrustEngine:
    """
    Score and weight a CMIP6 (or any) model ensemble against a reference.

    Parameters
    ----------
    reference_data : 1-D array-like
        Observed/reference series (e.g. ERA5-Land), in absolute units
        (Kelvin for temperature — see ArasDiagram guards).
    model_data : list of 1-D array-like
        Aligned model series, one per model.
    model_names : list of str, optional
    sharpness : float, default 1.0
        Exponent applied to skill before normalising weights. >1 concentrates
        weight on the best models; 1.0 is linear in skill above the benchmark.
    """

    def __init__(self, reference_data=None, model_data=None, model_names=None,
                 sharpness: float = 1.0, aras: ArasDiagram | None = None):
        if aras is None:
            if reference_data is None or model_data is None:
                raise ValueError(
                    "Provide either an existing `aras` ArasDiagram or "
                    "reference_data + model_data."
                )
            aras = ArasDiagram(reference_data, model_data, model_names)
        self.aras = aras
        self.sharpness = float(sharpness)
        self.reports = self._build_reports()

    # ── per-model scoring ────────────────────────────────────────────
    def _build_reports(self) -> list[dict]:
        reports = []
        for res in self.aras.results:
            tier = _classify(res["kge"], res["r"])
            attribution = _error_attribution(res)
            # Raw skill above the mean benchmark; rejected models contribute 0.
            skill = max(0.0, res["kge"] - KGE_BENCHMARK) if tier != "reject" else 0.0
            reports.append(
                {
                    "name": res["name"],
                    "kge": res["kge"],
                    "correlation": res["r"],
                    "bias_ratio_minus_1": res["beta"],
                    "variability_ratio_minus_1": res["alpha"],
                    "error_total_pct": res["e_pct"],
                    "trust_tier": tier,
                    "error_attribution": attribution,
                    "skill": skill,
                    "weight": 0.0,  # filled in below after normalisation
                }
            )

        total_skill = sum(rep["skill"] ** self.sharpness for rep in reports)
        for rep in reports:
            rep["weight"] = (
                (rep["skill"] ** self.sharpness) / total_skill if total_skill > 0 else 0.0
            )
        return reports

    # ── ensemble-level summary ───────────────────────────────────────
    def summary(self) -> dict:
        tiers = [rep["trust_tier"] for rep in self.reports]
        kept = [rep for rep in self.reports if rep["weight"] > 0]
        weights = np.array([rep["weight"] for rep in kept])
        # Effective ensemble size (inverse participation ratio of the weights):
        # 1 means one model dominates, len(kept) means perfectly even weighting.
        eff_n = float(1.0 / np.sum(weights**2)) if weights.size else 0.0
        ranked = sorted(self.reports, key=lambda r: r["kge"], reverse=True)
        return {
            "n_models": len(self.reports),
            "tier_counts": {name: tiers.count(name) for name, _ in TRUST_TIERS},
            "n_trusted_or_usable": sum(t in ("trusted", "usable") for t in tiers),
            "n_kept": len(kept),
            "effective_ensemble_size": eff_n,
            "best_model": ranked[0]["name"] if ranked else None,
            "best_kge": ranked[0]["kge"] if ranked else None,
            "recommendation": self._recommendation(kept, ranked),
        }

    @staticmethod
    def _recommendation(kept: list[dict], ranked: list[dict]) -> str:
        if not kept:
            return (
                "No model beats the mean benchmark here (KGE > -0.41). Do not project "
                "from this ensemble; treat the location as out-of-skill."
            )
        best = ranked[0]
        mode = best["error_attribution"]["dominant_label"]
        return (
            f"Project from the {len(kept)} skill-weighted model(s). Best model "
            f"'{best['name']}' (total Aras error {best['error_total_pct']:.0f}%); its residual "
            f"error is dominated by {mode}, which is the priority target for bias correction."
        )

    # ── skill-weighted projection ────────────────────────────────────
    def weighted_ensemble(self, series_by_model: dict) -> dict:
        """
        Apply the trust weights to a set of aligned model series (e.g. future
        projections) and return a skill-weighted central estimate plus a
        spread band. Rejected models contribute nothing.

        Parameters
        ----------
        series_by_model : dict[str, 1-D array-like]
            Must contain at least every kept (weight > 0) model and all arrays
            must share the same length.
        """
        kept = [rep for rep in self.reports if rep["weight"] > 0]
        if not kept:
            raise ValueError("No model has positive weight; cannot form a trusted ensemble.")

        missing = [rep["name"] for rep in kept if rep["name"] not in series_by_model]
        if missing:
            raise ValueError(f"Missing series for kept models: {missing}")

        names = [rep["name"] for rep in kept]
        weights = np.array([rep["weight"] for rep in kept])
        weights = weights / weights.sum()  # renormalise over the provided subset

        stacked = np.vstack([np.asarray(series_by_model[n], dtype=float) for n in names])
        if stacked.shape[1] == 0:
            raise ValueError("Model series are empty.")

        central = np.average(stacked, axis=0, weights=weights)
        variance = np.average((stacked - central) ** 2, axis=0, weights=weights)
        spread = np.sqrt(variance)
        return {
            "models_used": names,
            "weights": weights.tolist(),
            "central": central.tolist(),
            "lower": (central - spread).tolist(),
            "upper": (central + spread).tolist(),
        }


if __name__ == "__main__":
    rng = np.random.default_rng(42)
    n = 60
    obs = rng.normal(285, 4, n)  # Kelvin
    models = [
        obs * 1.01 + rng.normal(0.2, 0.4, n),   # excellent
        obs * 1.10 + rng.normal(0.5, 0.6, n),   # warm bias
        obs * 1.00 + rng.normal(0.0, 2.5, n),   # right mean, noisy phase
        rng.normal(285, 4, n),                  # uncorrelated junk
    ]
    names = ["GOOD", "WARM-BIAS", "NOISY", "JUNK"]

    eng = ModelTrustEngine(obs, models, names)
    for rep in sorted(eng.reports, key=lambda r: r["kge"], reverse=True):
        a = rep["error_attribution"]
        print(f"{rep['name']:<10} tier={rep['trust_tier']:<8} "
              f"KGE={rep['kge']:+.2f} weight={rep['weight']:.2f} "
              f"dominant={a['dominant']}")
    print("\nSUMMARY:", eng.summary()["recommendation"])
