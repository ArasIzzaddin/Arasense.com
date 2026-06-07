"""
E4b — does ALIGNED scoring rescue the weighting?

E4 scored trust on the monthly climatology and found weighting ~ equal for the
future extreme. Hypothesis: score trust on the target metric's OWN historical
year-to-year series (e.g. annual max 1-day rainfall) — aligning predictor and
predictand — and the perfect-model test may show a benefit.

Runs the perfect-model test twice for comparison:
  (a) trust scored on the monthly climatology (as in E4), and
  (b) trust scored on the annual target-metric series (aligned),
predicting the same future metric value. Same models, same future.

Requires Earth Engine credentials and PYTHONPATH=.../src.
    python e4b_aligned_scoring.py --lat 44.494 --lon 11.343 --metric rx1day
"""

import argparse
import json

import ee
import pandas as pd

from climate.data_fetcher import ArasenseDataFetcher
from common.gee import initialize_earth_engine
from validation.perfect_model import perfect_model_test

# metric -> (variable, extreme-stat, threshold)
_METRIC = {
    "rx1day": ("precipitation", "max", 20.0),
    "p95": ("precipitation", "p95", 20.0),
    "heavy_precip_frac": ("precipitation", "heavy_frac", 20.0),
    "dry_day_frac": ("precipitation", "dry_frac", 1.0),
    "tx_max": ("temperature", "max", 0.0),
    "hot_day_frac": ("temperature", "hot_frac", 303.15),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, default=44.494)
    ap.add_argument("--lon", type=float, default=11.343)
    ap.add_argument("--radius-km", type=float, default=50.0)
    ap.add_argument("--metric", default="rx1day", choices=list(_METRIC))
    ap.add_argument("--scenario", default="ssp245", choices=["ssp245", "ssp585"])
    ap.add_argument("--hist", nargs=2, default=["1995-01-01", "2014-12-31"])
    ap.add_argument("--future", nargs=2, default=["2040-01-01", "2059-12-31"])
    ap.add_argument("--out", default="e4b_aligned_result.json")
    args = ap.parse_args()

    variable, stat, threshold = _METRIC[args.metric]
    project_id = initialize_earth_engine()
    fetcher = ArasenseDataFetcher(project_id)
    roi = ee.Geometry.Point([args.lon, args.lat]).buffer(args.radius_km * 1000)
    loc = f"{args.lat:.4f},{args.lon:.4f},{args.radius_km:g}"

    print("Fetching historical MONTHLY series (baseline scoring)…")
    _, monthly = fetcher.get_monthly_series(
        geometry=roi, start_date=args.hist[0], end_date=args.hist[1],
        variable=variable, fast_mode=False, include_reference=False, loc_key=loc)
    monthly_df = pd.DataFrame(monthly).dropna()

    print("Fetching historical ANNUAL target-metric series (aligned scoring)…")
    annual = fetcher.get_annual_stat_series(
        geometry=roi, start_date=args.hist[0], end_date=args.hist[1],
        variable=variable, models=list(monthly_df.columns), stat=stat,
        threshold=threshold, scenario="historical", loc_key=loc)
    annual_df = pd.DataFrame(annual).dropna()

    print(f"Fetching future '{args.metric}' values…")
    future = fetcher.get_extreme_stat(
        geometry=roi, start_date=args.future[0], end_date=args.future[1],
        variable=variable, models=list(annual_df.columns), stat=stat,
        threshold=threshold, scenario=args.scenario, loc_key=loc)

    models = [m for m in annual_df.columns if m in future and m in monthly_df.columns]
    fut = {m: future[m] for m in models}

    res_monthly = perfect_model_test({m: monthly_df[m].values for m in models}, fut)
    res_aligned = perfect_model_test({m: annual_df[m].values for m in models}, fut)

    out = {"meta": {"lat": args.lat, "lon": args.lon, "metric": args.metric,
                    "scenario": args.scenario, "n_models": len(models)},
           "monthly_scoring": res_monthly, "aligned_scoring": res_aligned}
    json.dump(out, open(args.out, "w"), indent=2)

    print("\n=== ALIGNED vs MONTHLY scoring (perfect-model) ===")
    print(f"models: {len(models)}")
    print(f"  monthly-scored:  RMSE w {res_monthly['rmse_weighted']:.3f} vs e "
          f"{res_monthly['rmse_equal']:.3f}  -> {res_monthly['rmse_improvement_pct']:+.1f}%")
    print(f"  aligned-scored:  RMSE w {res_aligned['rmse_weighted']:.3f} vs e "
          f"{res_aligned['rmse_equal']:.3f}  -> {res_aligned['rmse_improvement_pct']:+.1f}%")
    print(f"saved -> {args.out}")


if __name__ == "__main__":
    main()
