"""Tests for the climate-risk portfolio report (pure parts, no network)."""

import pytest

from validation.portfolio_report import (
    PortfolioCase,
    PortfolioLocation,
    build_portfolio_report,
    render_portfolio_markdown,
)


def _case():
    return PortfolioCase(
        name="Euro flood portfolio",
        locations=[PortfolioLocation("Bologna", 44.49, 11.34),
                   PortfolioLocation("Venice", 45.44, 12.33),
                   PortfolioLocation("Milan", 45.46, 9.19),
                   PortfolioLocation("Atlantis", 0.0, -30.0)],
        metric="rx1day", variable="precipitation",
    )


def _proj(change, pct, agree, hist=40.0):
    return {"projection": {"historical_level": hist, "future_level": hist + change,
                           "change": change, "pct_change": pct,
                           "agreement_on_increase": agree, "n_models_trusted": 30}}


def _results():
    return [
        ("Bologna", _proj(4.0, 10.0, 0.8)),
        ("Venice", _proj(8.0, 20.0, 0.9)),
        ("Milan", _proj(2.0, 5.0, 0.6)),
        ("Atlantis", {"detail": "No historical climate data returned."}),  # ocean point
    ]


def test_portfolio_ranks_most_worsening_first():
    rep = build_portfolio_report(_case(), _results())
    names = [r["name"] for r in rep["ranked"]]
    assert names == ["Venice", "Bologna", "Milan"]      # by % change desc
    assert rep["ranked"][0]["rank"] == 1
    assert [r["name"] for r in rep["unavailable"]] == ["Atlantis"]


def test_portfolio_markdown_lists_rank_and_unavailable():
    md = render_portfolio_markdown(build_portfolio_report(_case(), _results()))
    assert "Climate-Risk Portfolio" in md
    assert "| 1 | **Venice**" in md
    assert "+20%" in md and "+8.00 mm" in md
    assert "Out of skill / unavailable: Atlantis" in md


def test_request_for_roundtrip():
    case = _case()
    req = case.request_for(case.locations[0])
    assert req["lat"] == 44.49 and req["metric"] == "rx1day"
    assert set(req) >= {"lat", "lon", "variable", "metric", "scenario", "fast_mode"}


def test_empty_portfolio_renders():
    rep = build_portfolio_report(PortfolioCase(name="empty", locations=[]), [])
    md = render_portfolio_markdown(rep)      # must not raise
    assert "Climate-Risk Portfolio" in md
