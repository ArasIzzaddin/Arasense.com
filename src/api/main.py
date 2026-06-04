import os
import traceback
from datetime import date
from pathlib import Path
from typing import Literal, Optional

import ee
import numpy as np
import pandas as pd
import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from climate.aras_eval import ArasDiagram
from climate.trust_engine import ModelTrustEngine
from climate.projection import ClimateProjection, weighted_projection
from climate.data_fetcher import ArasenseDataFetcher
from climate.gnn_bias_corrector import ClimateBiasCorrector
from common.gee import get_earth_engine_status, get_project_id, initialize_earth_engine
from flood.graph_builder import ArasenseGraphBuilder
from flood.climate_pipeline import FloodClimatePipeline
from flood.gnn_model import ArasenseFloodGNN
from flood.s1_flood_fetcher import ArasenseFloodFetcher


app = FastAPI(
    title="Arasense API",
    version="1.0.0",
    description="Arasense API — climate diagnostics, flood graph, and integrated climate-driven flood analysis.",
)

BASE_DIR = Path(__file__).resolve().parents[2]


def model_to_dict(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def mask_to_cells(mask: np.ndarray, west: float, south: float, east: float, north: float) -> list[dict]:
    rows, cols = mask.shape
    lat_step = (north - south) / max(rows, 1)
    lon_step = (east - west) / max(cols, 1)
    cells = []
    for r, c in np.argwhere(mask > 0).tolist():
        cells.append(
            {
                "south": round(north - (r + 1) * lat_step, 6),
                "west": round(west + c * lon_step, 6),
                "north": round(north - r * lat_step, 6),
                "east": round(west + (c + 1) * lon_step, 6),
            }
        )
    return cells


class ClimateDiagnosticRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(50, gt=0, le=500)
    start_date: date
    end_date: date
    variable: Literal["temperature", "precipitation", "all_euro_cordex"] = "temperature"
    ref_dataset: str = "ERA5-Land"
    fast_mode: bool = True


class ClimateProjectionRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(50, gt=0, le=500)
    variable: Literal["temperature", "precipitation"] = "precipitation"
    metric: Literal["mean", "p95", "rx1day", "heavy_precip_frac"] = "mean"
    hist_start: date = date(1995, 1, 1)
    hist_end: date = date(2014, 12, 31)
    future_start: date = date(2040, 1, 1)
    future_end: date = date(2059, 12, 31)
    fast_mode: bool = True


class FloodGraphRequest(BaseModel):
    west: float = Field(..., ge=-180, le=180)
    south: float = Field(..., ge=-90, le=90)
    east: float = Field(..., ge=-180, le=180)
    north: float = Field(..., ge=-90, le=90)
    scale: int = Field(2000, ge=250, le=10000)


class ClimateBiasCorrectionRequest(BaseModel):
    reference_series: dict[str, float]
    model_series: dict[str, dict[str, float]]
    best_model_name: str


class FloodClimateDrivenRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(50, gt=0, le=500)
    start_date: date
    end_date: date
    scale: int = Field(1000, ge=250, le=10000)
    fast_mode: bool = True


class SentinelFloodRequest(BaseModel):
    west: float = Field(..., ge=-180, le=180)
    south: float = Field(..., ge=-90, le=90)
    east: float = Field(..., ge=-180, le=180)
    north: float = Field(..., ge=-90, le=90)
    start_date: date
    end_date: date
    scale: int = Field(2000, ge=250, le=10000)


class FloodValidationRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(50, gt=0, le=500)
    start_date: date
    end_date: date
    sentinel_start_date: date
    sentinel_end_date: date
    scale: int = Field(2000, ge=250, le=10000)
    threshold: float = Field(0.5, ge=0.05, le=0.95)
    fast_mode: bool = True


@app.get("/brand-mark.svg")
def brand_mark() -> FileResponse:
    return FileResponse(BASE_DIR / "site" / "brand-mark-classic.svg", media_type="image/svg+xml")


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Arasense Climate Console</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
  <style>
    :root {
      --bg: #06151d;
      --bg-soft: #0b2029;
      --panel: rgba(10, 29, 37, 0.86);
      --panel-strong: rgba(8, 22, 29, 0.94);
      --line: rgba(121, 214, 196, 0.16);
      --text: #ebf9f4;
      --muted: #9bc9c0;
      --accent: #8bf0c7;
      --accent-strong: #29c48a;
      --amber: #ffd88a;
      --danger: #ff8f8f;
      --shadow: 0 30px 60px rgba(0, 0, 0, 0.24);
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      color: var(--text);
      font-family: "Space Grotesk", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(41, 196, 138, 0.16), transparent 26%),
        radial-gradient(circle at 90% 10%, rgba(255, 216, 138, 0.14), transparent 18%),
        linear-gradient(180deg, #031017 0%, var(--bg) 100%);
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
      background-size: 36px 36px;
      mask-image: linear-gradient(180deg, rgba(0,0,0,0.48), transparent 90%);
    }
    main {
      max-width: 1320px;
      margin: 0 auto;
      padding: 24px 24px 80px;
      position: relative;
      z-index: 1;
    }
    .nav, .hero, .workspace, .results-grid, .footer-panel {
      backdrop-filter: blur(18px);
    }
    .nav {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 28px;
      padding: 16px 20px;
      border: 1px solid var(--line);
      border-radius: 22px;
      background: rgba(7, 20, 26, 0.74);
      box-shadow: var(--shadow);
    }
    .brand-mark {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .brand-icon {
      width: 44px;
      height: 44px;
      display: block;
      flex: 0 0 auto;
      filter: drop-shadow(0 12px 18px rgba(0, 0, 0, 0.28));
    }
    .brand-copy strong {
      display: block;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      font-size: 12px;
      color: var(--accent);
    }
    .brand-copy span {
      color: var(--muted);
      font-size: 14px;
    }
    .nav-links {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }
    .pill {
      text-decoration: none;
      border-radius: 999px;
      padding: 11px 16px;
      font-size: 14px;
      border: 1px solid var(--line);
      color: var(--text);
      background: rgba(255,255,255,0.04);
    }
    .pill.primary {
      color: #03140f;
      background: linear-gradient(135deg, var(--accent), var(--accent-strong));
      border-color: transparent;
      font-weight: 700;
    }
    .hero {
      display: grid;
      grid-template-columns: 1.25fr 0.75fr;
      gap: 22px;
      margin-bottom: 22px;
    }
    .hero-card, .hero-side, .panel, .footer-panel {
      border: 1px solid var(--line);
      border-radius: 28px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }
    .hero-card {
      padding: 34px;
      background:
        radial-gradient(circle at top right, rgba(139,240,199,0.14), transparent 22%),
        linear-gradient(160deg, rgba(10, 29, 37, 0.92), rgba(6, 19, 25, 0.96));
    }
    .hero-side {
      padding: 26px;
      background:
        linear-gradient(160deg, rgba(18, 55, 63, 0.94), rgba(7, 20, 26, 0.96));
    }
    .eyebrow {
      display: inline-block;
      margin-bottom: 14px;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 12px;
      color: var(--accent);
    }
    h1, h2, h3 {
      margin: 0;
      font-family: "Fraunces", serif;
      font-weight: 700;
      letter-spacing: -0.03em;
    }
    h1 {
      font-size: clamp(44px, 7vw, 88px);
      line-height: 0.95;
      max-width: 760px;
      margin-bottom: 18px;
    }
    .lead {
      max-width: 760px;
      color: var(--muted);
      line-height: 1.7;
      font-size: 18px;
      margin-bottom: 28px;
    }
    .hero-stats {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }
    .stat {
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 16px;
      background: rgba(255,255,255,0.03);
    }
    .stat strong {
      display: block;
      font-size: 28px;
      color: var(--accent);
      margin-bottom: 6px;
    }
    .hero-side p, .hero-side li, .stat span {
      color: var(--muted);
      line-height: 1.6;
    }
    .hero-side ul {
      padding-left: 18px;
      margin: 16px 0 0;
    }
    .workspace {
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 22px;
      margin-bottom: 22px;
    }
    .panel {
      padding: 22px;
      background: var(--panel-strong);
    }
    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 16px;
    }
    .panel-header p {
      margin: 8px 0 0;
      color: var(--muted);
      line-height: 1.6;
      max-width: 680px;
    }
    .badge {
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 12px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--amber);
      background: rgba(255, 216, 138, 0.12);
      border: 1px solid rgba(255, 216, 138, 0.2);
      white-space: nowrap;
    }
    #map {
      height: 620px;
      border-radius: 22px;
      border: 1px solid var(--line);
      overflow: hidden;
      position: relative;
    }
    .map-fallback {
      display: none;
      place-items: center;
      text-align: center;
      padding: 24px;
      height: 620px;
      border-radius: 22px;
      border: 1px solid rgba(255, 143, 143, 0.28);
      background: rgba(255, 143, 143, 0.08);
      color: var(--text);
    }
    .map-tools {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-top: 14px;
    }
    .tool {
      border-radius: 16px;
      border: 1px solid var(--line);
      padding: 14px 16px;
      background: rgba(255,255,255,0.03);
      color: var(--muted);
    }
    .tool strong {
      display: block;
      color: var(--text);
      margin-bottom: 4px;
    }
    .controls {
      display: grid;
      gap: 16px;
    }
    .control-card {
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 18px;
      background: rgba(255,255,255,0.03);
    }
    .mode-tabs {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-bottom: 12px;
    }
    .mode-tab {
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 12px 14px;
      cursor: pointer;
      background: rgba(255,255,255,0.03);
      color: var(--muted);
      text-align: center;
      font-weight: 700;
    }
    .mode-tab.active {
      background: linear-gradient(135deg, rgba(139,240,199,0.18), rgba(41,196,138,0.34));
      color: var(--text);
      border-color: rgba(139,240,199,0.36);
    }
    form {
      display: grid;
      gap: 12px;
    }
    .row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    label {
      display: grid;
      gap: 6px;
      font-size: 13px;
      color: var(--muted);
    }
    input, select, textarea, button {
      width: 100%;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(3, 18, 23, 0.9);
      color: var(--text);
      padding: 12px 14px;
      font: inherit;
    }
    textarea {
      min-height: 360px;
      resize: vertical;
      font-family: "Space Grotesk", sans-serif;
    }
    button {
      cursor: pointer;
      font-weight: 700;
      background: linear-gradient(135deg, var(--accent), var(--accent-strong));
      color: #042016;
      border-color: transparent;
    }
    .secondary {
      background: rgba(255,255,255,0.04);
      color: var(--text);
      border-color: var(--line);
    }
    .meta-line {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 12px;
    }
    .chip {
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 12px;
      color: var(--muted);
      background: rgba(255,255,255,0.04);
      border: 1px solid var(--line);
    }
    .results-grid {
      display: grid;
      grid-template-columns: 0.8fr 1.2fr;
      gap: 22px;
      margin-bottom: 22px;
    }
    .results-stack {
      display: grid;
      gap: 22px;
    }
    .insight-list {
      display: grid;
      gap: 12px;
      margin-top: 16px;
    }
    .insight {
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,0.03);
    }
    .insight strong {
      display: block;
      margin-bottom: 4px;
      color: var(--accent);
    }
    .metric-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 16px;
    }
    .metric {
      padding: 14px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.03);
    }
    .metric strong {
      display: block;
      margin-bottom: 6px;
      font-size: 24px;
      color: var(--accent);
    }
    .footer-panel {
      padding: 22px;
      background: rgba(7, 20, 26, 0.8);
      border: 1px solid var(--line);
      border-radius: 24px;
    }
    .status.ok { color: var(--accent); }
    .status.error { color: var(--danger); }
    .leaflet-container {
      background: #09212b;
      font-family: "Space Grotesk", sans-serif;
    }
    .diagram-shell {
      border-radius: 22px;
      border: 1px solid var(--line);
      background: radial-gradient(circle at top, rgba(139,240,199,0.08), transparent 32%), rgba(255,255,255,0.02);
      min-height: 420px;
      padding: 16px;
    }
    .diagram-shell svg {
      width: 100%;
      height: 100%;
      min-height: 380px;
      display: block;
    }
    .diagram-placeholder {
      min-height: 380px;
      display: grid;
      place-items: center;
      text-align: center;
      color: var(--muted);
      line-height: 1.7;
    }
    .subpanel-grid {
      display: grid;
      grid-template-columns: 0.9fr 1.1fr;
      gap: 22px;
      margin-top: 22px;
    }
    .table-shell {
      border: 1px solid var(--line);
      border-radius: 18px;
      overflow: hidden;
      background: rgba(255,255,255,0.02);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      text-align: left;
    }
    th {
      color: var(--muted);
      font-weight: 500;
      background: rgba(255,255,255,0.03);
    }
    td strong {
      color: var(--text);
    }
    .chart-shell {
      border-radius: 22px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.02);
      min-height: 360px;
      padding: 16px;
    }
    .chart-shell svg {
      width: 100%;
      height: 100%;
      min-height: 320px;
      display: block;
    }
    .legend-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 10px;
    }
    .panel-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }
    .panel-actions button {
      width: auto;
      min-width: 190px;
    }
    .legend-item {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
    }
    .legend-swatch {
      width: 12px;
      height: 12px;
      border-radius: 999px;
    }
    .series-note {
      margin-top: 10px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.6;
    }
    @media (max-width: 980px) {
      .hero, .workspace, .results-grid, .row, .hero-stats, .metric-grid, .map-tools, .subpanel-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <main>
    <section class="nav">
      <div class="brand-mark">
        <img class="brand-icon" src="/brand-mark.svg" alt="Arasense logo">
        <div class="brand-copy">
          <strong>Arasense Climate Console</strong>
          <span>Map-first geospatial diagnostics for local testing</span>
        </div>
      </div>
      <div class="nav-links">
        <a class="pill" href="/healthz">Health</a>
        <a class="pill primary" href="/docs">API Docs</a>
      </div>
    </section>

    <section class="hero">
      <div class="hero-card">
        <div class="eyebrow">Spatial intelligence workbench</div>
        <h1>Next-level climate tech, running directly on your machine.</h1>
        <p class="lead">
          This console combines a live geospatial map, climate model diagnostics, and flood screening
          summaries in one interface. Click the map to set a climate point, drag a box for flood graph analysis,
          and inspect structured outputs without leaving the page.
        </p>
        <div class="hero-stats">
          <div class="stat"><strong>Live</strong><span>Map-driven spatial input selection</span></div>
          <div class="stat"><strong>GEE</strong><span>Earth Engine-backed climate retrieval</span></div>
          <div class="stat"><strong>FastAPI</strong><span>Local backend with deployable surface</span></div>
        </div>
      </div>
      <aside class="hero-side">
        <h2>Workflow</h2>
        <p>Use the interface in this order for the cleanest results.</p>
        <ul>
          <li>Click the map to position the climate ROI center and radius.</li>
          <li>Shift-drag on the map to define a flood-screening bounding box.</li>
          <li>Run diagnostics and inspect structured metrics in the console below.</li>
        </ul>
        <div class="meta-line">
          <span class="chip">Project: valid-shine-488311-d6</span>
          <span class="chip">Mode: local</span>
          <span class="chip">Docs: /docs</span>
        </div>
      </aside>
    </section>

    <section class="workspace">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2>Spatial Command Map</h2>
            <p>Single click sets the climate analysis point. Hold <strong>Shift</strong> and drag to draw a flood-screening bounding box.</p>
          </div>
          <div class="badge" id="map-status">Map ready</div>
        </div>
        <div id="map"></div>
        <div class="map-fallback" id="map-fallback">
          <div>
            <h3 style="margin-bottom:10px;">Map failed to load</h3>
            <p style="margin:0; color:var(--muted);">The external map library did not load in the browser. Reload the page or check browser console/network access.</p>
          </div>
        </div>
        <div class="map-tools">
          <div class="tool">
            <strong>Climate target</strong>
            <span id="climate-target">Lat 41.9028, Lon 12.4964, Radius 20 km</span>
          </div>
          <div class="tool">
            <strong>Flood box</strong>
            <span id="flood-target">West 11.0, South 44.2, East 11.3, North 44.4</span>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2>Mission Controls</h2>
            <p>Drive both analysis modes from the same console. The forms stay editable after map selection.</p>
          </div>
        </div>

        <div class="controls">
          <div class="control-card">
            <div class="mode-tabs">
              <div class="mode-tab top-tab active" data-target="climate-card">Climate Engine</div>
              <div class="mode-tab top-tab" data-target="flood-card">Flood Pilot</div>
            </div>
          </div>

          <div class="control-card" id="climate-card">
            <h3>Climate Diagnostic</h3>
            <form id="climate-form">
              <div class="row">
                <label>Latitude<input name="lat" id="climate-lat" type="number" step="any" value="41.9028"></label>
                <label>Longitude<input name="lon" id="climate-lon" type="number" step="any" value="12.4964"></label>
              </div>
              <div class="row">
                <label>Radius (km)<input name="radius_km" id="climate-radius" type="number" step="any" value="20"></label>
                <label>Variable
                  <select name="variable">
                    <option value="temperature">temperature</option>
                    <option value="precipitation">precipitation</option>
                    <option value="all_euro_cordex">all_euro_cordex</option>
                  </select>
                </label>
              </div>
              <div class="row">
                <label>Start Date<input name="start_date" type="date" value="2014-01-01"></label>
                <label>End Date<input name="end_date" type="date" value="2014-01-31"></label>
              </div>
              <div class="row">
                <label>Reference Dataset<input name="ref_dataset" type="text" value="ERA5-Land"></label>
                <label>Fast Mode
                  <select name="fast_mode">
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                </label>
              </div>
              <div class="row">
                <button type="submit">Run Climate Diagnostic</button>
                <button class="secondary" type="button" id="snap-rome">Reset to Rome</button>
              </div>
            </form>
          </div>

          <div class="control-card" id="flood-card" style="display:none;">
            <div class="mode-tabs" style="margin-bottom:14px;">
              <div class="mode-tab active" id="flood-mode-basic" onclick="setFloodMode('basic')">Terrain Only</div>
              <div class="mode-tab" id="flood-mode-climate" onclick="setFloodMode('climate')">Climate-Driven ★</div>
            </div>

            <div id="flood-basic-fields">
              <h3>Flood Graph Screening</h3>
              <form id="flood-form">
                <div class="row">
                  <label>West<input name="west" id="flood-west" type="number" step="any" value="11.0"></label>
                  <label>South<input name="south" id="flood-south" type="number" step="any" value="44.2"></label>
                </div>
                <div class="row">
                  <label>East<input name="east" id="flood-east" type="number" step="any" value="11.3"></label>
                  <label>North<input name="north" id="flood-north" type="number" step="any" value="44.4"></label>
                </div>
                <div class="row">
                  <label>Scale (m)<input name="scale" id="flood-scale" type="number" step="1" value="4000"></label>
                  <button type="submit" style="align-self:end;">Run Graph Screening</button>
                </div>
              </form>
              <div style="height:10px;"></div>
              <form id="sentinel-live-form">
                <div class="row">
                  <label>Sentinel-1 Start<input name="start_date" id="sentinel-start-date" type="date"></label>
                  <label>Sentinel-1 End<input name="end_date" id="sentinel-end-date" type="date"></label>
                </div>
                <div class="row">
                  <button type="submit" style="align-self:end;">Load Sentinel-1 Live</button>
                </div>
              </form>
            </div>

            <div id="flood-climate-fields" style="display:none;">
              <h3>Climate-Driven Flood Pilot</h3>
              <p style="color:var(--muted);font-size:13px;margin:0 0 12px;">Validation-stage workflow for Emilia-Romagna style pilots: identifies the best CMIP6 precipitation model, injects its signal into the terrain graph, and compares outputs with satellite evidence where available.</p>
              <form id="flood-climate-form">
                <div class="row">
                  <label>Latitude<input name="lat" id="flood-climate-lat" type="number" step="any" value="44.5"></label>
                  <label>Longitude<input name="lon" id="flood-climate-lon" type="number" step="any" value="11.5"></label>
                </div>
                <div class="row">
                  <label>Radius (km)<input name="radius_km" type="number" step="any" value="50"></label>
                  <label>Scale (m)<input name="scale" type="number" step="1" value="2000"></label>
                </div>
                <div class="row">
                  <label>Start Date<input name="start_date" type="date" value="2011-10-01"></label>
                  <label>End Date<input name="end_date" type="date" value="2011-11-30"></label>
                </div>
                <div class="row">
                  <label>Observed Start<input name="sentinel_start_date" type="date" value="2023-05-15"></label>
                  <label>Observed End<input name="sentinel_end_date" type="date" value="2023-05-25"></label>
                </div>
                <div class="row">
                  <label>Fast Mode
                    <select name="fast_mode">
                      <option value="true">true</option>
                      <option value="false">false</option>
                    </select>
                  </label>
                  <label>Threshold<input name="threshold" type="number" min="0.05" max="0.95" step="0.05" value="0.50"></label>
                </div>
                <div class="row">
                  <button type="submit" style="align-self:end;">Run Flood Pilot</button>
                  <button class="secondary" type="button" id="run-validation-case" style="align-self:end;">Run Validation Case</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="results-grid">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2>Operational Summary</h2>
            <p>The panel below surfaces the most relevant interpretation from the most recent request.</p>
          </div>
          <div class="badge status ok" id="request-status">Idle</div>
        </div>
        <div class="metric-grid" id="metric-grid">
          <div class="metric"><strong>0</strong><span>Reference points</span></div>
          <div class="metric"><strong>0</strong><span>Models or nodes</span></div>
          <div class="metric"><strong>0</strong><span>Edges or top score</span></div>
        </div>
        <div class="insight-list" id="insights">
          <div class="insight"><strong>Ready</strong><span>Select a point or bounding box, then run an analysis.</span></div>
        </div>
      </div>

      <div class="results-stack">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Aras Diagram</h2>
              <p>Climate runs render a live alpha-beta diagnostic view here. Flood runs keep the last diagram until the next climate request.</p>
            </div>
          </div>
          <div class="diagram-shell" id="diagram-shell">
            <div class="diagram-placeholder" id="diagram-placeholder">
              Run a climate diagnostic to generate the Aras diagram.
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Model Trust Report</h2>
              <p>Which models to trust here, and why. Tiers and skill weights come from the Aras Diagram via the Model Trust Engine; rejected models (KGE &le; &minus;0.41) earn zero weight.</p>
            </div>
            <div class="badge" id="trust-headline">Awaiting run</div>
          </div>
          <div class="table-shell" id="trust-shell">
            <div class="diagram-placeholder" style="min-height:220px;">Run a climate diagnostic to score model trust.</div>
          </div>
        </div>

        <div class="subpanel-grid">
          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>Model Ranking</h2>
                <p>Sorted by total error so the strongest model rises to the top immediately.</p>
              </div>
            </div>
            <div class="table-shell" id="ranking-shell">
              <div class="diagram-placeholder" style="min-height:260px;">Run a climate diagnostic to populate the ranking table.</div>
            </div>
          </div>

          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>Climate Time Series</h2>
                <p>Reference vs. top model trajectories across the selected period.</p>
              </div>
              <div class="panel-actions">
                <button class="secondary" type="button" id="bias-correction-toggle" disabled>Apply Bias Correction</button>
              </div>
            </div>
            <div class="chart-shell" id="series-shell">
              <div class="diagram-placeholder" style="min-height:300px;">Run a climate diagnostic to plot the reference and model series.</div>
            </div>
            <div class="legend-row" id="series-legend"></div>
            <div class="series-note" id="series-note">Bias correction is available after a climate diagnostic finishes.</div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Response Console</h2>
              <p>Raw JSON stays visible for validation, debugging, and API confidence checks.</p>
            </div>
          </div>
          <textarea id="response" readonly>{
  "message": "Run a climate or flood request from the controls above."
}</textarea>
        </div>
      </div>
    </section>

    <section class="footer-panel">
      <div class="panel-header">
        <div>
          <h2>Service Snapshot</h2>
          <p>This local console is a map-first interface on top of the same FastAPI service you can later ship to Cloud Run.</p>
        </div>
      </div>
      <div class="meta-line">
        <span class="chip">GET /healthz</span>
        <span class="chip">POST /api/climate/diagnostic</span>
        <span class="chip">POST /api/flood/graph-summary</span>
        <span class="chip">POST /api/flood/climate-driven</span>
        <span class="chip">POST /api/flood/validate-pilot</span>
        <span class="chip">POST /api/flood/sentinel-live</span>
      </div>
    </section>
  </main>

  <script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const responseBox = document.getElementById('response');
    const requestStatus = document.getElementById('request-status');
    const metricGrid = document.getElementById('metric-grid');
    const insights = document.getElementById('insights');
    const diagramShell = document.getElementById('diagram-shell');
    const diagramPlaceholder = document.getElementById('diagram-placeholder');
    const rankingShell = document.getElementById('ranking-shell');
    const trustShell = document.getElementById('trust-shell');
    const trustHeadline = document.getElementById('trust-headline');
    const seriesShell = document.getElementById('series-shell');
    const seriesLegend = document.getElementById('series-legend');
    const seriesNote = document.getElementById('series-note');
    const biasCorrectionToggle = document.getElementById('bias-correction-toggle');
    const climateTarget = document.getElementById('climate-target');
    const floodTarget = document.getElementById('flood-target');
    const mapStatus = document.getElementById('map-status');

    const climateLat = document.getElementById('climate-lat');
    const climateLon = document.getElementById('climate-lon');
    const climateRadius = document.getElementById('climate-radius');
    const floodWest = document.getElementById('flood-west');
    const floodSouth = document.getElementById('flood-south');
    const floodEast = document.getElementById('flood-east');
    const floodNorth = document.getElementById('flood-north');
    const floodScale = document.getElementById('flood-scale');
    const sentinelStartDate = document.getElementById('sentinel-start-date');
    const sentinelEndDate = document.getElementById('sentinel-end-date');
    const mapFallback = document.getElementById('map-fallback');
    const climateViewState = {
      latestClimateData: null,
      bestModelName: null,
      biasCorrectionEnabled: false,
      biasCorrectionResult: null
    };

    if (sentinelStartDate && sentinelEndDate) {
      const today = new Date();
      const end = new Date(today);
      end.setDate(today.getDate() - 1);
      const start = new Date(end);
      start.setDate(end.getDate() - 13);
      const toIsoDate = (value) => value.toISOString().slice(0, 10);
      sentinelStartDate.value = toIsoDate(start);
      sentinelEndDate.value = toIsoDate(end);
    }

    let map = null;

    if (typeof window.L === 'undefined') {
      document.getElementById('map').style.display = 'none';
      mapFallback.style.display = 'grid';
      mapStatus.textContent = 'Map library unavailable';
    } else {
      map = L.map('map', { zoomControl: true }).setView([42.5, 12.8], 5);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution: '&copy; OpenStreetMap contributors'
      }).addTo(map);

      let climateMarker = L.marker([Number(climateLat.value), Number(climateLon.value)]).addTo(map);
      let climateCircle = L.circle([Number(climateLat.value), Number(climateLon.value)], {
        radius: Number(climateRadius.value) * 1000,
        color: '#8bf0c7',
        weight: 2,
        fillColor: '#8bf0c7',
        fillOpacity: 0.14
      }).addTo(map);
      let floodRect = L.rectangle([[Number(floodSouth.value), Number(floodWest.value)], [Number(floodNorth.value), Number(floodEast.value)]], {
        color: '#ffd88a',
        weight: 2,
        fillColor: '#ffd88a',
        fillOpacity: 0.12
      }).addTo(map);

      function updateClimateVisual() {
        const lat = Number(climateLat.value);
        const lon = Number(climateLon.value);
        const radiusKm = Number(climateRadius.value);
        climateMarker.setLatLng([lat, lon]);
        climateCircle.setLatLng([lat, lon]);
        climateCircle.setRadius(radiusKm * 1000);
        climateTarget.textContent = `Lat ${lat.toFixed(4)}, Lon ${lon.toFixed(4)}, Radius ${radiusKm} km`;
      }

      function updateFloodVisual() {
        const west = Number(floodWest.value);
        const south = Number(floodSouth.value);
        const east = Number(floodEast.value);
        const north = Number(floodNorth.value);
        floodRect.setBounds([[south, west], [north, east]]);
        floodTarget.textContent = `West ${west.toFixed(3)}, South ${south.toFixed(3)}, East ${east.toFixed(3)}, North ${north.toFixed(3)}`;
      }

      updateClimateVisual();
      updateFloodVisual();

      climateLat.addEventListener('input', updateClimateVisual);
      climateLon.addEventListener('input', updateClimateVisual);
      climateRadius.addEventListener('input', updateClimateVisual);
      floodWest.addEventListener('input', updateFloodVisual);
      floodSouth.addEventListener('input', updateFloodVisual);
      floodEast.addEventListener('input', updateFloodVisual);
      floodNorth.addEventListener('input', updateFloodVisual);

      map.on('click', (event) => {
        climateLat.value = event.latlng.lat.toFixed(4);
        climateLon.value = event.latlng.lng.toFixed(4);
        updateClimateVisual();
        mapStatus.textContent = 'Climate point updated';
      });

      let dragStart = null;
      let draftRect = null;
      map.getContainer().style.cursor = 'crosshair';

      map.on('mousedown', (event) => {
        if (!event.originalEvent.shiftKey) {
          return;
        }
        dragStart = event.latlng;
        if (draftRect) {
          map.removeLayer(draftRect);
        }
        draftRect = L.rectangle([dragStart, dragStart], {
          color: '#ffb347',
          dashArray: '6 6',
          weight: 1
        }).addTo(map);
        map.dragging.disable();
        mapStatus.textContent = 'Drawing flood box';
      });

      map.on('mousemove', (event) => {
        if (!dragStart || !draftRect) {
          return;
        }
        draftRect.setBounds(L.latLngBounds(dragStart, event.latlng));
      });

      map.on('mouseup', (event) => {
        if (!dragStart) {
          return;
        }
        const bounds = L.latLngBounds(dragStart, event.latlng);
        floodWest.value = bounds.getWest().toFixed(3);
        floodSouth.value = bounds.getSouth().toFixed(3);
        floodEast.value = bounds.getEast().toFixed(3);
        floodNorth.value = bounds.getNorth().toFixed(3);
        updateFloodVisual();
        if (draftRect) {
          map.removeLayer(draftRect);
          draftRect = null;
        }
        dragStart = null;
        map.dragging.enable();
        mapStatus.textContent = 'Flood box updated';
      });

      document.getElementById('snap-rome').addEventListener('click', () => {
        climateLat.value = '41.9028';
        climateLon.value = '12.4964';
        climateRadius.value = '20';
        map.setView([41.9028, 12.4964], 8);
        updateClimateVisual();
        mapStatus.textContent = 'Reset to Rome';
      });
    }

    document.querySelectorAll('.top-tab').forEach((tab) => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.top-tab').forEach((node) => node.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('climate-card').style.display = tab.dataset.target === 'climate-card' ? 'block' : 'none';
        document.getElementById('flood-card').style.display   = tab.dataset.target === 'flood-card'   ? 'block' : 'none';
        // when switching to flood tab, restore the last active flood sub-mode
        if (tab.dataset.target === 'flood-card') {
          setFloodMode(window._lastFloodMode || 'basic');
        }
      });
    });

    function setStatus(text, kind) {
      requestStatus.textContent = text;
      requestStatus.className = `badge status ${kind}`;
    }

    function setInsights(items) {
      insights.innerHTML = items.map((item) => `<div class="insight"><strong>${item.title}</strong><span>${item.text}</span></div>`).join('');
    }

    function setMetrics(values) {
      metricGrid.innerHTML = values.map((item) => `<div class="metric"><strong>${item.value}</strong><span>${item.label}</span></div>`).join('');
    }

    function renderArasDiagram(metrics) {
      if (!metrics || !metrics.length) {
        diagramShell.innerHTML = '<div class="diagram-placeholder">No climate metrics available for diagram rendering.</div>';
        return;
      }

      const width = 760;
      const height = 500;
      const pad = 64;
      const colors = ['#8bf0c7', '#ffd88a', '#7cc8ff', '#ff9bb3', '#d8b4fe', '#fca36b', '#5eead4'];

      // BUG 3 FIX — axes were SWAPPED.
      // Paper: x-axis = β-1 (bias), y-axis = α-1 (variability).
      // Original code: toX used item.alpha, toY used item.beta — reversed.
      // Also include x_E / y_E in range so axis limits fit both points.
      const allVals = [];
      metrics.forEach((item) => {
        allVals.push(item.beta, item.alpha, item.x_E || 0, item.y_E || 0);
      });
      const maxVal = Math.max(0.5, ...allVals.map((v) => Math.abs(Number(v || 0)))) * 1.3;

      // x-axis maps β-1 (bias),  y-axis maps α-1 (variability)
      const toX = (v) => pad + ((Number(v) + maxVal) / (2 * maxVal)) * (width - pad * 2);
      const toY = (v) => height - pad - ((Number(v) + maxVal) / (2 * maxVal)) * (height - pad * 2);
      const cx0 = toX(0);
      const cy0 = toY(0);

      // BUG 5 FIX — circles should be at 10%, 25%, 50% per paper (not 0.1–0.5 evenly)
      const circleColors = ['#27ae60', '#e67e22', '#c0392b'];
      const circlePcts   = [0.10, 0.25, 0.50];
      const circles = circlePcts.map((r, i) => {
        const rr = (r * (width - pad * 2)) / (2 * maxVal);
        const lx = cx0 + rr * 0.72;
        const ly = cy0 - rr * 0.72;
        return `
          <circle cx="${cx0}" cy="${cy0}" r="${rr}" fill="none"
            stroke="${circleColors[i]}" stroke-width="1" stroke-dasharray="4 6" opacity="0.6"/>
          <text x="${lx}" y="${ly}" fill="${circleColors[i]}" font-size="10" text-anchor="middle"
            opacity="0.85">${Math.round(r * 100)}%</text>
        `;
      }).join('');

      // BUG 3+4 FIX — for each model draw THREE things:
      //   1. Segment from E_αβ (beta, alpha) → E_total (x_E, y_E)
      //   2. Filled circle at E_αβ (bias+variability error point)
      //   3. Diamond at E_total (total error point) ← THIS WAS MISSING
      const modelMarks = metrics.map((item, index) => {
        const color = colors[index % colors.length];
        // E_αβ point: x = β-1 (item.beta), y = α-1 (item.alpha)
        const ax = toX(item.beta);
        const ay = toY(item.alpha);
        // E_total point: x = x_E, y = y_E (sent from backend)
        const ex = toX(item.x_E || item.beta);
        const ey = toY(item.y_E || item.alpha);
        // Diamond path centred at (ex, ey)
        const ds = 6;
        const diamond = `M${ex},${ey - ds} L${ex + ds},${ey} L${ex},${ey + ds} L${ex - ds},${ey} Z`;
        const corr = Number(item.correlation || 0);
        const circle = corr >= 0
          ? `<circle cx="${ax}" cy="${ay}" r="7" fill="${color}" stroke="white" stroke-width="1.2"/>`
          : `<circle cx="${ax}" cy="${ay}" r="7" fill="none" stroke="${color}" stroke-width="2"/>`;
        return `
          <!-- segment E_αβ → E_total -->
          <line x1="${ax}" y1="${ay}" x2="${ex}" y2="${ey}"
            stroke="${color}" stroke-width="2" opacity="0.85"/>
          <!-- E_αβ circle (bias+variability) -->
          ${circle}
          <!-- E_total diamond (total error) — was missing -->
          <path d="${diamond}" fill="${color}" opacity="0.95" stroke="white" stroke-width="1"/>
          <!-- label -->
          <text x="${ax + 10}" y="${ay - 10}" fill="#dffcf1" font-size="11"
            font-family="Space Grotesk, sans-serif">${item.name}</text>
        `;
      }).join('');

      // Legend
      const legendItems = metrics.map((item, i) => {
        const color = colors[i % colors.length];
        return `<tspan x="0" dy="${i === 0 ? 0 : 16}" fill="${color}">● ${item.name}  KGE=${Number(item.kge).toFixed(2)}  E=${Number(item.error_total_pct).toFixed(1)}%</tspan>`;
      }).join('');

      diagramShell.innerHTML = `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Aras Diagram"
          style="width:100%;height:auto;display:block">
          <rect x="0" y="0" width="${width}" height="${height}" rx="18" fill="transparent"/>
          ${circles}
          <!-- axes -->
          <line x1="${toX(-maxVal)}" y1="${cy0}" x2="${toX(maxVal)}" y2="${cy0}"
            stroke="rgba(255,255,255,0.25)" stroke-width="1"/>
          <line x1="${cx0}" y1="${toY(-maxVal)}" x2="${cx0}" y2="${toY(maxVal)}"
            stroke="rgba(255,255,255,0.25)" stroke-width="1"/>
          <!-- origin cross -->
          <line x1="${cx0-8}" y1="${cy0}" x2="${cx0+8}" y2="${cy0}" stroke="#4fb3ff" stroke-width="2"/>
          <line x1="${cx0}" y1="${cy0-8}" x2="${cx0}" y2="${cy0+8}" stroke="#4fb3ff" stroke-width="2"/>
          <!-- quadrant labels -->
          <text x="${toX(maxVal*0.55)}" y="${toY(maxVal*0.82)}" text-anchor="middle"
            fill="rgba(255,255,255,0.2)" font-size="10">overest. mean / overest. var.</text>
          <text x="${toX(-maxVal*0.55)}" y="${toY(maxVal*0.82)}" text-anchor="middle"
            fill="rgba(255,255,255,0.2)" font-size="10">underest. mean / overest. var.</text>
          <text x="${toX(maxVal*0.55)}" y="${toY(-maxVal*0.82)}" text-anchor="middle"
            fill="rgba(255,255,255,0.2)" font-size="10">overest. mean / underest. var.</text>
          <text x="${toX(-maxVal*0.55)}" y="${toY(-maxVal*0.82)}" text-anchor="middle"
            fill="rgba(255,255,255,0.2)" font-size="10">underest. mean / underest. var.</text>
          ${modelMarks}
          <!-- axis labels -->
          <text x="${width/2}" y="${height - 14}" text-anchor="middle"
            fill="#9bc9c0" font-size="13">β − 1  =  (μ_model / μ_obs) − 1   [Bias ratio]</text>
          <text x="16" y="${height/2}" text-anchor="middle" fill="#9bc9c0" font-size="13"
            transform="rotate(-90 16 ${height/2})">α − 1  =  (σ_model / σ_obs) − 1   [Variability ratio]</text>
          <!-- legend -->
          <text x="${pad}" y="${pad - 18}" font-size="10" font-family="Space Grotesk,sans-serif">
            ${legendItems}
          </text>
          <!-- diagram title -->
          <text x="${width/2}" y="22" text-anchor="middle" fill="#8bf0c7"
            font-size="13" font-weight="600" font-family="Fraunces,serif">Aras' Diagram</text>
        </svg>
        <div style="display:flex;gap:16px;padding:6px 8px;font-size:11px;color:#9bc9c0;flex-wrap:wrap">
          <span>● Circle = E<sub>αβ</sub> (bias+variability error)</span>
          <span>◆ Diamond = E<sub>total</sub> (total error incl. correlation)</span>
          <span>— Segment length = correlation error</span>
          <span style="color:#27ae60">— 10%</span>
          <span style="color:#e67e22">— 25%</span>
          <span style="color:#c0392b">— 50%</span>
        </div>
      `;
    }

    function renderTrustReport(trust) {
      if (!trust || !trust.models || !trust.models.length) {
        trustShell.innerHTML = '<div class="diagram-placeholder" style="min-height:220px;">No trust report available.</div>';
        trustHeadline.textContent = 'No data';
        return;
      }
      const tierColor = { trusted: '#27ae60', usable: '#8bf0c7', weak: '#e67e22', reject: '#ff8f8f' };
      const summary = trust.summary || {};
      const rows = [...trust.models].sort((a, b) => b.weight - a.weight);

      trustHeadline.textContent = `${summary.n_kept || 0}/${summary.n_models || rows.length} kept · best ${summary.best_model || '-'}`;

      const body = rows.map((m) => {
        const color = tierColor[m.trust_tier] || '#9bc9c0';
        const pct = Math.round((Number(m.weight) || 0) * 100);
        const attr = m.error_attribution || {};
        const dom = m.trust_tier === 'reject' ? '—' : (attr.dominant || '-');
        return `
          <tr>
            <td>${m.name}</td>
            <td><span class="chip" style="color:${color};border-color:${color};background:rgba(255,255,255,0.03);text-transform:capitalize;">${m.trust_tier}</span></td>
            <td>${Number(m.kge).toFixed(2)}</td>
            <td>
              <div style="display:flex;align-items:center;gap:8px;">
                <div style="flex:1;height:8px;border-radius:999px;background:rgba(255,255,255,0.08);overflow:hidden;">
                  <div style="width:${pct}%;height:100%;background:${color};"></div>
                </div>
                <span style="min-width:34px;text-align:right;">${pct}%</span>
              </div>
            </td>
            <td style="text-transform:capitalize;">${dom}</td>
          </tr>`;
      }).join('');

      trustShell.innerHTML = `
        <table>
          <thead>
            <tr><th>Model</th><th>Trust</th><th>KGE</th><th>Skill weight</th><th>Fix first</th></tr>
          </thead>
          <tbody>${body}</tbody>
        </table>
        <div class="series-note" style="padding:12px 14px;">${summary.recommendation || ''}</div>
      `;
    }

    function renderRankingTable(metrics) {
      if (!metrics || !metrics.length) {
        rankingShell.innerHTML = '<div class="diagram-placeholder" style="min-height:260px;">No model ranking available.</div>';
        return;
      }
      const ordered = [...metrics].sort((a, b) => a.error_total_pct - b.error_total_pct);
      rankingShell.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Model</th>
              <th>Error %</th>
              <th>Alpha</th>
              <th>Beta</th>
              <th>Corr</th>
            </tr>
          </thead>
          <tbody>
            ${ordered.map((item, index) => `
              <tr>
                <td><strong>${index + 1}</strong></td>
                <td>${item.name}</td>
                <td>${Number(item.error_total_pct).toFixed(2)}</td>
                <td>${Number(item.alpha).toFixed(3)}</td>
                <td>${Number(item.beta).toFixed(3)}</td>
                <td>${Number(item.correlation).toFixed(3)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }

    function buildLinePath(points, width, height, pad, minVal, maxVal) {
      const toX = (index, total) => pad + (index / Math.max(total - 1, 1)) * (width - pad * 2);
      const toY = (value) => height - pad - ((value - minVal) / Math.max(maxVal - minVal, 1e-9)) * (height - pad * 2);
      return points.map((value, index) => `${index === 0 ? 'M' : 'L'} ${toX(index, points.length)} ${toY(value)}`).join(' ');
    }

    function renderSeriesChart(referenceSeries, modelSeries, bestModelName, options = {}) {
      const referenceEntries = Object.entries(referenceSeries || {});
      if (!referenceEntries.length || !bestModelName || !modelSeries || !modelSeries[bestModelName]) {
        seriesShell.innerHTML = '<div class="diagram-placeholder" style="min-height:300px;">No time series available.</div>';
        seriesLegend.innerHTML = '';
        seriesNote.textContent = 'Bias correction is available after a climate diagnostic finishes.';
        return;
      }

      const modelEntries = Object.entries(modelSeries[bestModelName]);
      const mergedDates = referenceEntries
        .map(([date]) => date)
        .filter((date) => Object.prototype.hasOwnProperty.call(modelSeries[bestModelName], date));
      const refValues = mergedDates.map((date) => Number(referenceSeries[date]));
      const modelValues = mergedDates.map((date) => Number(modelSeries[bestModelName][date]));
      const correction = options.biasCorrectionResult || null;
      const correctedValues = options.applyBiasCorrection && correction ? correction.corrected_values.map((value) => Number(value)) : null;
      const allValues = correctedValues ? [...refValues, ...modelValues, ...correctedValues] : [...refValues, ...modelValues];
      const minVal = Math.min(...allValues);
      const maxVal = Math.max(...allValues);
      const width = 760;
      const height = 340;
      const pad = 42;
      const refPath = buildLinePath(refValues, width, height, pad, minVal, maxVal);
      const modelPath = buildLinePath(modelValues, width, height, pad, minVal, maxVal);
      const correctedPath = correctedValues ? buildLinePath(correctedValues, width, height, pad, minVal, maxVal) : null;

      seriesShell.innerHTML = `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Climate time series">
          <rect x="0" y="0" width="${width}" height="${height}" rx="18" fill="transparent"></rect>
          <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" stroke="rgba(255,255,255,0.2)" />
          <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" stroke="rgba(255,255,255,0.2)" />
          <path d="${refPath}" fill="none" stroke="#8bf0c7" stroke-width="3" />
          <path d="${modelPath}" fill="none" stroke="#ffd88a" stroke-width="3" />
          ${correctedPath ? `<path d="${correctedPath}" fill="none" stroke="#7cc8ff" stroke-width="3" stroke-dasharray="10 8" />` : ''}
          <text x="${pad}" y="${pad - 12}" fill="#9bc9c0" font-size="12">Max ${maxVal.toFixed(2)}</text>
          <text x="${pad}" y="${height - 16}" fill="#9bc9c0" font-size="12">Min ${minVal.toFixed(2)}</text>
          <text x="${width / 2}" y="${height - 10}" text-anchor="middle" fill="#9bc9c0" font-size="12">${mergedDates[0]} to ${mergedDates[mergedDates.length - 1]}</text>
        </svg>
      `;
      seriesLegend.innerHTML = `
        <div class="legend-item"><span class="legend-swatch" style="background:#8bf0c7;"></span>Reference</div>
        <div class="legend-item"><span class="legend-swatch" style="background:#ffd88a;"></span>${bestModelName}</div>
        ${correctedPath ? '<div class="legend-item"><span class="legend-swatch" style="background:#7cc8ff;"></span>Bias-corrected best model</div>' : ''}
      `;
      seriesNote.textContent = correctedPath && correction
        ? `${correction.method}. MAE ${Number(correction.raw_mae).toFixed(3)} -> ${Number(correction.corrected_mae).toFixed(3)} (${Number(correction.improvement_pct).toFixed(1)}% improvement) after ${correction.epochs} epochs.`
        : `Showing the raw top-ranked model (${bestModelName}). Click "Apply Bias Correction" to run the climate GNN against the selected best model.`;
    }

    function rerenderClimateSeries() {
      if (!climateViewState.latestClimateData || !climateViewState.bestModelName) {
        return;
      }
      renderSeriesChart(
        climateViewState.latestClimateData.reference_series,
        climateViewState.latestClimateData.model_series,
        climateViewState.bestModelName,
        {
          applyBiasCorrection: climateViewState.biasCorrectionEnabled,
          biasCorrectionResult: climateViewState.biasCorrectionResult
        }
      );
    }

    async function runGnnBiasCorrection() {
      if (!climateViewState.latestClimateData || !climateViewState.bestModelName) {
        return;
      }

      biasCorrectionToggle.disabled = true;
      biasCorrectionToggle.textContent = 'Running GNN Correction...';
      seriesNote.textContent = `Training a temporal GNN for ${climateViewState.bestModelName}.`;

      try {
        const response = await fetch('/api/climate/bias-correct', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            reference_series: climateViewState.latestClimateData.reference_series,
            model_series: climateViewState.latestClimateData.model_series,
            best_model_name: climateViewState.bestModelName
          })
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data && data.detail ? data.detail : `HTTP ${response.status}`);
        }
        climateViewState.biasCorrectionResult = data.correction;
        climateViewState.biasCorrectionEnabled = true;
        biasCorrectionToggle.textContent = 'Show Raw Model';
        rerenderClimateSeries();
      } catch (error) {
        climateViewState.biasCorrectionResult = null;
        climateViewState.biasCorrectionEnabled = false;
        biasCorrectionToggle.textContent = 'Apply Bias Correction';
        seriesNote.textContent = `GNN bias correction failed: ${error.message}`;
      } finally {
        biasCorrectionToggle.disabled = false;
      }
    }

    async function submitJson(url, payload, mode) {
      setStatus('Running', 'ok');
      responseBox.value = JSON.stringify({ loading: true, url, payload }, null, 2);
      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const text = await response.text();
        let data = null;
        try {
          data = JSON.parse(text);
          responseBox.value = JSON.stringify(data, null, 2);
        } catch {
          responseBox.value = text;
        }
        if (!response.ok) {
          throw new Error(data && data.detail ? data.detail : `HTTP ${response.status}`);
        }
        if (mode === 'climate') {
          const best = data.metrics && data.metrics.length ? data.metrics.reduce((a, b) => (a.error_total_pct < b.error_total_pct ? a : b)) : null;
          climateViewState.latestClimateData = data;
          climateViewState.bestModelName = best ? best.name : null;
          climateViewState.biasCorrectionEnabled = false;
          climateViewState.biasCorrectionResult = null;
          biasCorrectionToggle.disabled = !best;
          biasCorrectionToggle.textContent = 'Apply Bias Correction';
          renderArasDiagram(data.metrics);
          renderTrustReport(data.trust);
          renderRankingTable(data.metrics);
          rerenderClimateSeries();
          setMetrics([
            { value: String(data.reference_points || 0), label: 'Reference points' },
            { value: String((data.models || []).length), label: 'Models benchmarked' },
            { value: best ? best.name : '-', label: 'Lowest error model' }
          ]);
          setInsights([
            { title: 'Climate run completed', text: `Fetched ${data.reference_points || 0} reference points for the selected ROI.` },
            { title: 'Best current model', text: best ? `${best.name} with ${best.error_total_pct.toFixed(2)}% total error.` : 'No model metrics returned.' },
            { title: 'Coverage', text: `Variable ${payload.variable} from ${payload.start_date} to ${payload.end_date}.` }
          ]);
        } else {
          if (mode === 'sentinel') {
            setMetrics([
              { value: String(data.image_count || 0), label: 'S1 scenes' },
              { value: String(data.flooded_cells_count || 0), label: 'Flooded cells' },
              { value: `${data.rows || 0} x ${data.cols || 0}`, label: 'Mask grid' }
            ]);
            setInsights([
              { title: 'Sentinel-1 live mask', text: `${data.image_count || 0} SAR scenes processed from ${payload.start_date} to ${payload.end_date}.` },
              { title: 'Flood extent', text: `${Number(data.flooded_fraction_pct || 0).toFixed(2)}% of sampled cells flagged as flooded within the selected bounding box.` },
              { title: 'Selected extent', text: `West ${payload.west}, South ${payload.south}, East ${payload.east}, North ${payload.north}.` }
            ]);
            renderSentinelFloodMask(data.flooded_cells || []);
          } else {
          if (mode === 'flood-validation') {
            const counts = data.counts || {};
            const metrics = data.metrics || {};
            setMetrics([
              { value: `${(Number(metrics.iou || 0) * 100).toFixed(1)}%`, label: 'IoU overlap' },
              { value: `${(Number(metrics.recall || 0) * 100).toFixed(1)}%`, label: 'Sentinel recall' },
              { value: String(data.sentinel_image_count || 0), label: 'S1 scenes' }
            ]);
            setInsights([
              { title: 'Validation case completed', text: `${counts.true_positive || 0} overlap cells, ${counts.false_positive || 0} screening-only cells, ${counts.false_negative || 0} Sentinel-only cells.` },
              { title: 'Screening threshold', text: `GNN nodes were flagged at p >= ${Number(data.threshold || 0).toFixed(2)}. Precision ${(Number(metrics.precision || 0) * 100).toFixed(1)}%, agreement ${(Number(metrics.agreement || 0) * 100).toFixed(1)}%.` },
              { title: 'Climate context', text: `${data.best_model || '-'} selected with KGE=${Number(data.kge || 0).toFixed(3)} and precip anomaly ${Number(data.precip_anomaly || 0).toFixed(3)}.` }
            ]);
            if (data.node_flood_probs && data.node_flood_probs.length) {
              renderFloodRiskMap(data.node_flood_probs, data.grid_shape);
            }
            renderSentinelFloodMask(data.sentinel_flooded_cells || []);
          } else {
          if (mode === 'flood-climate') {
            setMetrics([
              { value: String(data.graph_nodes || 0), label: 'Graph nodes' },
              { value: String(data.graph_edges || 0), label: 'Hydro edges' },
              { value: data.best_model || '-', label: 'Best CMIP6 model' }
            ]);
            setInsights([
              { title: 'Best precipitation model', text: `${data.best_model} selected by Aras diagram (KGE=${Number(data.kge||0).toFixed(3)}, E=${Number(data.error_pct||0).toFixed(1)}%).` },
              { title: 'Climate signal injected', text: `Precip mean ${Number(data.precip_mean||0).toFixed(2)} mm/day, anomaly ${Number(data.precip_anomaly||0).toFixed(3)} vs ERA5 mean ${Number(data.era5_mean||0).toFixed(2)} mm/day.` },
              { title: 'Flood graph', text: `${data.graph_nodes||0} nodes, ${data.graph_edges||0} edges. Grid ${(data.grid_shape||[0,0])[0]} × ${(data.grid_shape||[0,0])[1]}.${data.flood_risk_pct !== undefined ? ' GNN screening flag: ' + Number(data.flood_risk_pct).toFixed(1) + '% of nodes.' : ''}` }
            ]);
            if (data.all_metrics && data.all_metrics.length) {
              renderArasDiagram(data.all_metrics);
              renderRankingTable(data.all_metrics);
            }
            // Render flood screening nodes on the Leaflet map
            if (data.node_flood_probs && data.node_flood_probs.length) {
              renderFloodRiskMap(data.node_flood_probs, data.grid_shape);
            } else {
              mapStatus.textContent = data.gnn_error
                ? `Flood map unavailable: ${data.gnn_error}`
                : 'Flood map unavailable: no node probabilities returned';
            }
          } else {
            setMetrics([
              { value: String(data.nodes || 0), label: 'Graph nodes' },
              { value: String(data.edges || 0), label: 'Hydro edges' },
              { value: `${data.rows || 0} x ${data.cols || 0}`, label: 'Grid shape' }
            ]);
            setInsights([
              { title: 'Flood graph created', text: `Built topology across ${data.rows || 0} rows and ${data.cols || 0} columns.` },
              { title: 'Terrain summary', text: `Mean normalized elevation ${Number(data.mean_normalized_elevation || 0).toFixed(3)}, slope ${Number(data.mean_normalized_slope || 0).toFixed(3)}.` },
              { title: 'Selected extent', text: `West ${payload.west}, South ${payload.south}, East ${payload.east}, North ${payload.north}.` }
            ]);
          }
          }
          }
        }
        setStatus('Success', 'ok');
      } catch (error) {
        setStatus('Error', 'error');
        if (mode === 'climate') {
          climateViewState.latestClimateData = null;
          climateViewState.bestModelName = null;
          climateViewState.biasCorrectionEnabled = false;
          climateViewState.biasCorrectionResult = null;
          biasCorrectionToggle.disabled = true;
          biasCorrectionToggle.textContent = 'Apply Bias Correction';
          seriesNote.textContent = 'Bias correction is available after a climate diagnostic finishes.';
        }
        setInsights([
          { title: 'Request failed', text: error.message },
          { title: 'Check inputs', text: 'Verify the selected dates, geometry, and Earth Engine availability.' }
        ]);
        setMetrics([
          { value: '0', label: 'Valid output' },
          { value: '1', label: 'Request attempted' },
          { value: 'ERR', label: 'Status' }
        ]);
      }
    }

    biasCorrectionToggle.addEventListener('click', () => {
      if (!climateViewState.latestClimateData || !climateViewState.bestModelName) {
        return;
      }
      if (climateViewState.biasCorrectionResult) {
        climateViewState.biasCorrectionEnabled = !climateViewState.biasCorrectionEnabled;
        biasCorrectionToggle.textContent = climateViewState.biasCorrectionEnabled ? 'Show Raw Model' : 'Show GNN Correction';
        rerenderClimateSeries();
        return;
      }
      runGnnBiasCorrection();
    });

    document.getElementById('climate-form').addEventListener('submit', (event) => {
      event.preventDefault();
      const form = new FormData(event.target);
      submitJson('/api/climate/diagnostic', {
        lat: Number(form.get('lat')),
        lon: Number(form.get('lon')),
        radius_km: Number(form.get('radius_km')),
        start_date: form.get('start_date'),
        end_date: form.get('end_date'),
        variable: form.get('variable'),
        ref_dataset: form.get('ref_dataset'),
        fast_mode: form.get('fast_mode') === 'true'
      }, 'climate');
    });

    document.getElementById('flood-form').addEventListener('submit', (event) => {
      event.preventDefault();
      const form = new FormData(event.target);
      submitJson('/api/flood/graph-summary', {
        west: Number(form.get('west')),
        south: Number(form.get('south')),
        east: Number(form.get('east')),
        north: Number(form.get('north')),
        scale: Number(form.get('scale'))
      }, 'flood');
    });

    const sentinelLiveForm = document.getElementById('sentinel-live-form');
    if (sentinelLiveForm) {
      sentinelLiveForm.addEventListener('submit', (event) => {
        event.preventDefault();
        submitJson('/api/flood/sentinel-live', {
          west: Number(floodWest.value),
          south: Number(floodSouth.value),
          east: Number(floodEast.value),
          north: Number(floodNorth.value),
          start_date: sentinelStartDate.value,
          end_date: sentinelEndDate.value,
          scale: Number(floodScale.value)
        }, 'sentinel');
      });
    }

    // Flood mode toggle
    function setFloodMode(mode) {
      window._lastFloodMode = mode;
      document.getElementById('flood-basic-fields').style.display   = mode === 'basic'   ? 'block' : 'none';
      document.getElementById('flood-climate-fields').style.display = mode === 'climate' ? 'block' : 'none';
      document.getElementById('flood-mode-basic').classList.toggle('active',   mode === 'basic');
      document.getElementById('flood-mode-climate').classList.toggle('active', mode === 'climate');
    }

    // Flood screening map renderer.
    let floodRiskLayer = null;
    let sentinelFloodLayer = null;

    function renderFloodRiskMap(nodeProbs, gridShape) {
      if (!map) {
        mapStatus.textContent = 'Flood map unavailable: map is not initialized';
        return;
      }
      // Remove previous flood layer
      if (floodRiskLayer) {
        map.removeLayer(floodRiskLayer);
        floodRiskLayer = null;
      }
      const existingLegend = document.getElementById('flood-legend');
      if (existingLegend) existingLegend.remove();
      if (!nodeProbs || !nodeProbs.length) return;

      // Sample nodes for performance — render max 800 circles
      // Pick only moderate/high risk nodes + random sample of low risk
      const highRisk  = nodeProbs.filter(n => n.p >= 0.35);
      const lowRisk   = nodeProbs.filter(n => n.p <  0.35);
      const lowSample = lowRisk.filter((_, i) => i % Math.ceil(lowRisk.length / 200) === 0);
      const sample    = [...highRisk, ...lowSample];

      // Compute bounds from full dataset
      const lats = nodeProbs.map(n => n.lat);
      const lons = nodeProbs.map(n => n.lon);
      const minLat = Math.min(...lats), maxLat = Math.max(...lats);
      const minLon = Math.min(...lons), maxLon = Math.max(...lons);

      // Radius: fixed based on grid size (avoids map.getSize() scope issue)
      const rows = gridShape ? gridShape[0] : 50;
      const cols = gridShape ? gridShape[1] : 50;
      const latSpan = maxLat - minLat || 1;
      const radiusM = Math.max(600, Math.min(2500, (latSpan * 111320) / rows * 0.55));

      const layers = sample.map((node) => {
        const p = node.p;
        let color, fillOpacity;
        if      (p >= 0.80) { color = '#c0392b'; fillOpacity = 0.85; }
        else if (p >= 0.60) { color = '#e67e22'; fillOpacity = 0.70; }
        else if (p >= 0.35) { color = '#f39c12'; fillOpacity = 0.55; }
        else                { color = '#27ae60'; fillOpacity = 0.20; }
        return L.circle([node.lat, node.lon], {
          radius     : radiusM,
          color      : color,
          fillColor  : color,
          fillOpacity: fillOpacity,
          weight     : 0,
        }).bindTooltip(
          `<b>Screening probability: ${(p * 100).toFixed(1)}%</b><br>` +
          `${p >= 0.80 ? '🔴 Very high' : p >= 0.60 ? '🟠 High' : p >= 0.35 ? '🟡 Moderate' : '🟢 Low'}`,
          { sticky: true }
        );
      });

      floodRiskLayer = L.layerGroup(layers).addTo(map);
      mapStatus.textContent = `Rendered flood screening layer for ${nodeProbs.length} nodes`;

      // Zoom to show the flood area at a useful zoom level (zoom 9-10)
      map.fitBounds(
        [[minLat, minLon], [maxLat, maxLon]],
        { padding: [20, 20], maxZoom: 10 }
      );

      // Legend
      const legend = L.control({ position: 'bottomright' });
      legend.onAdd = () => {
        const div = L.DomUtil.create('div', '');
        div.id = 'flood-legend';
        div.style.cssText = 'background:rgba(0,0,0,0.78);padding:10px 14px;border-radius:8px;color:white;font-size:12px;line-height:1.9;font-family:sans-serif;min-width:170px';
        const hi = nodeProbs.filter(n=>n.p>=0.60).length;
        const med = nodeProbs.filter(n=>n.p>=0.35&&n.p<0.60).length;
        div.innerHTML = `
          <b style="font-size:13px">Flood Screening Map</b><br>
          <span style="color:#c0392b">●</span> Very high ≥80% <br>
          <span style="color:#e67e22">●</span> High 60–80%<br>
          <span style="color:#f39c12">●</span> Moderate 35–60%<br>
          <span style="color:#27ae60">●</span> Low &lt;35%<br>
          <hr style="border-color:rgba(255,255,255,0.2);margin:4px 0">
          <span style="font-size:10px;color:#aaa">
            ${hi} high-screening nodes (${(hi/nodeProbs.length*100).toFixed(0)}%)<br>
            ${nodeProbs.length} total nodes • 2 km grid
          </span>`;
        return div;
      };
      legend.addTo(map);
    }

    function renderSentinelFloodMask(floodedCells) {
      if (!map) {
        mapStatus.textContent = 'Sentinel-1 overlay unavailable: map is not initialized';
        return;
      }
      if (sentinelFloodLayer) {
        map.removeLayer(sentinelFloodLayer);
        sentinelFloodLayer = null;
      }
      const existingLegend = document.getElementById('sentinel-legend');
      if (existingLegend) existingLegend.remove();
      if (!floodedCells || !floodedCells.length) {
        mapStatus.textContent = 'Sentinel-1 loaded: no flooded cells detected for the selected window';
        return;
      }

      const layers = floodedCells.map((cell) => L.rectangle(
        [[cell.south, cell.west], [cell.north, cell.east]],
        {
          color: '#5fd2ff',
          fillColor: '#1e90ff',
          fillOpacity: 0.34,
          weight: 0.6,
        }
      ));
      sentinelFloodLayer = L.layerGroup(layers).addTo(map);

      const lats = floodedCells.flatMap((cell) => [cell.south, cell.north]);
      const lons = floodedCells.flatMap((cell) => [cell.west, cell.east]);
      map.fitBounds(
        [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]],
        { padding: [20, 20], maxZoom: 11 }
      );

      const legend = L.control({ position: 'bottomleft' });
      legend.onAdd = () => {
        const div = L.DomUtil.create('div', '');
        div.id = 'sentinel-legend';
        div.style.cssText = 'background:rgba(0,0,0,0.78);padding:10px 14px;border-radius:8px;color:white;font-size:12px;line-height:1.7;font-family:sans-serif;min-width:170px';
        div.innerHTML = `
          <b style="font-size:13px">Sentinel-1 Live</b><br>
          <span style="color:#5fd2ff">■</span> SAR-derived flood mask<br>
          <span style="font-size:10px;color:#aaa">${floodedCells.length} flooded cells rendered</span>
        `;
        return div;
      };
      legend.addTo(map);
      mapStatus.textContent = `Rendered Sentinel-1 overlay with ${floodedCells.length} flooded cells`;
    }
    // ─────────────────────────────────────────────────────────────

    // Climate-driven flood form submit
    const floodClimateForm = document.getElementById('flood-climate-form');
    if (floodClimateForm) {
      floodClimateForm.addEventListener('submit', (event) => {
        event.preventDefault();
        const form = new FormData(event.target);
        submitJson('/api/flood/climate-driven', {
          lat:        Number(form.get('lat')),
          lon:        Number(form.get('lon')),
          radius_km:  Number(form.get('radius_km')),
          start_date: form.get('start_date'),
          end_date:   form.get('end_date'),
          scale:      Number(form.get('scale')),
          fast_mode:  form.get('fast_mode') === 'true'
        }, 'flood-climate');
      });

      const validationButton = document.getElementById('run-validation-case');
      if (validationButton) {
        validationButton.addEventListener('click', () => {
          const form = new FormData(floodClimateForm);
          submitJson('/api/flood/validate-pilot', {
            lat:                 Number(form.get('lat')),
            lon:                 Number(form.get('lon')),
            radius_km:           Number(form.get('radius_km')),
            start_date:          form.get('start_date'),
            end_date:            form.get('end_date'),
            sentinel_start_date: form.get('sentinel_start_date'),
            sentinel_end_date:   form.get('sentinel_end_date'),
            scale:               Number(form.get('scale')),
            threshold:           Number(form.get('threshold')),
            fast_mode:           form.get('fast_mode') === 'true'
          }, 'flood-validation');
        });
      }
    }
  </script>
</body>
</html>"""


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return get_earth_engine_status()


@app.post("/api/climate/diagnostic")
def climate_diagnostic(payload: ClimateDiagnosticRequest) -> dict:
    if payload.start_date > payload.end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date.")

    try:
        project_id = initialize_earth_engine()
        roi = ee.Geometry.Point([payload.lon, payload.lat]).buffer(payload.radius_km * 1000)
        fetcher = ArasenseDataFetcher(project_id)
        results = fetcher.get_climate_data(
            geometry=roi,
            start_date=payload.start_date.isoformat(),
            end_date=payload.end_date.isoformat(),
            variable=payload.variable,
            ref_dataset=payload.ref_dataset,
            fast_mode=payload.fast_mode,
        )
        if not results:
            raise HTTPException(status_code=404, detail="No climate data returned for the selected inputs.")

        # BUG 1 FIX: results has a top-level 'reference' key from fixed
        # data_fetcher.py. Original code did results[model_names[0]]["reference"]
        # which would use 'reference' as a model name and crash.
        model_names = [k for k in results.keys() if k != "reference"]
        if not model_names:
            raise HTTPException(status_code=404, detail="No CMIP6 model data returned.")
        reference_series = results["reference"]
        aligned_ref = results[model_names[0]]["reference"].values
        model_series = [results[name]["model"].values for name in model_names]
        aras = ArasDiagram(aligned_ref, model_series, model_names)
        trust = ModelTrustEngine(aras=aras)

        metrics = []
        for item in aras.results:
            metrics.append(
                {
                    "name": item["name"],
                    "alpha": float(item["alpha"]),      # variability ratio-1 (y-axis)
                    "beta": float(item["beta"]),        # bias ratio-1 (x-axis)
                    "x_E": float(item["x_E"]),          # BUG 2 FIX: E_total x coord
                    "y_E": float(item["y_E"]),          # BUG 2 FIX: E_total y coord
                    "correlation": float(item["r"]),
                    "kge": float(item["kge"]),
                    "error_total_pct": float(item["e_pct"]),  # BUG 2 FIX: was item["e_total"]
                }
            )

        return {
            "project_id": project_id,
            "input": model_to_dict(payload),
            "reference_points": int(len(reference_series)),
            "models": model_names,
            "metrics": metrics,
            "trust": {
                "summary": trust.summary(),
                "models": trust.reports,
            },
            "reference_series": {
                idx.strftime("%Y-%m-%d"): float(value) for idx, value in reference_series.items()
            },
            "model_series": {
                name: {
                    idx.strftime("%Y-%m-%d"): float(value)
                    for idx, value in results[name]["model"].items()
                }
                for name in model_names
            },
        }
    except HTTPException:
        raise
    except ValueError as exc:
        # Domain guards (e.g. Aras bias ratio β undefined for a zero-mean / non-Kelvin
        # variable, or a constant reference series) raise ValueError. These are caused
        # by the request inputs, not a server fault, so return 400 with the reason.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/climate/trust-report")
def climate_trust_report(payload: ClimateDiagnosticRequest) -> dict:
    """
    Arasense Model Trust Engine: for the requested location/variable, score the
    CMIP6 ensemble with the Aras Diagram, classify each model (trusted/usable/
    weak/reject), attribute its dominant error mode, and return skill weights
    plus an ensemble-level recommendation. This is the 'which models do I
    trust here, and why' decision layer.
    """
    if payload.start_date > payload.end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date.")

    try:
        project_id = initialize_earth_engine()
        roi = ee.Geometry.Point([payload.lon, payload.lat]).buffer(payload.radius_km * 1000)
        fetcher = ArasenseDataFetcher(project_id)
        results = fetcher.get_climate_data(
            geometry=roi,
            start_date=payload.start_date.isoformat(),
            end_date=payload.end_date.isoformat(),
            variable=payload.variable,
            ref_dataset=payload.ref_dataset,
            fast_mode=payload.fast_mode,
        )
        if not results:
            raise HTTPException(status_code=404, detail="No climate data returned for the selected inputs.")

        model_names = [k for k in results.keys() if k != "reference"]
        if not model_names:
            raise HTTPException(status_code=404, detail="No CMIP6 model data returned.")

        aligned_ref = results[model_names[0]]["reference"].values
        model_series = [results[name]["model"].values for name in model_names]
        engine = ModelTrustEngine(aligned_ref, model_series, model_names)

        return {
            "project_id": project_id,
            "input": model_to_dict(payload),
            "summary": engine.summary(),
            "models": engine.reports,
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/climate/projection")
def climate_projection(payload: ClimateProjectionRequest) -> dict:
    """
    Forward-looking, trust-weighted climate projection — the defensible hazard
    layer. Scores CMIP6 models against the observed historical climatology with
    the Model Trust Engine, keeps the trusted ones, and projects the change in a
    hazard metric (mean / p95 / heavy-precip fraction) into a future scenario
    window, with an across-model uncertainty band.
    """
    if payload.hist_start > payload.hist_end or payload.future_start > payload.future_end:
        raise HTTPException(status_code=400, detail="start dates must precede end dates.")

    try:
        project_id = initialize_earth_engine()
        roi = ee.Geometry.Point([payload.lon, payload.lat]).buffer(payload.radius_km * 1000)
        fetcher = ArasenseDataFetcher(project_id)

        # 1. Historical monthly climatology -> score model trust (which models are
        #    skilful at this location's seasonal cycle and magnitude).
        ref_hist, hist_models = fetcher.get_monthly_series(
            geometry=roi,
            start_date=payload.hist_start.isoformat(),
            end_date=payload.hist_end.isoformat(),
            variable=payload.variable,
            fast_mode=payload.fast_mode,
            include_reference=True,
        )
        if ref_hist is None or ref_hist.empty or not hist_models:
            raise HTTPException(status_code=404, detail="No historical climate data returned.")
        hist_df = pd.DataFrame({"reference": ref_hist, **hist_models}).dropna()
        if hist_df.shape[0] < 6:
            raise HTTPException(status_code=404, detail="Too few overlapping months for a robust climatology.")
        model_names = [c for c in hist_df.columns if c != "reference"]

        engine = ModelTrustEngine(hist_df["reference"].values,
                                  [hist_df[n].values for n in model_names], model_names)
        trusted = [r for r in engine.reports if r["weight"] > 0]
        if not trusted:
            raise HTTPException(status_code=400, detail="No model is trustworthy here (all KGE <= -0.41).")
        trusted_names = [r["name"] for r in trusted]
        report_by = {r["name"]: r for r in trusted}

        # 2. Historical vs future value of the chosen metric, for trusted models.
        #    "mean" uses the (fast) monthly series; extremes (p95/rx1day/heavy
        #    precip) are computed server-side from DAILY data — where the real
        #    Mediterranean signal lives.
        if payload.metric == "mean":
            _, fut_m = fetcher.get_monthly_series(
                geometry=roi, start_date=payload.future_start.isoformat(),
                end_date=payload.future_end.isoformat(), variable=payload.variable,
                models=trusted_names, fast_mode=payload.fast_mode)
            hist_val = {n: float(hist_df[n].mean()) for n in trusted_names}
            fut_val = {n: float(fut_m[n].mean()) for n in trusted_names
                       if n in fut_m and not fut_m[n].empty}
        else:
            stat = {"p95": "p95", "rx1day": "rx1day", "heavy_precip_frac": "heavy_frac"}[payload.metric]
            hist_val = fetcher.get_extreme_stat(
                geometry=roi, start_date=payload.hist_start.isoformat(),
                end_date=payload.hist_end.isoformat(), variable=payload.variable,
                models=trusted_names, stat=stat)
            fut_val = fetcher.get_extreme_stat(
                geometry=roi, start_date=payload.future_start.isoformat(),
                end_date=payload.future_end.isoformat(), variable=payload.variable,
                models=trusted_names, stat=stat)

        per_model = [
            {"name": n, "weight": report_by[n]["weight"], "trust_tier": report_by[n]["trust_tier"],
             "historical": hist_val[n], "future": fut_val[n]}
            for n in trusted_names if n in hist_val and n in fut_val
        ]
        if not per_model:
            raise HTTPException(status_code=404, detail="No trusted models present in both windows.")

        proj = weighted_projection(per_model, payload.metric, len(engine.reports), engine.summary())

        return {
            "project_id": project_id,
            "input": model_to_dict(payload),
            "windows": {
                "historical": [payload.hist_start.isoformat(), payload.hist_end.isoformat()],
                "future": [payload.future_start.isoformat(), payload.future_end.isoformat()],
            },
            "projection": proj,
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/climate/bias-correct")
def climate_bias_correct(payload: ClimateBiasCorrectionRequest) -> dict:
    try:
        if payload.best_model_name not in payload.model_series:
            raise HTTPException(status_code=400, detail="best_model_name was not found in model_series.")

        reference_series = payload.reference_series
        best_model_series = payload.model_series[payload.best_model_name]
        merged_dates = sorted(set(reference_series.keys()) & set(best_model_series.keys()))
        if len(merged_dates) < 3:
            raise HTTPException(status_code=400, detail="At least three overlapping dates are required for GNN bias correction.")

        reference_values = [float(reference_series[date]) for date in merged_dates]
        raw_model_values = [float(best_model_series[date]) for date in merged_dates]

        corrector = ClimateBiasCorrector()
        correction = corrector.correct(reference_values, raw_model_values)
        corrected_series = {
            date: float(value) for date, value in zip(merged_dates, correction["corrected_values"])
        }

        return {
            "best_model_name": payload.best_model_name,
            "dates": merged_dates,
            "correction": {
                "method": correction["method"],
                "epochs": correction["epochs"],
                "learning_rate": correction["learning_rate"],
                "raw_mae": correction["raw_mae"],
                "corrected_mae": correction["corrected_mae"],
                "improvement_pct": correction["improvement_pct"],
                "raw_mean": correction["raw_mean"],
                "corrected_mean": correction["corrected_mean"],
                "reference_mean": correction["reference_mean"],
                "corrected_values": correction["corrected_values"],
            },
            "corrected_series": corrected_series,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/flood/graph-summary")
def flood_graph_summary(payload: FloodGraphRequest) -> dict:
    if payload.west >= payload.east or payload.south >= payload.north:
        raise HTTPException(status_code=400, detail="Bounding box is invalid.")

    try:
        project_id = initialize_earth_engine()
        region = ee.Geometry.Rectangle([payload.west, payload.south, payload.east, payload.north])
        builder = ArasenseGraphBuilder(project_id)
        graph, shape = builder.build_hydrological_graph(region, scale=payload.scale)

        feature_means = graph.x.mean(dim=0).tolist() if graph.x.numel() else [0.0, 0.0]
        return {
            "project_id": project_id,
            "input": model_to_dict(payload),
            "rows": int(shape[0]),
            "cols": int(shape[1]),
            "nodes": int(graph.num_nodes),
            "edges": int(graph.edge_index.shape[1]),
            "mean_normalized_elevation": float(feature_means[0]),
            "mean_normalized_slope": float(feature_means[1]),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/flood/sentinel-live")
def flood_sentinel_live(payload: SentinelFloodRequest) -> dict:
    if payload.start_date > payload.end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date.")
    if payload.west >= payload.east or payload.south >= payload.north:
        raise HTTPException(status_code=400, detail="Bounding box is invalid.")

    try:
        project_id = initialize_earth_engine()
        region = ee.Geometry.Rectangle([payload.west, payload.south, payload.east, payload.north])

        image_count = int(
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(region)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filterDate(payload.start_date.isoformat(), payload.end_date.isoformat())
            .size()
            .getInfo()
        )
        if image_count == 0:
            return {
                "project_id": project_id,
                "input": model_to_dict(payload),
                "image_count": 0,
                "rows": 0,
                "cols": 0,
                "flooded_cells_count": 0,
                "flooded_fraction_pct": 0.0,
                "flooded_cells": [],
            }

        fetcher = ArasenseFloodFetcher(project_id)
        flood_mask = fetcher.get_flood_mask(
            region=region,
            start_date=payload.start_date.isoformat(),
            end_date=payload.end_date.isoformat(),
            scale=payload.scale,
        )

        rows, cols = flood_mask.shape
        flooded_cells = mask_to_cells(
            flood_mask,
            payload.west,
            payload.south,
            payload.east,
            payload.north,
        )

        total_cells = int(rows * cols)
        flooded_count = int(len(flooded_cells))
        flooded_fraction_pct = round((flooded_count / total_cells) * 100, 3) if total_cells else 0.0

        return {
            "project_id": project_id,
            "input": model_to_dict(payload),
            "image_count": image_count,
            "rows": rows,
            "cols": cols,
            "flooded_cells_count": flooded_count,
            "flooded_fraction_pct": flooded_fraction_pct,
            "flooded_cells": flooded_cells,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/flood/validate-pilot")
def flood_validate_pilot(payload: FloodValidationRequest) -> dict:
    if payload.start_date > payload.end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date.")
    if payload.sentinel_start_date > payload.sentinel_end_date:
        raise HTTPException(status_code=400, detail="sentinel_start_date must be on or before sentinel_end_date.")

    try:
        project_id = initialize_earth_engine()
        geometry = ee.Geometry.Point([payload.lon, payload.lat]).buffer(payload.radius_km * 1000)
        bounds = geometry.bounds(maxError=1).getInfo()["coordinates"][0]
        west = min(c[0] for c in bounds)
        east = max(c[0] for c in bounds)
        south = min(c[1] for c in bounds)
        north = max(c[1] for c in bounds)

        pipeline = FloodClimatePipeline(project_id)
        climate = pipeline.get_best_model_precipitation(
            geometry=geometry,
            start_date=payload.start_date.isoformat(),
            end_date=payload.end_date.isoformat(),
            fast_mode=payload.fast_mode,
        )

        builder = ArasenseGraphBuilder(project_id)
        graph, (rows, cols) = builder.build_hydrological_graph(
            region=geometry,
            scale=payload.scale,
            precip_mean=climate["precip_mean"],
            precip_anomaly=climate["precip_anomaly"],
        )

        gnn_path = "arasense_flood_gnn.pth"
        if not os.path.exists(gnn_path):
            raise HTTPException(status_code=404, detail="arasense_flood_gnn.pth was not found.")

        checkpoint = torch.load(gnn_path, map_location="cpu")
        gnn = ArasenseFloodGNN(
            num_node_features=checkpoint.get(
                "num_node_features",
                ArasenseGraphBuilder.NUM_NODE_FEATURES,
            )
        )
        gnn.load_state_dict(checkpoint["model_state_dict"])
        gnn.eval()
        with torch.no_grad():
            probs = gnn(graph).squeeze().numpy()

        prob_grid = np.asarray(probs, dtype=np.float32).reshape(rows, cols)
        predicted_mask = prob_grid >= payload.threshold

        fetcher = ArasenseFloodFetcher(project_id)
        sentinel_collection, sentinel_count = fetcher.get_s1_collection(
            geometry,
            payload.sentinel_start_date.isoformat(),
            payload.sentinel_end_date.isoformat(),
        )
        observed_mask = fetcher.get_flood_mask(
            region=geometry,
            start_date=payload.sentinel_start_date.isoformat(),
            end_date=payload.sentinel_end_date.isoformat(),
            scale=payload.scale,
            grid_shape=(rows, cols),
        ) > 0

        tp = int(np.logical_and(predicted_mask, observed_mask).sum())
        fp = int(np.logical_and(predicted_mask, ~observed_mask).sum())
        fn = int(np.logical_and(~predicted_mask, observed_mask).sum())
        tn = int(np.logical_and(~predicted_mask, ~observed_mask).sum())
        predicted_count = int(predicted_mask.sum())
        observed_count = int(observed_mask.sum())
        total = int(rows * cols)

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        iou = tp / (tp + fp + fn) if (tp + fp + fn) else 0.0
        agreement = (tp + tn) / total if total else 0.0

        node_data = []
        lat_step = (north - south) / max(rows - 1, 1)
        lon_step = (east - west) / max(cols - 1, 1)
        for idx, prob in enumerate(probs.tolist()):
            r = idx // cols
            c = idx % cols
            node_data.append(
                {
                    "lat": round(north - r * lat_step, 5),
                    "lon": round(west + c * lon_step, 5),
                    "p": round(float(prob), 3),
                    "observed": bool(observed_mask[r, c]),
                    "predicted": bool(predicted_mask[r, c]),
                }
            )

        return {
            "project_id": project_id,
            "input": model_to_dict(payload),
            "module_stage": "validation-stage flood screening pilot",
            "scope_note": "Validation metrics compare GNN screening flags with a Sentinel-1 threshold mask. They are useful for pilot evaluation, not final operational accuracy claims.",
            "best_model": climate["best_model"],
            "kge": round(climate["kge"], 4),
            "error_pct": round(climate["error_pct"], 2),
            "precip_mean": round(climate["precip_mean"], 3),
            "precip_anomaly": round(climate["precip_anomaly"], 4),
            "precip_spread": round(climate["precip_spread"], 3),
            "trusted_models": climate["models_used"],
            "trust_weights": [round(w, 4) for w in climate["weights"]],
            "grid_shape": [rows, cols],
            "graph_nodes": int(graph.x.shape[0]),
            "graph_edges": int(graph.edge_index.shape[1]),
            "sentinel_image_count": int(sentinel_count),
            "threshold": payload.threshold,
            "counts": {
                "total_cells": total,
                "predicted_screening_cells": predicted_count,
                "observed_sentinel_cells": observed_count,
                "true_positive": tp,
                "false_positive": fp,
                "false_negative": fn,
                "true_negative": tn,
            },
            "metrics": {
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "iou": round(iou, 4),
                "agreement": round(agreement, 4),
            },
            "gnn_trained_on_model": checkpoint.get("best_model", "unknown"),
            "node_flood_probs": node_data,
            "sentinel_flooded_cells": mask_to_cells(observed_mask, west, south, east, north),
        }

    except HTTPException:
        raise
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.post("/api/flood/climate-driven")
def flood_climate_driven(payload: FloodClimateDrivenRequest) -> dict:
    """
    Integrated endpoint: Aras model-trust scoring → climate-enriched flood graph.

    1. Fetches ERA5-Land + CMIP6 precipitation for the ROI and date range.
    2. Scores the ensemble with the Model Trust Engine; drops models below the
       mean-flow benchmark (KGE <= -0.41).
    3. Injects the SKILL-WEIGHTED ENSEMBLE precip features (mean + spread) of the
       trusted models into the hydrological graph nodes.
    4. Optionally runs GNN flood inference if arasense_flood_gnn.pth exists.
    """
    if payload.start_date > payload.end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date.")

    try:
        project_id = initialize_earth_engine()
        geometry   = ee.Geometry.Point([payload.lon, payload.lat]).buffer(
            payload.radius_km * 1000
        )

        # 1. Aras climate diagnostic → best CMIP6 model + precip features
        pipeline = FloodClimatePipeline(project_id)
        climate  = pipeline.get_best_model_precipitation(
            geometry   = geometry,
            start_date = payload.start_date.isoformat(),
            end_date   = payload.end_date.isoformat(),
            fast_mode  = payload.fast_mode,
        )

        # 2. Build climate-enriched hydrological graph
        builder = ArasenseGraphBuilder(project_id)
        graph, (rows, cols) = builder.build_hydrological_graph(
            region         = geometry,
            scale          = payload.scale,
            precip_mean    = climate["precip_mean"],
            precip_anomaly = climate["precip_anomaly"],
        )

        response = {
            "project_id"    : project_id,
            "input"         : model_to_dict(payload),
            "module_stage"  : "validation-stage flood screening pilot",
            "scope_note"    : "GNN flood probabilities are exploratory screening outputs and should be validated against local events, Sentinel-1 evidence, and hydraulic or field data before operational use.",
            "best_model"    : climate["best_model"],
            "kge"           : round(climate["kge"], 4),
            "error_pct"     : round(climate["error_pct"], 2),
            "precip_mean"   : round(climate["precip_mean"], 3),
            "precip_anomaly": round(climate["precip_anomaly"], 4),
            "precip_spread" : round(climate["precip_spread"], 3),
            "era5_mean"     : round(climate["era5_mean"], 3),
            "trusted_models": climate["models_used"],
            "trust_weights" : [round(w, 4) for w in climate["weights"]],
            "trust_summary" : climate["trust_summary"],
            "graph_nodes"   : int(graph.x.shape[0]),
            "graph_edges"   : int(graph.edge_index.shape[1]),
            "grid_shape"    : [rows, cols],
            "all_metrics"   : climate["all_metrics"],
        }

        # 3. Optional GNN inference if trained model exists
        gnn_path = "arasense_flood_gnn.pth"
        if os.path.exists(gnn_path):
            try:
                checkpoint = torch.load(gnn_path, map_location="cpu")
                gnn = ArasenseFloodGNN(
                    num_node_features=checkpoint.get(
                        "num_node_features",
                        ArasenseGraphBuilder.NUM_NODE_FEATURES
                    )
                )
                gnn.load_state_dict(checkpoint["model_state_dict"])
                gnn.eval()
                with torch.no_grad():
                    probs = gnn(graph).squeeze().numpy()
                flood_nodes = int((probs > 0.5).sum())
                response["flood_risk_nodes"]     = flood_nodes
                response["flood_risk_pct"]       = round(
                    flood_nodes / graph.x.shape[0] * 100, 2
                )
                response["gnn_output_type"] = "screening_probability"
                response["gnn_trained_on_model"] = checkpoint.get(
                    "best_model", "unknown"
                )
                # Send per-node probabilities + grid coords for map rendering
                # Reconstruct lat/lon for each node from grid shape + bbox
                import math
                bounds   = geometry.bounds(maxError=1).getInfo()["coordinates"][0]
                west     = min(c[0] for c in bounds)
                east     = max(c[0] for c in bounds)
                south    = min(c[1] for c in bounds)
                north    = max(c[1] for c in bounds)
                rows_n, cols_n = rows, cols
                lat_step = (north - south) / max(rows_n - 1, 1)
                lon_step = (east  - west)  / max(cols_n - 1, 1)
                node_data = []
                probs_list = probs.tolist()
                for idx, prob in enumerate(probs_list):
                    r = idx // cols_n
                    c = idx  % cols_n
                    node_data.append({
                        "lat": round(north - r * lat_step, 5),
                        "lon": round(west  + c * lon_step, 5),
                        "p"  : round(float(prob), 3),
                    })
                response["node_flood_probs"] = node_data
            except Exception as gnn_exc:
                response["gnn_error"] = str(gnn_exc)

        return response

    except HTTPException:
        raise
    except Exception as exc:
        traceback.print_exc()   # prints full stack trace to PowerShell
        raise HTTPException(status_code=500, detail=str(exc)) from exc
