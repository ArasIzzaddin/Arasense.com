"""
Aras Diagram coordinates for the real Bologna trust screening.

This reproduces the exact screening that produced the published +14.2%
rx1day projection: the projection endpoint scores model trust from monthly
climatology (`get_monthly_series`), not daily series, then feeds it to
ModelTrustEngine. The engine keeps its ArasDiagram, so every model's
bias (beta-1), variability (alpha-1), correlation and total error come
straight out of the run that made the decision.

Monthly climatology is ~240 points per model instead of ~7300 daily ones,
which is why this completes in minutes while a daily-series diagnostic over
the same window does not return at all.

    set PYTHONPATH=src && python scripts/run_bologna_diagnostic.py
"""

import json
import time

import ee
import pandas as pd

from climate.data_fetcher import ArasenseDataFetcher
from climate.trust_engine import ModelTrustEngine
from common.gee import initialize_earth_engine

LAT, LON, RADIUS_KM = 44.494, 11.343, 50
START, END = "1995-01-01", "2014-12-31"
OUT = "bologna_diag_full.json"


def main() -> None:
    t0 = time.time()
    project_id = initialize_earth_engine()
    roi = ee.Geometry.Point([LON, LAT]).buffer(RADIUS_KM * 1000)
    fetcher = ArasenseDataFetcher(project_id)

    print("fetching monthly climatology (full ensemble, 1995-2014)…", flush=True)
    ref_hist, hist_models = fetcher.get_monthly_series(
        geometry=roi, start_date=START, end_date=END,
        variable="precipitation", fast_mode=False, include_reference=True,
        loc_key=f"{LAT:.4f},{LON:.4f},{RADIUS_KM:g}",
    )
    print(f"fetched in {time.time()-t0:.0f}s · {len(hist_models)} models", flush=True)

    hist_df = pd.DataFrame({"reference": ref_hist, **hist_models}).dropna()
    model_names = [c for c in hist_df.columns if c != "reference"]
    engine = ModelTrustEngine(hist_df["reference"].values,
                              [hist_df[n].values for n in model_names], model_names)

    by_name = {r["name"]: r for r in engine.reports}
    metrics = []
    for it in engine.aras.results:
        rep = by_name.get(it["name"], {})
        metrics.append({
            "name": it["name"],
            "alpha": float(it["alpha"]), "beta": float(it["beta"]),
            "x_E": float(it["x_E"]), "y_E": float(it["y_E"]),
            "correlation": float(it["r"]), "kge": float(it["kge"]),
            "error_total_pct": float(it["e_pct"]),
            "weight": float(rep.get("weight", 0.0)),
            "trust_tier": rep.get("trust_tier", ""),
        })

    n_rej = sum(1 for m in metrics if m["weight"] <= 0)
    json.dump({
        "input": {"lat": LAT, "lon": LON, "radius_km": RADIUS_KM,
                  "start_date": START, "end_date": END,
                  "variable": "precipitation", "basis": "monthly climatology",
                  "note": "same trust screening as the published rx1day projection"},
        "n_models": len(metrics), "n_rejected": n_rej,
        "metrics": metrics,
    }, open(OUT, "w", encoding="utf-8"), indent=1)
    print(f"{OUT}: {len(metrics)} models, {n_rej} rejected, {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
