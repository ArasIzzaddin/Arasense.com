"""
Distill the full Bologna diagnostic run into the published diagram file.

Reads bologna_diag_full.json (output of POST /api/climate/diagnostic for
Bologna, 34 models, 1995-2014, ERA5-Land reference) and joins each model's
Aras Diagram coordinates with its projection trust weight from the deep-dive
file. Writes site/data/bologna-aras-diagram.json — the raw evidence behind
the case-study diagram. Rejection rule mirrors the engine: KGE <= -0.41
(Knoben et al. 2019).

    python scripts/distill_aras_diagram.py
"""

import json

DIAG = "bologna_diag_full.json"
DEEP = "docs/projections/bologna-flood-driving-rainfall-mid-century.json"
OUT = "site/data/bologna-aras-diagram.json"
KGE_FLOOR = -0.41


def main() -> None:
    diag = json.load(open(DIAG, encoding="utf-8"))
    deep = json.load(open(DEEP, encoding="utf-8"))

    weights = {m["name"]: m for m in deep.get("per_model", [])}

    models = []
    for m in diag["metrics"]:
        rej = m["kge"] <= KGE_FLOOR
        w = weights.get(m["name"], {})
        models.append({
            "n": m["name"],
            "b": round(m["beta"], 4),
            "a": round(m["alpha"], 4),
            "xe": round(m["x_E"], 4),
            "ye": round(m["y_E"], 4),
            "r": round(m["correlation"], 4),
            "kge": round(m["kge"], 4),
            "e": round(m["error_total_pct"], 1),
            "w": round(w.get("weight", 0.0), 5),
            "tier": w.get("trust_tier", "rejected" if rej else "unweighted"),
            "rej": rej,
        })

    models.sort(key=lambda x: x["kge"], reverse=True)
    n_rej = sum(1 for m in models if m["rej"])

    out = {
        "case": "Bologna — Aras Diagram of the full CMIP6 screening",
        "notes": "Each model's bias (beta-1), variability (alpha-1) and "
                 "correlation error against observed ERA5-Land climate, "
                 "1995-2014, 50 km radius. Same run family as the deep-dive "
                 "projection; rejection rule KGE <= -0.41.",
        "region": {"lat": 44.494, "lon": 11.343, "radius_km": 50},
        "reference": "ERA5-Land",
        "window": ["1995-01-01", "2014-12-31"],
        "n_models": len(models),
        "n_rejected": n_rej,
        "models": models,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
    print(f"{OUT}: {len(models)} models, {n_rej} rejected")
    for m in models[-4:]:
        print(f"  tail: {m['n']} KGE {m['kge']} rej={m['rej']}")


if __name__ == "__main__":
    main()
