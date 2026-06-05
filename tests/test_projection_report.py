"""Tests for the climate-projection report generator (pure parts, no network)."""

import pytest

from validation.projection_report import (
    BOLOGNA_2050,
    ProjectionCase,
    build_compare_report,
    build_projection_report,
    render_compare_markdown,
    render_markdown,
)


def _fake_response():
    # Shape mirrors the real /api/climate/projection response (Bologna rx1day run).
    return {
        "n_models_scored": 34,
        "windows": {"historical": ["1995-01-01", "2014-12-31"],
                    "future": ["2040-01-01", "2059-12-31"]},
        "projection": {
            "metric": "rx1day",
            "n_models_trusted": 32, "n_models_total": 34,
            "historical_level": 40.23, "future_level": 45.97,
            "change": 5.74, "change_low": -0.26, "change_high": 11.73,
            "pct_change": 14.2, "agreement_on_increase": 0.78,
            "trust_summary": {"best_model": "EC-Earth3"},
            "per_model": [
                {"name": "EC-Earth3", "weight": 0.05, "historical": 41.0, "future": 49.0, "change": 8.0},
                {"name": "MPI-ESM1-2-HR", "weight": 0.04, "historical": 38.0, "future": 40.0, "change": 2.0},
            ],
        },
    }


def test_build_report_core_fields():
    rep = build_projection_report(BOLOGNA_2050, _fake_response())
    assert rep["metric"] == "rx1day"
    assert rep["unit"] == "mm"                       # rx1day precipitation
    assert rep["n_models_trusted"] == 32
    assert rep["n_models_scored"] == 34
    assert rep["change"] == pytest.approx(5.74)
    assert rep["best_model"] == "EC-Earth3"


def test_render_markdown_has_headline_numbers():
    md = render_markdown(build_projection_report(BOLOGNA_2050, _fake_response()))
    assert "Climate Projection Report" in md
    assert "+5.74 mm" in md          # signed change with unit
    assert "+14.2%" in md            # percent change
    assert "32 of 34" in md          # trust breakdown
    assert "78%" in md               # agreement
    assert "EC-Earth3" in md         # best model + table


def test_temperature_unit_is_kelvin():
    case = ProjectionCase(name="T", lat=44, lon=11, variable="temperature", metric="mean")
    resp = {"n_models_scored": 5, "projection": {"metric": "mean", "n_models_trusted": 5,
            "historical_level": 285.0, "future_level": 287.0, "change": 2.0,
            "change_low": 1.5, "change_high": 2.5, "pct_change": 0.7,
            "agreement_on_increase": 1.0, "trust_summary": {"best_model": "X"}, "per_model": []}}
    rep = build_projection_report(case, resp)
    assert rep["unit"] == "K"
    assert "+2.00 K" in render_markdown(rep)


def test_case_to_request_roundtrip():
    req = BOLOGNA_2050.to_request()
    assert req["metric"] == "rx1day"
    assert req["fast_mode"] is False
    assert set(req) >= {"lat", "lon", "variable", "metric",
                        "hist_start", "future_end", "fast_mode"}


def test_render_handles_missing_fields_gracefully():
    rep = build_projection_report(BOLOGNA_2050, {"projection": {}})
    md = render_markdown(rep)               # must not raise on n/a values
    assert "n/a" in md


def _fake_compare_response():
    base = {"n_models_trusted": 32, "historical_level": 40.23}
    return {
        "n_models_scored": 34,
        "windows": {"historical": ["1995-01-01", "2014-12-31"],
                    "future": ["2040-01-01", "2059-12-31"]},
        "scenarios": {
            "ssp245": {**base, "future_level": 45.97, "change": 5.74,
                       "change_low": -0.26, "change_high": 11.73,
                       "pct_change": 14.2, "agreement_on_increase": 0.78},
            "ssp585": {**base, "future_level": 49.5, "change": 9.27,
                       "change_low": 1.0, "change_high": 17.5,
                       "pct_change": 23.0, "agreement_on_increase": 0.88},
        },
    }


def test_build_compare_report_shares_baseline():
    rep = build_compare_report(BOLOGNA_2050, _fake_compare_response())
    assert rep["historical_level"] == pytest.approx(40.23)   # shared baseline
    assert rep["n_models_trusted"] == 32
    assert set(rep["scenarios"]) == {"ssp245", "ssp585"}
    assert rep["scenarios"]["ssp585"]["pct_change"] == pytest.approx(23.0)


def test_render_compare_markdown_shows_both_scenarios():
    md = render_compare_markdown(build_compare_report(BOLOGNA_2050, _fake_compare_response()))
    assert "Scenario Comparison" in md
    assert "SSP2-4.5" in md and "SSP5-8.5" in md
    assert "+14.2%" in md and "+23.0%" in md
    assert "32 of 34" in md
