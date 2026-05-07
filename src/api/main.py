import os
import traceback
from datetime import date
from pathlib import Path
from typing import Literal, Optional

import ee
import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from climate.aras_eval import ArasDiagram
from climate.data_fetcher import ArasenseDataFetcher
from climate.gnn_bias_corrector import ClimateBiasCorrector
from common.gee import get_earth_engine_status, get_project_id, initialize_earth_engine
from flood.graph_builder import ArasenseGraphBuilder
from flood.climate_pipeline import FloodClimatePipeline
from flood.gnn_model import ArasenseFloodGNN


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


class ClimateDiagnosticRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(50, gt=0, le=500)
    start_date: date
    end_date: date
    variable: Literal["temperature", "precipitation", "all_euro_cordex"] = "temperature"
    ref_dataset: str = "ERA5-Land"
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
          This console combines a live geospatial map, climate model diagnostics, and flood topology
          summaries in one interface. Click the map to set a climate point, drag a box for flood analysis,
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
          <li>Shift-drag on the map to define a flood bounding box.</li>
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
            <p>Single click sets the climate analysis point. Hold <strong>Shift</strong> and drag to draw a flood bounding box.</p>
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
              <div class="mode-tab top-tab" data-target="flood-card">Flood Engine</div>
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
              <h3>Flood Graph Summary</h3>
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
                  <label>Scale (m)<input name="scale" type="number" step="1" value="4000"></label>
                  <button type="submit" style="align-self:end;">Run Flood Summary</button>
                </div>
              </form>
            </div>

            <div id="flood-climate-fields" style="display:none;">
              <h3>Climate-Driven Flood Analysis</h3>
              <p style="color:var(--muted);font-size:13px;margin:0 0 12px;">Identifies the best CMIP6 precipitation model via the Aras diagram, then injects its signal into the flood graph.</p>
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
                  <label>Fast Mode
                    <select name="fast_mode">
                      <option value="true">true</option>
                      <option value="false">false</option>
                    </select>
                  </label>
                  <button type="submit" style="align-self:end;">Run Climate-Driven Flood</button>
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
    const mapFallback = document.getElementById('map-fallback');
    const climateViewState = {
      latestClimateData: null,
      bestModelName: null,
      biasCorrectionEnabled: false,
      biasCorrectionResult: null
    };

    if (typeof window.L === 'undefined') {
      document.getElementById('map').style.display = 'none';
      mapFallback.style.display = 'grid';
      mapStatus.textContent = 'Map library unavailable';
    } else {
      const map = L.map('map', { zoomControl: true }).setView([42.5, 12.8], 5);
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
          if (mode === 'flood-climate') {
            setMetrics([
              { value: String(data.graph_nodes || 0), label: 'Graph nodes' },
              { value: String(data.graph_edges || 0), label: 'Hydro edges' },
              { value: data.best_model || '-', label: 'Best CMIP6 model' }
            ]);
            setInsights([
              { title: 'Best precipitation model', text: `${data.best_model} selected by Aras diagram (KGE=${Number(data.kge||0).toFixed(3)}, E=${Number(data.error_pct||0).toFixed(1)}%).` },
              { title: 'Climate signal injected', text: `Precip mean ${Number(data.precip_mean||0).toFixed(2)} mm/day, anomaly ${Number(data.precip_anomaly||0).toFixed(3)} vs ERA5 mean ${Number(data.era5_mean||0).toFixed(2)} mm/day.` },
              { title: 'Flood graph', text: `${data.graph_nodes||0} nodes, ${data.graph_edges||0} edges. Grid ${(data.grid_shape||[0,0])[0]} × ${(data.grid_shape||[0,0])[1]}.${data.flood_risk_pct !== undefined ? ' GNN flood risk: ' + Number(data.flood_risk_pct).toFixed(1) + '% of nodes.' : ''}` }
            ]);
            if (data.all_metrics && data.all_metrics.length) {
              renderArasDiagram(data.all_metrics);
              renderRankingTable(data.all_metrics);
            }
            // Render flood risk nodes on the Leaflet map
            if (data.node_flood_probs && data.node_flood_probs.length) {
              renderFloodRiskMap(data.node_flood_probs, data.grid_shape);
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

    // Flood mode toggle
    function setFloodMode(mode) {
      window._lastFloodMode = mode;
      document.getElementById('flood-basic-fields').style.display   = mode === 'basic'   ? 'block' : 'none';
      document.getElementById('flood-climate-fields').style.display = mode === 'climate' ? 'block' : 'none';
      document.getElementById('flood-mode-basic').classList.toggle('active',   mode === 'basic');
      document.getElementById('flood-mode-climate').classList.toggle('active', mode === 'climate');
    }

    // ── Flood risk map renderer ──────────────────────────────────
    let floodRiskLayer = null;

    function renderFloodRiskMap(nodeProbs, gridShape) {
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
          `<b>Flood risk: ${(p * 100).toFixed(1)}%</b><br>` +
          `${p >= 0.80 ? '🔴 Very high' : p >= 0.60 ? '🟠 High' : p >= 0.35 ? '🟡 Moderate' : '🟢 Low'}`,
          { sticky: true }
        );
      });

      floodRiskLayer = L.layerGroup(layers).addTo(map);

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
          <b style="font-size:13px">🌊 Flood Risk Map</b><br>
          <span style="color:#c0392b">●</span> Very high ≥80% <br>
          <span style="color:#e67e22">●</span> High 60–80%<br>
          <span style="color:#f39c12">●</span> Moderate 35–60%<br>
          <span style="color:#27ae60">●</span> Low &lt;35%<br>
          <hr style="border-color:rgba(255,255,255,0.2);margin:4px 0">
          <span style="font-size:10px;color:#aaa">
            ${hi} high-risk nodes (${(hi/nodeProbs.length*100).toFixed(0)}%)<br>
            ${nodeProbs.length} total nodes • 2 km grid
          </span>`;
        return div;
      };
      legend.addTo(map);
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

@app.post("/api/flood/climate-driven")
def flood_climate_driven(payload: FloodClimateDrivenRequest) -> dict:
    """
    Integrated endpoint: Aras climate diagnostic → climate-enriched flood graph.

    1. Fetches ERA5-Land + CMIP6 precipitation for the ROI and date range.
    2. Runs the Aras diagram to identify the best CMIP6 model.
    3. Injects best-model precip features into the hydrological graph nodes.
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
            "best_model"    : climate["best_model"],
            "kge"           : round(climate["kge"], 4),
            "error_pct"     : round(climate["error_pct"], 2),
            "precip_mean"   : round(climate["precip_mean"], 3),
            "precip_anomaly": round(climate["precip_anomaly"], 4),
            "era5_mean"     : round(climate["era5_mean"], 3),
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
