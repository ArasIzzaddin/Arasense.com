"""
E4 — perfect-model validation on real CMIP6 data (Paper 1).

Fetches the full CMIP6 ensemble's historical monthly series (for trust scoring)
and each model's future hazard-metric value, then runs the perfect-model test:
does skill-weighting the ensemble beat equal weighting at predicting a held-out
model's future?

Requires Earth Engine credentials and the platform on the path:
    export PYTHONPATH=.../src
    export ARASENSE_GCP_PROJECT=valid-shine-488311-d6
    export GCP_SERVICE_ACCOUNT_JSON="$(cat key.json)"
    python e4_perfect_model.py --lat 44.494 --lon 11.343 --metric rx1day

Heavy: a full-ensemble run reuses the platform fetch cache, so re-runs are fast.
"""

import argparse
import json

import ee
import pandas as pd

from climate.data_fetcher import ArasenseDataFetcher
from common.gee import initialize_earth_engine
from validation.perfect_model import perfect_model_test

# metric -> (variable, extreme-stat, threshold). "mean" is handled specially
# (future value = mean of the future monthly series) to test whether weighting
# helps for the climatological quantity the trust is actually scored on.
_METRIC = {
    "mean": ("precipitation", "mean", 0.0),
    "rx1day": ("precipitation", "rx1day", 20.0),
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
    ap.add_argument("--fast-mode", action="store_true", help="5-model subset (debug)")
    ap.add_argument("--out", default="e4_perfect_model_result.json")
    args = ap.parse_args()

    variable, stat, threshold = _METRIC[args.metric]
    project_id = initialize_earth_engine()
    fetcher = ArasenseDataFetcher(project_id)
    roi = ee.Geometry.Point([args.lon, args.lat]).buffer(args.radius_km * 1000)
    loc = f"{args.lat:.4f},{args.lon:.4f},{args.radius_km:g}"

    print("Fetching historical monthly series (all models)…")
    _, hist_models = fetcher.get_monthly_series(
        geometry=roi, start_date=args.hist[0], end_date=args.hist[1],
        variable=variable, fast_mode=args.fast_mode, include_reference=False, loc_key=loc)
    if len(hist_models) < 3:
        raise SystemExit("Need >= 3 models with historical data.")
    hist_df = pd.DataFrame(hist_models).dropna()
    models = list(hist_df.columns)

    print(f"Fetching future '{args.metric}' for {len(models)} models ({args.scenario})…")
    if stat == "mean":
        _, fut_models = fetcher.get_monthly_series(
            geometry=roi, start_date=args.future[0], end_date=args.future[1],
            variable=variable, models=models, fast_mode=args.fast_mode,
            scenario=args.scenario, loc_key=loc)
        future = {m: float(s.mean()) for m, s in fut_models.items() if not s.empty}
    else:
        future = fetcher.get_extreme_stat(
            geometry=roi, start_date=args.future[0], end_date=args.future[1],
            variable=variable, models=models, stat=stat, threshold=threshold,
            scenario=args.scenario, loc_key=loc)

    hist_by_model = {m: hist_df[m].values for m in models if m in future}
    future_by_model = {m: future[m] for m in models if m in future}
    print(f"Running perfect-model test on {len(future_by_model)} models…")
    res = perfect_model_test(hist_by_model, future_by_model)

    res["meta"] = {"lat": args.lat, "lon": args.lon, "metric": args.metric,
                   "scenario": args.scenario, "hist": args.hist, "future": args.future}
    json.dump(res, open(args.out, "w"), indent=2)
    print("\n=== PERFECT-MODEL TEST ===")
    print(f"models: {res['n_models']}")
    print(f"RMSE  weighted {res['rmse_weighted']:.3f}  vs equal {res['rmse_equal']:.3f}  "
          f"-> improvement {res['rmse_improvement_pct']:+.1f}%")
    print(f"weighting better for {res['n_truth_weighting_better']}/{res['n_models']} truth models")
    print(f"saved -> {args.out}")


if __name__ == "__main__":
    main()
