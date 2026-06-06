# Arasense — the trust layer for climate risk

![Scientific Core](https://img.shields.io/badge/Scientific%20Core-Aras%20Diagram%20(Izzaddin%20et%20al.%2C%202024)-00ff88?style=for-the-badge)
![Data](https://img.shields.io/badge/Data-ERA5--Land%20%2F%20NASA%20GDDP--CMIP6-orange?style=for-the-badge)
![Tests](https://img.shields.io/badge/tests-pytest%20%2B%20CI-blue?style=for-the-badge)

**Arasense tells institutions which climate models to trust — for their location, across every hazard — and turns that into defensible, decision-ready risk evidence.**

Most climate-risk work averages a whole CMIP6 ensemble, giving a model that captures the local climate the same weight as one that doesn't. Arasense scores every model against the observed climatology with the peer-reviewed **Aras Diagram** (Izzaddin et al., 2024, *SERRA*), keeps only the models that earn trust, weights them by skill, and projects how the hazard changes — with the uncertainty reported, not hidden.

Developed at the Technical University of Bari (Poliba).

---

## What it does

| Capability | Detail |
| --- | --- |
| **Model trust** | Per-model total Aras error (bias / variability / timing), trust tiers, skill weights; rejects out-of-skill models (KGE ≤ −0.41). |
| **Hazards** | Flood-driving rainfall (max 1-day, heavy-rain days, p95), heat (max temperature, hot-day frequency), drought (dry-day frequency). |
| **Forward projection** | Trust-weighted change to mid-century with an across-model uncertainty band and model-agreement. |
| **Scenarios** | SSP2-4.5 vs SSP5-8.5, sharing one trust baseline. |
| **Multi-hazard profile** | Flood + heat + drought for a location in one report. |
| **Portfolio** | Rank a list of locations by which worsens most. |
| **Global** | Any land location (ERA5-Land + GDDP-CMIP6 are global). |
| **Reports** | Every result renders to a shareable one-page markdown/JSON. |

### Example (live data)
- **Bologna, mid-century:** max 1-day rainfall **+14%** (32/34 models trusted, 78% agree); hottest day **37 → 41 °C**.
- **Italian portfolio (max 1-day rainfall):** Rome +19% · Milan +13% · Florence +11% · Bologna +11% · Venice +3%.

---

## The science: the Aras Diagram

Each model's error vs. an observed reference is decomposed into three components
(Izzaddin et al., 2024):

- **β − 1** — bias ratio (μ_model / μ_obs − 1)
- **α − 1** — variability ratio (σ_model / σ_obs − 1)
- **r** — correlation (timing / phase)

with **total error** `E = √[(1−r)² + (β−1)² + (α−1)²]` and `KGE = 1 − E`. Trust tiers
and skill weights follow from this; the reject threshold KGE = −0.41 is the
mean-flow benchmark of Knoben et al. (2019). See [`METHODOLOGY.md`](METHODOLOGY.md).

> **Reference:** Izzaddin, A., et al. (2024). *A new diagram for performance
> evaluation of complex models.* Stochastic Environmental Research and Risk
> Assessment (SERRA).

---

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /` | Map-first console (UI) |
| `GET /healthz` | Earth Engine readiness |
| `POST /api/climate/diagnostic` | Aras Diagram + Model Trust Report |
| `POST /api/climate/projection` | Trust-weighted forward projection (one metric) |
| `POST /api/climate/projection-compare` | SSP2-4.5 vs SSP5-8.5 |
| `POST /api/climate/hazard-profile` | Multi-hazard city profile |
| `POST /api/climate/portfolio` | Rank a portfolio of locations |
| `POST /api/flood/*` | Flood screening pilot (validation-stage) |

---

## Quickstart (local)

```bash
pip install -r requirements.txt
$env:ARASENSE_GCP_PROJECT   = "valid-shine-488311-d6"
$env:GCP_SERVICE_ACCOUNT_JSON = (Get-Content path\to\service-account.json -Raw)
$env:PYTHONPATH = "$PWD\src"
python -m uvicorn api.main:app --host 127.0.0.1 --port 8088
```

Open <http://127.0.0.1:8088>. For a fast live demo, pre-warm the cache first:

```bash
python scripts/prewarm.py            # warms demo cities; later clicks are instant
```

### Tests

```bash
python -m pytest                     # zero-config via pytest.ini; runs in CI on every push
```

---

## Scope and honesty

- The **trust + projection layer** is the validated core and works globally on land.
- Where no model earns trust, the platform **declines to project** rather than fake a number.
- **Open ocean** has no land reference and is declined.
- The **flood-event GNN** is a **validation-stage** screening pilot (Emilia-Romagna /
  Bologna), not engineering-grade forecasting — see the flood section below.
- **Consecutive-dry-days** is implemented in-engine but not served (the server-side
  scan exceeds Earth Engine limits).

### Flood screening pilot
A Graph Neural Network combines terrain graph structure, precipitation, and
Sentinel-1 evidence for rapid, exploratory regional screening. Validation
priorities: validate against known event windows, compare with Sentinel-1 masks,
document false positives/negatives and scale sensitivity, expand only after 3–5
defensible case studies. Not a replacement for hydraulic modelling or field
validation.

---

## Deployment (Google Cloud Run)

```bash
gcloud run deploy arasense-api ^
  --source . --region us-central1 --allow-unauthenticated ^
  --min-instances 0 --max-instances 1 --cpu 1 --memory 1Gi --concurrency 10 ^
  --set-env-vars ARASENSE_GCP_PROJECT=valid-shine-488311-d6
```

Cost-controlled access: keep `www.arasense.com` on Cloudflare Pages as the public
site; deploy this app to Cloud Run for `app.arasense.com`; put the Cloudflare
Worker in `cloudflare-worker/` in front, sharing `ARASENSE_BACKEND_SHARED_SECRET`
/ `ORIGIN_SHARED_SECRET`, with `MONTHLY_API_LIMIT` to cap `/api/*` usage. See
`docs/deployment-cost-control.md`. Windows: copy `env.cloudrun.example.yaml` →
`env.cloudrun.yaml`, fill in real values, run `.\deploy-cloudrun.ps1`.

---

## Founder

**Aras Izzaddin** — Founder & Lead Researcher, Technical University of Bari (Poliba).
Author of the Aras Diagram (Izzaddin et al., 2024).
📧 [arasbotan.izzaddin@poliba.it](mailto:arasbotan.izzaddin@poliba.it) ·
📑 [ResearchGate](https://www.researchgate.net/profile/Aras-Izzaddin)

*© Arasense. Scientific IP: Izzaddin et al. (2024).*
