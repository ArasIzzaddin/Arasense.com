"""
Pre-warm the Arasense fetch cache for a live demo.

Runs the multi-hazard profile for each demo city, which warms the model-trust
scoring and every hazard metric for that location. After this finishes, clicking
those cities in the console (projection, multi-hazard, scenario compare) returns
in milliseconds — ideal before a stage demo.

Usage:
    python scripts/prewarm.py                       # defaults below, localhost:8088
    python scripts/prewarm.py --api-base http://127.0.0.1:8088

Note: the cache is process-level, so do NOT restart the server between warming
and demoing.
"""

import argparse
import json
import time
import urllib.error
import urllib.request

# Edit this list to the cities you will demo.
DEMO_CITIES = [
    ("Bologna", 44.494, 11.343),
    ("Rome", 41.903, 12.496),
    ("Jakarta", -6.200, 106.850),
]


def warm(api_base: str, lat: float, lon: float, timeout: int = 900) -> tuple[float, str]:
    body = json.dumps({"lat": lat, "lon": lon, "radius_km": 50,
                       "scenario": "ssp245", "fast_mode": True}).encode()
    req = urllib.request.Request(f"{api_base}/api/climate/hazard-profile",
                                 data=body, headers={"Content-Type": "application/json"})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            json.load(r)
        return time.time() - t, "ok"
    except urllib.error.HTTPError as exc:
        return time.time() - t, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return time.time() - t, f"error: {exc}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-base", default="http://127.0.0.1:8088")
    args = ap.parse_args()

    print(f"Pre-warming {len(DEMO_CITIES)} cities at {args.api_base} …")
    print("(first pass is cold ~5–8 min/city; subsequent demo clicks are instant)\n")
    for name, lat, lon in DEMO_CITIES:
        dt, status = warm(args.api_base, lat, lon)
        print(f"  {name:<12} {dt:6.0f}s  {status}")
    print("\nDone — these cities are now warm. Do not restart the server before the demo.")


if __name__ == "__main__":
    main()
