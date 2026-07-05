"""
Atlas re-verification sweep under the extreme-plausibility screen.

Re-runs every published Trust Atlas city (24 ranked European + 12 global
preview) through the live pipeline with identical settings and compares the
fresh result to the published number. Cities with sane ensembles should
match to rounding; any plausibility-screen exclusion or drift is recorded.

Incremental: results save after every city; re-running skips finished ones.

    python scripts/reverify_atlas.py
"""

import json
import os
import time

import requests

API = "http://127.0.0.1:8080/api/climate/projection"
OUT = "docs/portfolios/atlas-reverification-2026-07-05.json"

ITALIAN_COORDS = {
    "Rome": (41.893, 12.483), "Milan": (45.464, 9.190),
    "Florence": (43.770, 11.255), "Bologna": (44.494, 11.343),
    "Venice": (45.438, 12.327),
}

PAYLOAD_BASE = {
    "radius_km": 50, "variable": "precipitation", "metric": "rx1day",
    "scenario": "ssp245", "hist_start": "1995-01-01", "hist_end": "2014-12-31",
    "future_start": "2040-01-01", "future_end": "2059-12-31", "fast_mode": True,
}


def load_published():
    """(name, lat, lon, published_pct, published_agree) for every atlas city."""
    cities = []
    italian = json.load(open("docs/portfolios/italian-flood-portfolio.json", encoding="utf-8"))
    for r in italian["ranked"]:
        lat, lon = ITALIAN_COORDS[r["name"]]
        cities.append((r["name"], lat, lon, r["pct_change"], r["agreement"]))
    for src in ("docs/portfolios/european-trust-atlas.json",
                "docs/portfolios/world-trust-atlas.json"):
        data = json.load(open(src, encoding="utf-8"))
        for name, r in data["cities"].items():
            if "error" in r:
                continue
            cities.append((name, r["lat"], r["lon"], r["pct_change"], r["agreement"]))
    return cities


def main() -> None:
    out = {"case": "Atlas re-verification under extreme-plausibility screen",
           "cities": {}}
    if os.path.exists(OUT):
        out = json.load(open(OUT, encoding="utf-8"))

    cities = load_published()
    for name, lat, lon, pub_pct, pub_agree in cities:
        if name in out["cities"] and "error" not in out["cities"][name]:
            print(f"{name}: already re-verified, skipping")
            continue
        t0 = time.time()
        try:
            resp = requests.post(API, json={"lat": lat, "lon": lon, **PAYLOAD_BASE},
                                 timeout=1800)
            body = resp.json()
            proj = body.get("projection") or {}
            if resp.status_code != 200 or not proj:
                out["cities"][name] = {"error": body.get("detail", f"HTTP {resp.status_code}")}
            else:
                screen = proj.get("plausibility_screen")
                new_pct = proj.get("pct_change")
                out["cities"][name] = {
                    "published_pct": pub_pct,
                    "reverified_pct": new_pct,
                    "pct_drift": (None if new_pct is None
                                  else round(new_pct - pub_pct, 3)),
                    "published_agree": pub_agree,
                    "reverified_agree": proj.get("agreement_on_increase"),
                    "n_trusted": proj.get("n_models_trusted"),
                    "screen_excluded": ([m["name"] for m in screen["excluded_models"]]
                                        if screen else []),
                }
        except Exception as exc:  # noqa: BLE001 - record and continue
            out["cities"][name] = {"error": str(exc)}
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1)
        r = out["cities"][name]
        if "error" in r:
            status = f"ERROR {r['error'][:70]}"
        else:
            status = (f"{r['reverified_pct']:+.1f}% (drift {r['pct_drift']:+.2f} pts)"
                      + (f" SCREEN: {r['screen_excluded']}" if r["screen_excluded"] else ""))
        print(f"{name}: {status} ({time.time()-t0:.0f}s)", flush=True)

    ok = [v for v in out["cities"].values() if "error" not in v]
    drifted = [v for v in ok if v["pct_drift"] and abs(v["pct_drift"]) > 0.05]
    screened = [v for v in ok if v["screen_excluded"]]
    print(f"done: {len(ok)}/{len(cities)} ok, {len(drifted)} drifted >0.05 pts, "
          f"{len(screened)} with screen exclusions")


if __name__ == "__main__":
    main()
