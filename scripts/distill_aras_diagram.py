"""
Distill the Bologna screening run into the published diagram file.

Reads bologna_diag_full.json (scripts/run_bologna_diagnostic.py: the same
monthly-climatology trust screening the published rx1day projection used)
and writes site/data/bologna-aras-diagram.json.

The 32 trusted weights reproduce the published deep dive exactly. Of the two
models the published run rejected, EC-Earth3-Veg-LR is rejected again
(negative correlation); HadGEM3-GC31-MM now sits marginally above the floor
(r = +0.11) because the upstream archive has updated since the original run.
It is flagged as borderline rather than silently promoted.

    python scripts/distill_aras_diagram.py
"""

import json

DIAG = "bologna_diag_full.json"
OUT = "site/data/bologna-aras-diagram.json"

BORDERLINE = {
    "HadGEM3-GC31-MM": "rejected in the original published run; in this "
                       "re-run it sits just above the floor (r = +0.11). "
                       "Borderline models can flip as the archive updates — "
                       "which is why the floor is published.",
}


def main() -> None:
    diag = json.load(open(DIAG, encoding="utf-8"))

    models = []
    for m in diag["metrics"]:
        rej = m["weight"] <= 0
        row = {
            "n": m["name"],
            "b": round(m["beta"], 4),
            "a": round(m["alpha"], 4),
            "xe": round(m["x_E"], 4),
            "ye": round(m["y_E"], 4),
            "r": round(m["correlation"], 4),
            "kge": round(m["kge"], 4),
            "e": round(m["error_total_pct"], 1),
            "w": round(m["weight"], 5),
            "tier": m["trust_tier"],
            "rej": rej,
        }
        if m["name"] in BORDERLINE:
            row["bl"] = BORDERLINE[m["name"]]
        models.append(row)

    models.sort(key=lambda x: x["kge"], reverse=True)
    n_rej = sum(1 for m in models if m["rej"])

    out = {
        "case": "Bologna — Aras Diagram of the CMIP6 trust screening",
        "notes": "Re-run (July 2026) of the exact screening configuration "
                 "behind the published +14.2% rx1day projection: monthly "
                 "climatology vs observed ERA5-Land, 1995-2014, 50 km radius. "
                 "The 32 trusted weights reproduce the published run to four "
                 "decimals. EC-Earth3-Veg-LR is rejected (negative "
                 "correlation); HadGEM3-GC31-MM, rejected originally, now "
                 "sits marginally above the floor and is flagged borderline.",
        "region": {"lat": 44.494, "lon": 11.343, "radius_km": 50},
        "reference": "ERA5-Land",
        "window": ["1995-01-01", "2014-12-31"],
        "n_models": len(models),
        "n_rejected": n_rej,
        "models": models,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
    print(f"{OUT}: {len(models)} models, {n_rej} rejected, "
          f"{sum(1 for m in models if 'bl' in m)} borderline")


if __name__ == "__main__":
    main()
