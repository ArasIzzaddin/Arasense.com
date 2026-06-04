"""
Arasense validation evidence-pack generator.

Turns the output of the `/api/flood/validate-pilot` endpoint into a slide-ready
validation report for a regional case study (e.g. Emilia-Romagna / Bologna 2023).

It re-derives the standard categorical flood-verification scores hydrologists
expect — POD, FAR, CSI, frequency bias, F1 — from the raw confusion counts the
endpoint returns, and renders a markdown report plus a machine-readable JSON
pack. The scoring is pure and unit-tested; only `run_case()` touches the network.

Categorical scores (contingency-table verification):
    POD / recall        = TP / (TP + FN)        — probability of detection
    FAR                 = FP / (TP + FP)        — false alarm ratio
    precision           = TP / (TP + FP)        = 1 - FAR
    CSI / IoU           = TP / (TP + FP + FN)    — critical success index
    F1                  = 2 TP / (2 TP + FP + FN)
    frequency bias      = (TP + FP) / (TP + FN)  — >1 over-warns, <1 under-warns
    accuracy            = (TP + TN) / total
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date


# ─────────────────────────────────────────────────────────────────
#  Case presets
# ─────────────────────────────────────────────────────────────────
@dataclass
class ValidationCase:
    """A regional validation case = a flood event + the request to reproduce it."""
    name: str
    lat: float
    lon: float
    radius_km: float
    # Climate (CMIP6/ERA5) characterisation window:
    start_date: str
    end_date: str
    # Sentinel-1 post-event window the flood mask is derived from:
    sentinel_start_date: str
    sentinel_end_date: str
    scale: int = 2000
    threshold: float = 0.5
    fast_mode: bool = True
    notes: str = ""

    def to_request(self) -> dict:
        """Payload for POST /api/flood/validate-pilot."""
        return {
            "lat": self.lat, "lon": self.lon, "radius_km": self.radius_km,
            "start_date": self.start_date, "end_date": self.end_date,
            "sentinel_start_date": self.sentinel_start_date,
            "sentinel_end_date": self.sentinel_end_date,
            "scale": self.scale, "threshold": self.threshold,
            "fast_mode": self.fast_mode,
        }


# The 2023 Emilia-Romagna flood, centred on Bologna. Dates confirmed by the
# founder (hydrologist) for the May 2023 event.
EMILIA_ROMAGNA_2023 = ValidationCase(
    name="Emilia-Romagna / Bologna — May 2023 flood",
    lat=44.494, lon=11.343, radius_km=60,
    start_date="2023-05-01", end_date="2023-05-18",      # rainfall window through the 16-17 May peak
    sentinel_start_date="2023-05-17", sentinel_end_date="2023-05-27",  # post-event Sentinel-1 mask
    scale=1000, threshold=0.5, fast_mode=True,
    notes="Validation-stage screening pilot for the May 2023 Emilia-Romagna flood "
          "(main flooding 16-17 May 2023).",
)


# ─────────────────────────────────────────────────────────────────
#  Pure scoring
# ─────────────────────────────────────────────────────────────────
def _safe_div(num: float, den: float):
    return num / den if den else None


def categorical_scores(tp: int, fp: int, fn: int, tn: int = 0) -> dict:
    """Standard 2x2 contingency-table flood-verification scores.

    Returns floats in [0, 1] (or ratio for frequency bias); a score is None
    when its denominator is zero (undefined), so it is never silently 0.
    """
    total = tp + fp + fn + tn
    return {
        "precision": _safe_div(tp, tp + fp),
        "pod_recall": _safe_div(tp, tp + fn),
        "far": _safe_div(fp, tp + fp),
        "csi_iou": _safe_div(tp, tp + fp + fn),
        "f1": _safe_div(2 * tp, 2 * tp + fp + fn),
        "frequency_bias": _safe_div(tp + fp, tp + fn),
        "accuracy": _safe_div(tp + tn, total),
    }


def _fmt(v, pct: bool = True) -> str:
    if v is None:
        return "n/a"
    return f"{v * 100:.1f}%" if pct else f"{v:.2f}"


def build_evidence_pack(case: ValidationCase, api_response: dict) -> dict:
    """Combine the endpoint response into a structured evidence pack."""
    counts = api_response.get("counts", {})
    tp = int(counts.get("true_positive", 0))
    fp = int(counts.get("false_positive", 0))
    fn = int(counts.get("false_negative", 0))
    tn = int(counts.get("true_negative", 0))
    scores = categorical_scores(tp, fp, fn, tn)

    trust = api_response.get("trust_summary") or {}
    return {
        "case": case.name,
        "notes": case.notes,
        "event_window": {
            "climate": [case.start_date, case.end_date],
            "sentinel": [case.sentinel_start_date, case.sentinel_end_date],
        },
        "region": {"lat": case.lat, "lon": case.lon, "radius_km": case.radius_km},
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "scores": scores,
        "climate": {
            "driver": api_response.get("climate_driver"),
            "best_model": api_response.get("best_model"),
            "trusted_models": api_response.get("trusted_models"),
            "trust_weights": api_response.get("trust_weights"),
            "precip_mean": api_response.get("precip_mean"),
            "precip_spread": api_response.get("precip_spread"),
            "precip_anomaly": api_response.get("precip_anomaly"),
            "clim_mean": api_response.get("precip_climatology_mean"),
            "n_kept": trust.get("n_kept"),
            "n_models": trust.get("n_models"),
        },
        "sentinel_image_count": api_response.get("sentinel_image_count"),
        "grid_shape": api_response.get("grid_shape"),
        "threshold": api_response.get("threshold", case.threshold),
    }


def render_markdown(pack: dict) -> str:
    """Render a slide-ready markdown validation report from an evidence pack."""
    s = pack["scores"]
    c = pack["confusion"]
    cl = pack["climate"]
    ew = pack["event_window"]
    lines = [
        f"# Validation Evidence Pack — {pack['case']}",
        "",
        f"_Climate window {ew['climate'][0]} → {ew['climate'][1]} · "
        f"Sentinel-1 window {ew['sentinel'][0]} → {ew['sentinel'][1]}_",
        "",
        "> Validation-stage flood **screening**, compared against a Sentinel-1 "
        "threshold mask. Useful for pilot evaluation, not engineering-grade "
        "flood forecasting.",
        "",
        "## Skill vs. Sentinel-1 observed flood mask",
        "",
        "| Metric | Value | Reading |",
        "| --- | --- | --- |",
        f"| Critical Success Index (CSI / IoU) | **{_fmt(s['csi_iou'])}** | overlap of predicted vs. observed |",
        f"| Probability of Detection (POD / recall) | {_fmt(s['pod_recall'])} | share of observed flood captured |",
        f"| Precision | {_fmt(s['precision'])} | share of warnings that were correct |",
        f"| False Alarm Ratio (FAR) | {_fmt(s['far'])} | share of warnings that were wrong |",
        f"| F1 score | {_fmt(s['f1'])} | balance of POD and precision |",
        f"| Frequency bias | {_fmt(s['frequency_bias'], pct=False)} | >1 over-warns, <1 under-warns |",
        f"| Cell agreement | {_fmt(s['accuracy'])} | overall correct cells |",
        "",
        f"Confusion cells — TP {c['tp']} · FP {c['fp']} · FN {c['fn']} · TN {c['tn']}.",
        "",
        "## Climate signal driving the screen",
        "",
    ]
    if cl.get("driver"):
        lines += [
            f"- Driver: **{cl['driver']}** — event hindcast from observed "
            "rainfall, not a free-running climate model.",
            f"- Event precip: {cl.get('precip_mean')} mm/day "
            f"(climatology {cl.get('clim_mean')} mm/day, "
            f"anomaly {cl.get('precip_anomaly')} sigma).",
            "",
        ]
    else:
        lines += [
            f"- Trusted models: **{cl.get('n_kept')}/{cl.get('n_models')}** kept "
            f"({', '.join(cl.get('trusted_models') or []) or 'n/a'}).",
            f"- Top model: {cl.get('best_model') or 'n/a'}.",
            f"- Skill-weighted ensemble precip: {cl.get('precip_mean')} "
            f"± {cl.get('precip_spread')} mm/day.",
            "",
        ]
    if pack.get("notes"):
        lines += ["---", f"_Note: {pack['notes']}_", ""]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
#  Network runner (not unit-tested — needs a live API + Earth Engine)
# ─────────────────────────────────────────────────────────────────
def run_case(case: ValidationCase, api_base: str = "http://localhost:8080",
             out_dir: str = "docs/validation", timeout: int = 600) -> dict:
    """
    POST the case to a running Arasense API, write <case>.json and <case>.md,
    and return the evidence pack. Requires `requests`, a running server, and
    valid Earth Engine credentials.
    """
    import os
    import re
    import requests  # lazy: only needed for live runs

    resp = requests.post(f"{api_base}/api/flood/validate-pilot",
                         json=case.to_request(), timeout=timeout)
    resp.raise_for_status()
    pack = build_evidence_pack(case, resp.json())

    os.makedirs(out_dir, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", case.name.lower()).strip("-")
    with open(os.path.join(out_dir, f"{slug}.json"), "w", encoding="utf-8") as f:
        json.dump(pack, f, indent=2)
    with open(os.path.join(out_dir, f"{slug}.md"), "w", encoding="utf-8") as f:
        f.write(render_markdown(pack))
    return pack


if __name__ == "__main__":
    # Live run against a local server (needs GEE creds):
    #   python -m validation.evidence_pack
    pack = run_case(EMILIA_ROMAGNA_2023)
    print(render_markdown(pack))
