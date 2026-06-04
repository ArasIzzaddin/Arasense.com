import numpy as np
import pandas as pd

from climate.aras_eval import ArasDiagram
from climate.data_fetcher import ArasenseDataFetcher
from climate.trust_engine import ModelTrustEngine


class FloodClimatePipeline:
    """
    Connects the Aras climate diagnostic pipeline to the flood GNN.

    Trust-driven workflow:
        1. Fetch ERA5-Land + CMIP6 precipitation via ArasenseDataFetcher
        2. Score every CMIP6 model with the Model Trust Engine (Aras Diagram)
        3. Drop models that fail the mean-flow benchmark (KGE <= -0.41) and
           build a SKILL-WEIGHTED ENSEMBLE precipitation from the survivors
        4. Return ensemble precipitation stats ready to inject into graph nodes

    The returned precipitation features are:
        precip_mean    : skill-weighted ensemble mean daily precip (mm/day)
        precip_anomaly : (precip_mean - era5_mean) / era5_std  — normalised bias
        precip_spread  : weighted across-model spread (mm/day) — an uncertainty
                         signal the single-best-model approach could not provide

    These scalars are broadcast to every node in the hydrological graph, giving
    the GNN a climate signal driven only by models that earned trust here.
    """

    def __init__(self, project_id: str):
        self.fetcher = ArasenseDataFetcher(project_id)

    # ── main entry point ──────────────────────────────────────────
    def get_trusted_precipitation(
        self,
        geometry,           # ee.Geometry
        start_date: str,    # "YYYY-MM-DD"
        end_date: str,      # "YYYY-MM-DD"
        fast_mode: bool = True,
        sharpness: float = 1.0,
    ) -> dict:
        """
        Run the Model Trust Engine and return a SKILL-WEIGHTED ENSEMBLE
        precipitation signal for injection into the flood graph. Models that
        fail the mean-flow benchmark (KGE <= -0.41) contribute nothing.

        Returns
        -------
        dict with keys:
            best_model      : str   — top-ranked CMIP6 model (display/back-compat)
            kge             : float — KGE of the top-ranked model
            error_pct       : float — total error % of the top-ranked model
            precip_mean     : float — skill-weighted ensemble mean precip (mm/day)
            precip_anomaly  : float — normalised bias of the ensemble vs ERA5
            precip_spread   : float — weighted across-model spread (mm/day)
            era5_mean       : float — mean daily precip from ERA5 (mm/day)
            era5_std        : float — std of ERA5 precip
            models_used     : list  — kept (trusted) model names
            weights         : list  — their normalised skill weights
            trust_summary   : dict  — ModelTrustEngine.summary()
            model_reports   : list  — per-model trust reports
            all_metrics     : list  — full Aras metrics (back-compat) + trust fields
            model_series    : pd.Series — the weighted ensemble daily precip series
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

        # 4. Build aligned arrays and score the ensemble with the Trust Engine
        aligned_ref   = results[model_names[0]]["reference"].values
        model_arrays  = [results[n]["model"].values for n in model_names]
        print("FloodClimatePipeline: scoring ensemble with Model Trust Engine...")
        engine  = ModelTrustEngine(aligned_ref, model_arrays, model_names,
                                   sharpness=sharpness)
        summary = engine.summary()

        # 5. Refuse to drive flood from an out-of-skill ensemble
        kept = [r for r in engine.reports if r["weight"] > 0]
        if not kept:
            raise RuntimeError(
                "FloodClimatePipeline: every CMIP6 model is out-of-skill here "
                "(KGE <= -0.41). Refusing to drive the flood graph from an "
                "untrusted ensemble."
            )

        # 6. Build the skill-weighted ensemble precipitation series.
        #    Align kept-model series on their common dates, then weight them.
        kept_series = {r["name"]: results[r["name"]]["model"] for r in kept}
        df = pd.DataFrame(kept_series).dropna()
        if df.empty:
            raise RuntimeError(
                "FloodClimatePipeline: kept models share no overlapping dates."
            )
        ens = engine.weighted_ensemble({n: df[n].values for n in df.columns})
        central = np.asarray(ens["central"], dtype=float)
        spread  = np.asarray(ens["upper"], dtype=float) - central

        ensemble_series = pd.Series(central, index=df.index)
        precip_mean     = float(central.mean())
        precip_anomaly  = (precip_mean - era5_mean) / era5_std
        precip_spread   = float(spread.mean())

        best_name = summary["best_model"]
        best = next(r for r in engine.reports if r["name"] == best_name)
        print(f"FloodClimatePipeline: {len(kept)} trusted model(s), "
              f"top = {best_name} (KGE={best['kge']:.3f}); "
              f"ensemble precip = {precip_mean:.2f} ± {precip_spread:.2f} mm/day")

        # 7. Back-compat metrics list (Aras geometry) enriched with trust fields
        report_by_name = {r["name"]: r for r in engine.reports}
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
                "trust_tier"     : report_by_name[r["name"]]["trust_tier"],
                "weight"         : report_by_name[r["name"]]["weight"],
            }
            for r in engine.aras.results
        ]

        return {
            "best_model"    : best_name,
            "kge"           : float(best["kge"]),
            "error_pct"     : float(best["error_total_pct"]),
            "precip_mean"   : precip_mean,
            "precip_anomaly": precip_anomaly,
            "precip_spread" : precip_spread,
            "era5_mean"     : era5_mean,
            "era5_std"      : era5_std,
            "models_used"   : ens["models_used"],
            "weights"       : ens["weights"],
            "trust_summary" : summary,
            "model_reports" : engine.reports,
            "all_metrics"   : all_metrics,
            "model_series"  : ensemble_series,
        }

    # ── backward-compatible alias ─────────────────────────────────
    def get_best_model_precipitation(self, *args, **kwargs) -> dict:
        """
        Deprecated name. The pipeline is now trust-driven: this delegates to
        :meth:`get_trusted_precipitation`, which uses a skill-weighted ensemble
        instead of a single best model. Kept so existing callers keep working.
        """
        return self.get_trusted_precipitation(*args, **kwargs)
