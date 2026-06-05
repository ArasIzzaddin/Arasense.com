"""
Arasense climate-risk portfolio report.

Ranks a portfolio of locations (an insurer's or asset manager's exposures) by the
trust-weighted projected change in a single hazard metric — answering "which of
my assets worsen most?" Each location is screened independently; out-of-skill
locations are listed, not silently dropped. Structuring/rendering is pure and
unit-tested; only run_portfolio() touches the network.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from validation.projection_report import _disp, _disp_change, _meta


@dataclass
class PortfolioLocation:
    name: str
    lat: float
    lon: float


@dataclass
class PortfolioCase:
    name: str
    locations: list[PortfolioLocation]
    variable: str = "precipitation"
    metric: str = "rx1day"
    scenario: str = "ssp245"
    radius_km: float = 50.0
    hist_start: str = "1995-01-01"
    hist_end: str = "2014-12-31"
    future_start: str = "2040-01-01"
    future_end: str = "2059-12-31"
    fast_mode: bool = True
    notes: str = ""

    def request_for(self, loc: PortfolioLocation) -> dict:
        return {
            "lat": loc.lat, "lon": loc.lon, "radius_km": self.radius_km,
            "variable": self.variable, "metric": self.metric, "scenario": self.scenario,
            "hist_start": self.hist_start, "hist_end": self.hist_end,
            "future_start": self.future_start, "future_end": self.future_end,
            "fast_mode": self.fast_mode,
        }


def build_portfolio_report(case: PortfolioCase, results: list[tuple[str, dict]]) -> dict:
    """
    results: list of (location_name, api_response). An api_response with a
    'detail' key (HTTP error body) marks an unavailable / out-of-skill location.
    """
    label, unit = _meta(case.metric, case.variable)
    rows = []
    for name, resp in results:
        detail = (resp or {}).get("detail") if isinstance(resp, dict) else None
        proj = (resp or {}).get("projection") if isinstance(resp, dict) else None
        if detail or not proj:
            rows.append({"name": name, "available": False,
                         "reason": detail or "no projection"})
            continue
        rows.append({
            "name": name, "available": True,
            "historical": proj.get("historical_level"), "future": proj.get("future_level"),
            "change": proj.get("change"), "pct_change": proj.get("pct_change"),
            "agreement": proj.get("agreement_on_increase"),
            "n_trusted": proj.get("n_models_trusted"),
        })

    ranked = [r for r in rows if r["available"]]
    ranked.sort(key=lambda r: (r["pct_change"] if r["pct_change"] is not None else -1e9),
                reverse=True)
    for i, r in enumerate(ranked):
        r["rank"] = i + 1
    return {
        "case": case.name,
        "notes": case.notes,
        "metric": case.metric,
        "metric_label": label,
        "unit": unit,
        "scenario": case.scenario,
        "windows": {"historical": [case.hist_start, case.hist_end],
                    "future": [case.future_start, case.future_end]},
        "ranked": ranked,
        "unavailable": [r for r in rows if not r["available"]],
    }


def render_portfolio_markdown(report: dict) -> str:
    u = report["unit"]
    w = report["windows"]
    scen = (report.get("scenario") or "ssp245").upper()
    lines = [
        f"# Climate-Risk Portfolio — {report['case']}",
        "",
        f"_{report['metric_label']} change · {scen} · historical "
        f"{w['historical'][0]}–{w['historical'][1]} vs future {w['future'][0]}–{w['future'][1]}_",
        "",
        "> Trust-weighted CMIP6 projection (Aras Diagram), ranked most-worsening "
        "first. Each location is skill-screened independently; agreement is the "
        "share of trusted-model weight moving in the same direction.",
        "",
        f"| Rank | Location | Today ({u}) | 2050 ({u}) | Change | Agreement |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in report["ranked"]:
        agree = r.get("agreement")
        agree_s = "n/a" if agree is None else f"{agree * 100:.0f}%"
        pct = r.get("pct_change")
        pct_s = "" if pct is None else f" ({pct:+.0f}%)"
        lines.append(
            f"| {r['rank']} | **{r['name']}** | {_disp(r['historical'], u)} | "
            f"{_disp(r['future'], u)} | {_disp_change(r['change'], u)}{pct_s} | {agree_s} |"
        )
    if report.get("unavailable"):
        names = ", ".join(r["name"] for r in report["unavailable"])
        lines += ["", f"_Out of skill / unavailable: {names}._"]
    if report.get("notes"):
        lines += ["", "---", f"_Note: {report['notes']}_"]
    return "\n".join(lines) + "\n"


def run_portfolio(case: PortfolioCase, api_base: str = "http://localhost:8080",
                  out_dir: str = "docs/portfolios", timeout: int = 600) -> dict:
    """POST each location to /api/climate/projection and write <slug>.json/.md."""
    import os
    import re
    import requests  # lazy: only needed for live runs

    results = []
    for loc in case.locations:
        try:
            resp = requests.post(f"{api_base}/api/climate/projection",
                                 json=case.request_for(loc), timeout=timeout)
            results.append((loc.name, resp.json()))
        except requests.HTTPError as exc:  # pragma: no cover - network
            results.append((loc.name, {"detail": str(exc)}))

    report = build_portfolio_report(case, results)
    os.makedirs(out_dir, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", case.name.lower()).strip("-")
    with open(os.path.join(out_dir, f"{slug}.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    with open(os.path.join(out_dir, f"{slug}.md"), "w", encoding="utf-8") as f:
        f.write(render_portfolio_markdown(report))
    return report
