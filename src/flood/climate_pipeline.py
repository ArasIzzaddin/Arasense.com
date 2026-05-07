import numpy as np
import pandas as pd

from climate.aras_eval import ArasDiagram
from climate.data_fetcher import ArasenseDataFetcher


class FloodClimatePipeline:
    """
    Connects the Aras climate diagnostic pipeline to the flood GNN.

    Workflow:
        1. Fetch ERA5-Land + CMIP6 precipitation via ArasenseDataFetcher
        2. Rank all CMIP6 models with ArasDiagram → pick best (lowest E%)
        3. Return best-model precipitation stats ready to inject into graph nodes

    The returned precipitation features are:
        precip_mean    : mean daily precipitation over the period (mm/day)
        precip_anomaly : (model_mean - era5_mean) / era5_std  — normalised bias

    These two scalars are broadcast to every node in the hydrological graph,
    giving the GNN a climate signal it previously had none of.
    """

    def __init__(self, project_id: str):
        self.fetcher = ArasenseDataFetcher(project_id)

    # ── main entry point ──────────────────────────────────────────
    def get_best_model_precipitation(
        self,
        geometry,           # ee.Geometry
        start_date: str,    # "YYYY-MM-DD"
        end_date: str,      # "YYYY-MM-DD"
        fast_mode: bool = True,
    ) -> dict:
        """
        Run the full Aras diagnostic and return the best CMIP6 model's
        precipitation features for injection into the flood graph.

        Returns
        -------
        dict with keys:
            best_model      : str   — name of best CMIP6 model
            kge             : float — KGE of best model
            error_pct       : float — total error % (lower = better)
            precip_mean     : float — mean daily precip from best model (mm/day)
            precip_anomaly  : float — normalised bias vs ERA5
            era5_mean       : float — mean daily precip from ERA5 (mm/day)
            era5_std        : float — std of ERA5 precip
            all_metrics     : list  — full Aras metrics for all models
            model_series    : pd.Series — daily precip from best model
        """
        # 1. Fetch all data
        print("FloodClimatePipeline: fetching ERA5 + CMIP6 precipitation...")
        results = self.fetcher.get_climate_data(
            geometry    = geometry,
            start_date  = start_date,
            end_date    = end_date,
            variable    = "precipitation",
            fast_mode   = fast_mode,
        )

        # 2. Guard — need at least one model
        model_names = [k for k in results.keys() if k != "reference"]
        if not model_names:
            raise RuntimeError(
                "FloodClimatePipeline: no CMIP6 model data returned. "
                "Check GEE credentials and quota."
            )

        # 3. ERA5 reference series
        era5_series  = results["reference"]
        era5_mean    = float(era5_series.mean())
        era5_std     = float(era5_series.std())
        era5_std     = era5_std if era5_std > 1e-6 else 1.0

        # 4. Build aligned arrays for ArasDiagram
        aligned_ref   = results[model_names[0]]["reference"].values
        model_arrays  = [results[n]["model"].values for n in model_names]

        # 5. Run Aras diagram evaluation
        print("FloodClimatePipeline: running Aras diagram evaluation...")
        diagram = ArasDiagram(aligned_ref, model_arrays, model_names)

        # 6. Pick best model = lowest total error %
        best = min(diagram.results, key=lambda r: r["e_pct"])
        best_name = best["name"]
        print(f"FloodClimatePipeline: best model = {best_name} "
              f"(KGE={best['kge']:.3f}, E={best['e_pct']:.1f}%)")

        # 7. Extract best model precipitation series
        best_series   = results[best_name]["model"]
        precip_mean   = float(best_series.mean())
        precip_anomaly = (precip_mean - era5_mean) / era5_std

        # 8. Build full metrics list for API response
        all_metrics = [
            {
                "name"           : r["name"],
                "alpha"          : float(r["alpha"]),
                "beta"           : float(r["beta"]),
                "x_E"            : float(r["x_E"]),
                "y_E"            : float(r["y_E"]),
                "correlation"    : float(r["r"]),
                "kge"            : float(r["kge"]),
                "error_total_pct": float(r["e_pct"]),
                "is_best"        : r["name"] == best_name,
            }
            for r in diagram.results
        ]

        return {
            "best_model"    : best_name,
            "kge"           : float(best["kge"]),
            "error_pct"     : float(best["e_pct"]),
            "precip_mean"   : precip_mean,
            "precip_anomaly": precip_anomaly,
            "era5_mean"     : era5_mean,
            "era5_std"      : era5_std,
            "all_metrics"   : all_metrics,
            "model_series"  : best_series,
        }
