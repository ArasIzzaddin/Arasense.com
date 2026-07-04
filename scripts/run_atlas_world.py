"""
World Trust Atlas runner — global preview tier.

Same method and settings as the European Trust Atlas (rx1day, SSP2-4.5,
50 km radius, 1995-2014 vs 2040-2059, fast_mode 5-model screening ensemble),
POSTed to the local Arasense API. Results save incrementally to
docs/portfolios/world-trust-atlas.json; re-running skips finished cities.

Each city carries a qualitative reference-data confidence tier: how strongly
long-record ground observations constrain the ERA5-Land baseline there
(dense gauge networks -> "strong"; sparse tropical coverage -> "weak").
The tier is editorial metadata, published alongside the numbers so readers
can weigh them — the same honesty rule as model agreement.

    python scripts/run_atlas_world.py
"""

import json
import os
import time

import requests

API = "http://127.0.0.1:8080/api/climate/projection"
OUT = "docs/portfolios/world-trust-atlas.json"

CITIES = [
    # name, lat, lon, reference-data confidence
    ("New York", 40.713, -74.006, "strong"),
    ("Miami", 25.762, -80.192, "strong"),
    ("Mexico City", 19.433, -99.133, "moderate"),
    ("Sao Paulo", -23.551, -46.633, "moderate"),
    ("Lagos", 6.524, 3.379, "weak"),
    ("Nairobi", -1.286, 36.817, "weak"),
    ("Cape Town", -33.925, 18.424, "moderate"),
    ("Mumbai", 19.076, 72.878, "moderate"),
    ("Singapore", 1.352, 103.820, "moderate"),
    ("Jakarta", -6.208, 106.846, "moderate"),
    ("Tokyo", 35.677, 139.650, "strong"),
    ("Sydney", -33.869, 151.209, "strong"),
]

PAYLOAD_BASE = {
    "radius_km": 50, "variable": "precipitation", "metric": "rx1day",
    "scenario": "ssp245", "hist_start": "1995-01-01", "hist_end": "2014-12-31",
    "future_start": "2040-01-01", "future_end": "2059-12-31", "fast_mode": True,
}


def load() -> dict:
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    return {
        "case": "World Trust Atlas — global preview",
        "notes": "rx1day, SSP2-4.5, 1995-2014 vs 2040-2059, 50 km radius, "
                 "fast_mode 5-model screening ensemble (same method as the "
                 "European Trust Atlas). Each city carries a qualitative "
                 "reference-data confidence tier.",
        "cities": {},
    }


def main() -> None:
    data = load()
    for name, lat, lon, conf in CITIES:
        if name in data["cities"] and "error" not in data["cities"][name]:
            data["cities"][name]["confidence"] = conf
            print(f"{name}: already done, skipping")
            continue
        t0 = time.time()
        try:
            resp = requests.post(API, json={"lat": lat, "lon": lon, **PAYLOAD_BASE},
                                 timeout=1800)
            body = resp.json()
            proj = body.get("projection") or {}
            if resp.status_code != 200 or not proj:
                data["cities"][name] = {"error": body.get("detail", f"HTTP {resp.status_code}")}
            else:
                data["cities"][name] = {
                    "lat": lat, "lon": lon, "confidence": conf,
                    "historical": proj.get("historical_level"),
                    "future": proj.get("future_level"),
                    "change": proj.get("change"),
                    "pct_change": proj.get("pct_change"),
                    "agreement": proj.get("agreement_on_increase"),
                    "n_trusted": proj.get("n_models_trusted"),
                }
        except Exception as exc:  # noqa: BLE001 - record and continue
            data["cities"][name] = {"error": str(exc)}
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
        r = data["cities"][name]
        status = (f"{r['pct_change']:+.1f}% agree {r['agreement']*100:.0f}%"
                  if "error" not in r else f"ERROR {r['error'][:80]}")
        print(f"{name}: {status} ({time.time()-t0:.0f}s)", flush=True)

    ok = sum(1 for v in data["cities"].values() if "error" not in v)
    print(f"done: {ok}/{len(CITIES)} cities ok")


if __name__ == "__main__":
    main()
