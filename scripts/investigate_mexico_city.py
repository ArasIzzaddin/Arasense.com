"""
Mexico City investigation — why does the fast-mode screening baseline say
263 mm rx1day?

Runs the full-ensemble projection (fast_mode off) and the diagnostic for
Mexico City and saves both raw responses to docs/portfolios/. The goal is
to either publish a defensible number or document exactly which model(s)
broke the screening baseline.

    python scripts/investigate_mexico_city.py
"""

import json
import time

import requests

BASE = "http://127.0.0.1:8080"
LAT, LON = 19.433, -99.133

COMMON = {
    "lat": LAT, "lon": LON, "radius_km": 50,
    "variable": "precipitation", "metric": "rx1day",
    "hist_start": "1995-01-01", "hist_end": "2014-12-31",
}


def run(name: str, path: str, payload: dict, out: str) -> None:
    t0 = time.time()
    print(f"{name}: running…", flush=True)
    resp = requests.post(BASE + path, json=payload, timeout=5400)
    body = resp.json()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(body, f, indent=1)
    print(f"{name}: HTTP {resp.status_code} in {time.time()-t0:.0f}s -> {out}", flush=True)


def main() -> None:
    run("full projection", "/api/climate/projection",
        {**COMMON, "scenario": "ssp245",
         "future_start": "2040-01-01", "future_end": "2059-12-31",
         "fast_mode": False},
        "docs/portfolios/mexico-city-full-projection.json")


if __name__ == "__main__":
    main()
