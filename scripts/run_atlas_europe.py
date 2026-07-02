"""
European Trust Atlas runner.

POSTs each city to the local Arasense API (/api/climate/projection) with the
same settings as the Italian flood portfolio (rx1day, SSP2-4.5, 50 km radius,
1995-2014 vs 2040-2059, fast_mode 5-model screening ensemble) and saves results
incrementally to docs/portfolios/european-trust-atlas.json so a mid-run failure
loses nothing. Re-running skips cities already present.

    python scripts/run_atlas_europe.py
"""

import json
import os
import time

import requests

API = "http://127.0.0.1:8080/api/climate/projection"
OUT = "docs/portfolios/european-trust-atlas.json"

CITIES = [
    # name, lat, lon
    ("London", 51.507, -0.128),
    ("Paris", 48.857, 2.352),
    ("Berlin", 52.520, 13.405),
    ("Madrid", 40.417, -3.704),
    ("Barcelona", 41.387, 2.170),
    ("Lisbon", 38.722, -9.139),
    ("Amsterdam", 52.368, 4.904),
    ("Brussels", 50.847, 4.352),
    ("Vienna", 48.208, 16.373),
    ("Zurich", 47.377, 8.541),
    ("Munich", 48.135, 11.582),
    ("Prague", 50.075, 14.437),
    ("Warsaw", 52.230, 21.011),
    ("Budapest", 47.498, 19.040),
    ("Copenhagen", 55.676, 12.568),
    ("Stockholm", 59.329, 18.069),
    ("Oslo", 59.913, 10.752),
    ("Dublin", 53.349, -6.260),
    ("Athens", 37.984, 23.728),
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
        "case": "European Trust Atlas",
        "notes": "rx1day, SSP2-4.5, 1995-2014 vs 2040-2059, 50 km radius, "
                 "fast_mode 5-model screening ensemble (same method as the "
                 "Italian flood portfolio).",
        "cities": {},
    }


def main() -> None:
    data = load()
    for name, lat, lon in CITIES:
        if name in data["cities"] and "error" not in data["cities"][name]:
            print(f"{name}: already done, skipping")
            continue
        t0 = time.time()
        try:
            resp = requests.post(API, json={"lat": lat, "lon": lon, **PAYLOAD_BASE},
                                 timeout=900)
            body = resp.json()
            proj = body.get("projection") or {}
            if resp.status_code != 200 or not proj:
                data["cities"][name] = {"error": body.get("detail", f"HTTP {resp.status_code}")}
            else:
                data["cities"][name] = {
                    "lat": lat, "lon": lon,
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
        print(f"{name}: {status} ({time.time()-t0:.0f}s)")

    ok = sum(1 for v in data["cities"].values() if "error" not in v)
    print(f"done: {ok}/{len(CITIES)} cities ok")


if __name__ == "__main__":
    main()
