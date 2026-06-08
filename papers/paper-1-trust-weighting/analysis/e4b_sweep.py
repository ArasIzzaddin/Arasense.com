"""
E4b sweep — aligned vs monthly scoring across multiple cities (Paper 1 evidence).

For each city, runs the perfect-model test for the chosen extreme metric twice:
trust scored on the monthly climatology (baseline) and on the annual target-metric
series (aligned). Aggregates the RMSE improvement-over-equal for both, so the paper
can show whether aligned scoring helps generally, not just at Bologna.

Saves results incrementally (survives a mid-run failure) to JSON, and writes a
markdown table.

    python e4b_sweep.py --metric rx1day
"""

import argparse
import json

import ee
import pandas as pd

from climate.data_fetcher import ArasenseDataFetcher
from common.gee import initialize_earth_engine
from validation.perfect_model import perfect_model_test

_METRIC = {
    "rx1day": ("precipitation", "max", 20.0),
    "p95": ("precipitation", "p95", 20.0),
    "heavy_precip_frac": ("precipitation", "heavy_frac", 20.0),
    "dry_day_frac": ("precipitation", "dry_frac", 1.0),
    "tx_max": ("temperature", "max", 0.0),
    "hot_day_frac": ("temperature", "hot_frac", 303.15),
}

CITIES = [
    ("Bologna", 44.494, 11.343),
    ("Rome", 41.903, 12.496),
    ("Milan", 45.464, 9.190),
    ("Florence", 43.770, 11.256),
]


def run_city(fetcher, lat, lon, radius_km, metric, scenario, hist, future):
    variable, stat, threshold = _METRIC[metric]
    roi = ee.Geometry.Point([lon, lat]).buffer(radius_km * 1000)
    loc = f"{lat:.4f},{lon:.4f},{radius_km:g}"

    _, monthly = fetcher.get_monthly_series(
        geometry=roi, start_date=hist[0], end_date=hist[1], variable=variable,
        fast_mode=False, include_reference=False, loc_key=loc)
    monthly_df = pd.DataFrame(monthly).dropna()
    annual = fetcher.get_annual_stat_series(
        geometry=roi, start_date=hist[0], end_date=hist[1], variable=variable,
        models=list(monthly_df.columns), stat=stat, threshold=threshold,
        scenario="historical", loc_key=loc)
    annual_df = pd.DataFrame(annual).dropna()
    fut = fetcher.get_extreme_stat(
        geometry=roi, start_date=future[0], end_date=future[1], variable=variable,
        models=list(annual_df.columns), stat=stat, threshold=threshold,
        scenario=scenario, loc_key=loc)

    models = [m for m in annual_df.columns if m in fut and m in monthly_df.columns]
    fut = {m: fut[m] for m in models}
    res_m = perfect_model_test({m: monthly_df[m].values for m in models}, fut)
    res_a = perfect_model_test({m: annual_df[m].values for m in models}, fut)
    return {"n_models": len(models),
            "monthly_improvement_pct": res_m["rmse_improvement_pct"],
            "aligned_improvement_pct": res_a["rmse_improvement_pct"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metric", default="rx1day", choices=list(_METRIC))
    ap.add_argument("--scenario", default="ssp245", choices=["ssp245", "ssp585"])
    ap.add_argument("--radius-km", type=float, default=50.0)
    ap.add_argument("--hist", nargs=2, default=["1995-01-01", "2014-12-31"])
    ap.add_argument("--future", nargs=2, default=["2040-01-01", "2059-12-31"])
    ap.add_argument("--out", default="e4b_sweep_result.json")
    args = ap.parse_args()

    project_id = initialize_earth_engine()
    fetcher = ArasenseDataFetcher(project_id)

    results = {"metric": args.metric, "scenario": args.scenario, "cities": {}}
    for name, lat, lon in CITIES:
        print(f"[{name}] running…", flush=True)
        try:
            results["cities"][name] = run_city(
                fetcher, lat, lon, args.radius_km, args.metric, args.scenario,
                args.hist, args.future)
            r = results["cities"][name]
            print(f"[{name}] monthly {r['monthly_improvement_pct']:+.1f}%  "
                  f"aligned {r['aligned_improvement_pct']:+.1f}%", flush=True)
        except Exception as exc:  # noqa: BLE001
            results["cities"][name] = {"error": str(exc)}
            print(f"[{name}] ERROR: {exc}", flush=True)
        json.dump(results, open(args.out, "w"), indent=2)   # incremental save

    # markdown table
    ok = {k: v for k, v in results["cities"].items() if "error" not in v}
    lines = [f"# E4b sweep — {args.metric} ({args.scenario})", "",
             "| City | models | monthly | aligned |", "| --- | --- | --- | --- |"]
    for k, v in results["cities"].items():
        if "error" in v:
            lines.append(f"| {k} | — | — | _{v['error'][:40]}_ |")
        else:
            lines.append(f"| {k} | {v['n_models']} | {v['monthly_improvement_pct']:+.1f}% "
                         f"| {v['aligned_improvement_pct']:+.1f}% |")
    if ok:
        ma = sum(v["aligned_improvement_pct"] for v in ok.values()) / len(ok)
        mm = sum(v["monthly_improvement_pct"] for v in ok.values()) / len(ok)
        better = sum(v["aligned_improvement_pct"] > v["monthly_improvement_pct"] for v in ok.values())
        lines += ["", f"Mean improvement: monthly {mm:+.1f}%, aligned {ma:+.1f}%. "
                  f"Aligned beats monthly in {better}/{len(ok)} cities."]
    open(args.out.replace(".json", ".md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
