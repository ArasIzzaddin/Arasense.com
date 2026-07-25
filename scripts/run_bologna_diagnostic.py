"""
Full Bologna Aras Diagram diagnostic, run directly (no HTTP, no timeout).

Replicates POST /api/climate/diagnostic exactly — same fetcher, same
ArasDiagram, same metric fields — for the full CMIP6 ensemble against
ERA5-Land, 1995-2014, 50 km around Bologna. Writes bologna_diag_full.json
(metrics + trust reports, no bulk series).

    set PYTHONPATH=src && python scripts/run_bologna_diagnostic.py
"""

import json
import time

import ee

from climate.aras_eval import ArasDiagram
from climate.data_fetcher import ArasenseDataFetcher
from climate.trust_engine import ModelTrustEngine
from common.gee import initialize_earth_engine

LAT, LON, RADIUS_KM = 44.494, 11.343, 50
START, END = "1995-01-01", "2014-12-31"


def main() -> None:
    t0 = time.time()
    project_id = initialize_earth_engine()
    roi = ee.Geometry.Point([LON, LAT]).buffer(RADIUS_KM * 1000)
    fetcher = ArasenseDataFetcher(project_id)
    print("fetching climate data (full ensemble, 20y)…", flush=True)
    results = fetcher.get_climate_data(
        geometry=roi, start_date=START, end_date=END,
        variable="precipitation", ref_dataset="era5", fast_mode=False,
    )
    print(f"fetched in {time.time()-t0:.0f}s", flush=True)

    model_names = [k for k in results.keys() if k != "reference"]
    aligned_ref = results[model_names[0]]["reference"].values
    model_series = [results[name]["model"].values for name in model_names]
    aras = ArasDiagram(aligned_ref, model_series, model_names)
    trust = ModelTrustEngine(aras=aras)

    metrics = []
    for item in aras.results:
        metrics.append({
            "name": item["name"],
            "alpha": float(item["alpha"]),
            "beta": float(item["beta"]),
            "x_E": float(item["x_E"]),
            "y_E": float(item["y_E"]),
            "correlation": float(item["r"]),
            "kge": float(item["kge"]),
            "error_total_pct": float(item["e_pct"]),
        })

    out = {
        "input": {"lat": LAT, "lon": LON, "radius_km": RADIUS_KM,
                  "start_date": START, "end_date": END,
                  "variable": "precipitation", "ref_dataset": "era5",
                  "fast_mode": False},
        "n_models": len(model_names),
        "metrics": metrics,
        "trust": {"summary": trust.summary(), "models": trust.reports},
    }
    with open("bologna_diag_full.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(f"bologna_diag_full.json: {len(metrics)} models in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
