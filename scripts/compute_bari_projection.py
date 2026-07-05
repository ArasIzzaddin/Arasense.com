"""Compute a REAL trust-weighted Rx1day projection for Bari, Puglia.

Runs the same pipeline as POST /api/climate/projection-compare (the workflow
that produced the Bologna evidence pack), so the numbers are genuine, not
hand-entered. Writes a JSON in the same shape as
docs/projections/bologna-rx1day-ssp245-vs-ssp585.json.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from api.main import ClimateScenarioCompareRequest, climate_projection_compare  # noqa: E402

OUT = ROOT / "docs" / "startcup-demoday-final" / "data" / "bari-rx1day-ssp245-vs-ssp585.json"

# Bari, Puglia
LAT, LON = 41.1171, 16.8719

LABELS = {"ssp245": "SSP2-4.5 (moderate)", "ssp585": "SSP5-8.5 (high emissions)"}


def main() -> None:
    payload = ClimateScenarioCompareRequest(
        lat=LAT, lon=LON, radius_km=50, variable="precipitation",
        metric="rx1day", scenarios=["ssp245", "ssp585"],
        hist_start=date(1995, 1, 1), hist_end=date(2014, 12, 31),
        future_start=date(2040, 1, 1), future_end=date(2059, 12, 31),
        fast_mode=False,  # full ensemble, to match the "34 models" framing
    )
    print("Running Bari projection-compare (full ensemble, this can take many minutes)...", flush=True)
    res = climate_projection_compare(payload)

    scen_out = {}
    hist_level = None
    n_trusted = None
    for scen, proj in res["scenarios"].items():
        hist_level = proj["historical_level"]
        n_trusted = proj["n_models_trusted"]
        scen_out[scen] = {
            "label": LABELS.get(scen, scen),
            "future_level": proj["future_level"],
            "change": proj["change"],
            "change_low": proj["change_low"],
            "change_high": proj["change_high"],
            "pct_change": proj["pct_change"],
            "agreement_on_increase": proj["agreement_on_increase"],
        }

    out = {
        "case": "Bari — flood-driving rainfall, mid-century",
        "notes": "Trust-weighted CMIP6 projection over a 20-year climatology, Bari (Puglia). Same Arasense workflow as the Bologna evidence pack. Extremes are the forward-looking flood-risk driver.",
        "metric": "rx1day",
        "metric_label": "Maximum 1-day precipitation",
        "unit": "mm",
        "windows": res["windows"],
        "n_models_scored": res["n_models_scored"],
        "n_models_trusted": n_trusted,
        "historical_level": hist_level,
        "scenarios": scen_out,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print("WROTE", OUT, flush=True)
    print(json.dumps({"n_scored": out["n_models_scored"], "n_trusted": n_trusted,
                      "ssp245_pct": scen_out["ssp245"]["pct_change"],
                      "ssp245_agree": scen_out["ssp245"]["agreement_on_increase"],
                      "hist": hist_level}, indent=2), flush=True)


if __name__ == "__main__":
    main()
