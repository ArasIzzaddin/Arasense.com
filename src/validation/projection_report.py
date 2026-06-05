"""
Arasense climate-projection report generator.

Turns a `/api/climate/projection` response into a shareable one-page report
(markdown + JSON) for a location: the trust-weighted change in a hazard metric
by mid-century, the across-model uncertainty, model agreement, and which models
were trusted. The structuring/rendering is pure and unit-tested; only
`run_projection()` touches the network.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


# (label, unit) per metric.
_METRIC_META = {
    "mean":              ("Mean precipitation", "mm/day"),
    "p95":               ("95th-percentile daily precipitation", "mm/day"),
    "rx1day":            ("Maximum 1-day precipitation", "mm"),
    "heavy_precip_frac": ("Heavy-rain-day frequency", "fraction of days"),
    "tx_max":            ("Maximum temperature", "K"),
    "hot_day_frac":      ("Hot-day frequency (Tmax >= 30 C)", "fraction of days"),
    "dry_day_frac":      ("Dry-day frequency", "fraction of days"),
    "cdd":               ("Consecutive dry days (max run)", "days"),
}


def _meta(metric: str, variable: str):
    label, unit = _METRIC_META.get(metric, (metric, ""))
    # Temperature mean/p95 reuse the precipitation labels — relabel + Kelvin.
    if variable == "temperature" and metric in ("mean", "p95"):
        label = label.replace("precipitation", "temperature").replace("rainfall", "temperature")
        unit = "K"
    return label, unit


@dataclass
class ProjectionCase:
    """A projection request = a place, a hazard metric, and two time windows."""
    name: str
    lat: float
    lon: float
    radius_km: float = 50.0
    variable: str = "precipitation"
    metric: str = "rx1day"
    hist_start: str = "1995-01-01"
    hist_end: str = "2014-12-31"
    future_start: str = "2040-01-01"
    future_end: str = "2059-12-31"
    fast_mode: bool = False
    notes: str = ""

    def to_request(self) -> dict:
        return {
            "lat": self.lat, "lon": self.lon, "radius_km": self.radius_km,
            "variable": self.variable, "metric": self.metric,
            "hist_start": self.hist_start, "hist_end": self.hist_end,
            "future_start": self.future_start, "future_end": self.future_end,
            "fast_mode": self.fast_mode,
        }


BOLOGNA_2050 = ProjectionCase(
    name="Bologna — flood-driving rainfall, mid-century",
    lat=44.494, lon=11.343, radius_km=50,
    variable="precipitation", metric="rx1day", fast_mode=False,
    notes="Trust-weighted CMIP6 projection over a 20-year climatology. Pilot "
          "demonstration; extremes are the forward-looking flood-risk driver.",
)


def build_projection_report(case: ProjectionCase, api_response: dict) -> dict:
    """Structure a /api/climate/projection response into a report dict."""
    proj = api_response.get("projection") or {}
    label, unit = _meta(proj.get("metric", case.metric), case.variable)
    windows = api_response.get("windows", {
        "historical": [case.hist_start, case.hist_end],
        "future": [case.future_start, case.future_end],
    })
    return {
        "case": case.name,
        "notes": case.notes,
        "region": {"lat": case.lat, "lon": case.lon, "radius_km": case.radius_km},
        "variable": case.variable,
        "metric": proj.get("metric", case.metric),
        "metric_label": label,
        "unit": unit,
        "windows": windows,
        "n_models_scored": api_response.get("n_models_scored"),
        "n_models_trusted": proj.get("n_models_trusted"),
        "historical_level": proj.get("historical_level"),
        "future_level": proj.get("future_level"),
        "change": proj.get("change"),
        "change_low": proj.get("change_low"),
        "change_high": proj.get("change_high"),
        "pct_change": proj.get("pct_change"),
        "agreement_on_increase": proj.get("agreement_on_increase"),
        "best_model": (proj.get("trust_summary") or {}).get("best_model"),
        "per_model": proj.get("per_model", []),
    }


def _fnum(v, nd=2):
    return "n/a" if v is None else f"{v:.{nd}f}"


def _fsigned(v, nd=2):
    return "n/a" if v is None else f"{v:+.{nd}f}"


def render_markdown(report: dict) -> str:
    u = report["unit"]
    w = report["windows"]
    agree = report.get("agreement_on_increase")
    agree_pct = "n/a" if agree is None else f"{agree * 100:.0f}%"
    pct = report.get("pct_change")
    pct_s = "n/a" if pct is None else f"{pct:+.1f}%"
    direction = "increase" if (report.get("change") or 0) >= 0 else "decrease"

    lines = [
        f"# Climate Projection Report — {report['case']}",
        "",
        f"_{report['metric_label']} · historical {w['historical'][0]}–{w['historical'][1]} "
        f"vs future {w['future'][0]}–{w['future'][1]}_",
        "",
        "> Trust-weighted CMIP6 projection: only models that pass skill screening "
        "(Aras Diagram, Izzaddin et al. 2024) contribute, weighted by skill. The "
        "band is the across-model spread — uncertainty reported, not hidden.",
        "",
        "## Headline",
        "",
        f"- **{report['metric_label']}: {_fsigned(report['change'])} {u} ({pct_s})** by mid-century",
        f"- Historical {_fnum(report['historical_level'])} {u} → future {_fnum(report['future_level'])} {u}",
        f"- Across-model spread (±1σ): {_fsigned(report['change_low'])} to {_fsigned(report['change_high'])} {u}",
        f"- Model agreement on {direction}: **{agree_pct}** of trusted-model weight",
        "",
        "## Model trust",
        "",
        f"- **{report.get('n_models_trusted')} of {report.get('n_models_scored')}** CMIP6 models "
        "passed skill screening and were skill-weighted.",
        f"- Best model: {report.get('best_model') or 'n/a'}.",
        "",
    ]

    pm = sorted(report.get("per_model", []), key=lambda m: m.get("weight", 0), reverse=True)[:8]
    if pm:
        lines += [
            "## Top contributing models",
            "",
            f"| Model | Weight | Historical ({u}) | Future ({u}) | Change ({u}) |",
            "| --- | --- | --- | --- | --- |",
        ]
        for m in pm:
            lines.append(
                f"| {m['name']} | {m.get('weight', 0) * 100:.0f}% | "
                f"{_fnum(m.get('historical'))} | {_fnum(m.get('future'))} | "
                f"{_fsigned(m.get('change'))} |"
            )
        lines.append("")

    if report.get("notes"):
        lines += ["---", f"_Note: {report['notes']}_", ""]
    return "\n".join(lines)


_SCENARIO_LABEL = {
    "ssp245": "SSP2-4.5 (moderate)",
    "ssp585": "SSP5-8.5 (high emissions)",
}


def build_compare_report(case: ProjectionCase, api_response: dict) -> dict:
    """Structure a /api/climate/projection-compare response into a report dict."""
    scen_in = api_response.get("scenarios", {})
    label, unit = _meta(case.metric, case.variable)
    windows = api_response.get("windows", {
        "historical": [case.hist_start, case.hist_end],
        "future": [case.future_start, case.future_end],
    })
    # Historical level is shared across scenarios (same baseline).
    any_proj = next(iter(scen_in.values()), {}) if scen_in else {}
    scenarios = {
        s: {
            "label": _SCENARIO_LABEL.get(s, s),
            "future_level": p.get("future_level"),
            "change": p.get("change"),
            "change_low": p.get("change_low"),
            "change_high": p.get("change_high"),
            "pct_change": p.get("pct_change"),
            "agreement_on_increase": p.get("agreement_on_increase"),
        }
        for s, p in scen_in.items()
    }
    return {
        "case": case.name,
        "notes": case.notes,
        "metric": case.metric,
        "metric_label": label,
        "unit": unit,
        "windows": windows,
        "n_models_scored": api_response.get("n_models_scored"),
        "n_models_trusted": any_proj.get("n_models_trusted"),
        "historical_level": any_proj.get("historical_level"),
        "scenarios": scenarios,
    }


def render_compare_markdown(report: dict) -> str:
    u = report["unit"]
    w = report["windows"]
    lines = [
        f"# Scenario Comparison — {report['case']}",
        "",
        f"_{report['metric_label']} · historical {w['historical'][0]}–{w['historical'][1]} "
        f"vs future {w['future'][0]}–{w['future'][1]}_",
        "",
        "> Trust-weighted CMIP6 projection (Aras Diagram). Model trust and the "
        "historical baseline are identical across scenarios — only emissions differ, "
        "so the gap between rows is the policy-relevant decision space.",
        "",
        f"Historical baseline: **{_fnum(report['historical_level'])} {u}** · "
        f"**{report.get('n_models_trusted')} of {report.get('n_models_scored')}** models trusted.",
        "",
        f"| Scenario | Future ({u}) | Change ({u}) | % change | Spread ({u}) | Agreement |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for s in ("ssp245", "ssp585"):
        sc = report["scenarios"].get(s)
        if not sc:
            continue
        agree = sc.get("agreement_on_increase")
        agree_s = "n/a" if agree is None else f"{agree * 100:.0f}%"
        pct = sc.get("pct_change")
        pct_s = "n/a" if pct is None else f"{pct:+.1f}%"
        lines.append(
            f"| {sc['label']} | {_fnum(sc['future_level'])} | {_fsigned(sc['change'])} | "
            f"{pct_s} | {_fsigned(sc['change_low'])} to {_fsigned(sc['change_high'])} | {agree_s} |"
        )
    lines.append("")
    if report.get("notes"):
        lines += ["---", f"_Note: {report['notes']}_", ""]
    return "\n".join(lines)


# Hazards shown in the multi-hazard city profile: (metric, hazard label, variable).
_HAZARD_DEF = [
    ("rx1day", "Flood-driving rainfall", "precipitation"),
    ("tx_max", "Heat", "temperature"),
    ("dry_day_frac", "Drought", "precipitation"),
]


def _disp(v, unit):
    if v is None:
        return "n/a"
    if unit == "K":
        return f"{v - 273.15:.1f} °C"
    if unit == "fraction of days":
        return f"{v * 100:.1f}% of days"
    return f"{v:.2f} {unit}"


def _disp_change(v, unit):
    if v is None:
        return "n/a"
    if unit == "K":
        return f"{v:+.1f} K"           # a Kelvin delta equals a Celsius delta
    if unit == "fraction of days":
        return f"{v * 100:+.1f} pts"
    return f"{v:+.2f} {unit}"


def build_hazard_profile(case: ProjectionCase, api_response: dict) -> dict:
    """Structure a /api/climate/hazard-profile response into a multi-hazard report."""
    haz_in = api_response.get("hazards", {})
    hazards = []
    for metric, hazard_label, variable in _HAZARD_DEF:
        p = haz_in.get(metric)
        if not p or "error" in p:
            hazards.append({"hazard": hazard_label, "metric": metric, "available": False,
                            "reason": (p or {}).get("error", "not available")})
            continue
        label, unit = _meta(metric, variable)
        hazards.append({
            "hazard": hazard_label, "metric": metric, "indicator": label, "unit": unit,
            "available": True,
            "historical": p.get("historical_level"), "future": p.get("future_level"),
            "change": p.get("change"), "pct_change": p.get("pct_change"),
            "agreement": p.get("agreement_on_increase"), "n_trusted": p.get("n_models_trusted"),
        })
    return {
        "case": case.name,
        "notes": case.notes,
        "scenario": api_response.get("scenario"),
        "windows": api_response.get("windows", {
            "historical": [case.hist_start, case.hist_end],
            "future": [case.future_start, case.future_end],
        }),
        "n_models_scored": api_response.get("n_models_scored"),
        "hazards": hazards,
    }


def render_hazard_markdown(report: dict) -> str:
    w = report["windows"]
    scen = (report.get("scenario") or "ssp245").upper().replace("SSP", "SSP")
    lines = [
        f"# Multi-Hazard Climate Profile — {report['case']}",
        "",
        f"_Scenario {scen} · historical {w['historical'][0]}–{w['historical'][1]} "
        f"vs future {w['future'][0]}–{w['future'][1]}_",
        "",
        "> Trust-weighted CMIP6 projection (Aras Diagram). Each hazard uses only the "
        "models that pass skill screening for that variable here; agreement is the "
        "share of trusted-model weight moving in the same direction.",
        "",
        "| Hazard | Indicator | Today | 2050 | Change | Agreement |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for h in report["hazards"]:
        if not h.get("available"):
            lines.append(f"| {h['hazard']} | — | _out of skill / unavailable_ | — | — | — |")
            continue
        u = h["unit"]
        agree = h.get("agreement")
        agree_s = "n/a" if agree is None else f"{agree * 100:.0f}%"
        pct = h.get("pct_change")
        pct_s = "" if pct is None else f" ({pct:+.0f}%)"
        lines.append(
            f"| **{h['hazard']}** | {h['indicator']} | {_disp(h['historical'], u)} | "
            f"{_disp(h['future'], u)} | {_disp_change(h['change'], u)}{pct_s} | {agree_s} |"
        )
    lines.append("")
    if report.get("notes"):
        lines += ["---", f"_Note: {report['notes']}_", ""]
    return "\n".join(lines)


def run_projection(case: ProjectionCase, api_base: str = "http://localhost:8080",
                   out_dir: str = "docs/projections", timeout: int = 3600) -> dict:
    """POST the case to a running Arasense API and write <slug>.json/.md."""
    import os
    import re
    import requests  # lazy: only needed for live runs

    resp = requests.post(f"{api_base}/api/climate/projection",
                         json=case.to_request(), timeout=timeout)
    resp.raise_for_status()
    report = build_projection_report(case, resp.json())

    os.makedirs(out_dir, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", case.name.lower()).strip("-")
    with open(os.path.join(out_dir, f"{slug}.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    with open(os.path.join(out_dir, f"{slug}.md"), "w", encoding="utf-8") as f:
        f.write(render_markdown(report))
    return report


if __name__ == "__main__":
    report = run_projection(BOLOGNA_2050)
    print(render_markdown(report))
