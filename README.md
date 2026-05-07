# ARASENSE INTELLIGENCE
### Institutional-Grade Climate Risk Analytics & AI Predictive Engines

## FastAPI / Cloud Run

This repo includes a FastAPI backend that can be deployed to Google Cloud Run.

What works after deployment:

- `GET /` serves the website shell
- `GET /docs` serves the API docs
- `GET /healthz` reports whether Earth Engine is ready

What requires Earth Engine credentials:

- `POST /api/climate/diagnostic`
- `POST /api/flood/graph-summary`

Local run:

```bash
$env:PYTHONPATH="D:\arasbotan\src"
python -m uvicorn api.main:app --host 0.0.0.0 --port 8080
```

Required environment variables for Earth Engine service-account auth:

```bash
ARASENSE_GCP_PROJECT=valid-shine-488311-d6
GCP_SERVICE_ACCOUNT_JSON='{"type":"service_account", ... }'
```

Cloud Run deploy example:

```bash
gcloud run deploy arasense-api ^
  --source . ^
  --region us-central1 ^
  --allow-unauthenticated ^
  --set-env-vars ARASENSE_GCP_PROJECT=valid-shine-488311-d6
```

Windows shortcut:

1. Copy `env.cloudrun.example.yaml` to `env.cloudrun.yaml`
2. Replace the placeholder values with your real Google service-account values
3. Run `.\deploy-cloudrun.ps1`

Production checklist:

1. Install and authenticate `gcloud`
2. Enable Cloud Run and Artifact Registry in your Google Cloud project
3. Put your Earth Engine service-account JSON into `env.cloudrun.yaml`
4. Deploy with `.\deploy-cloudrun.ps1`
5. Open the returned Cloud Run URL
6. Verify `GET /healthz` returns `"status": "ok"`

Main endpoints:

- `GET /healthz`
- `POST /api/climate/diagnostic`
- `POST /api/flood/graph-summary`

![Scientific Foundation](https://img.shields.io/badge/Scientific%20Core-Aras%20Diagram%20(2024)-00ff88?style=for-the-badge)
![AI Engine](https://img.shields.io/badge/AI%20Engine-GNN%20Surrogates-blue?style=for-the-badge)
![Data Source](https://img.shields.io/badge/Data%20Provenance-ECMWF%20%2F%20NASA-orange?style=for-the-badge)

**Arasense AI** is a professional climate intelligence platform that translates complex climate physics into actionable institutional risk data. Developed at the Technical University of Bari (Poliba), the platform bridges the gap between academic peer-reviewed research and enterprise-level climate adaptation strategies.

---

## 🚀 Core Business Pillars

### 1. Climate Intelligence (Model Benchmarking)
Powered by the **Aras Diagram (Izzaddin et al., 2024)**, Arasense provides a unique 2D error decomposition for Global and Regional Climate Models (CMIP6/CORDEX). Unlike traditional Taylor Diagrams, the Arasense engine explicitly identifies:
*   **Bias (α):** Systematic mean mismatch.
*   **Variability (β):** Fluctuation and magnitude mismatch.
*   **Phase Alignment:** Temporal and spatial correlation.

### 2. Flood Surrogates (Topological GNN)
Arasense utilizes **Graph Neural Networks (GNN)** to perform real-time flood propagation modeling. By training on historical Sentinel-1 SAR imagery and topological flow paths, our GNN surrogates offer a **1000x speedup** over traditional hydraulic models (like HEC-RAS) without sacrificing topological accuracy.

---

## 🔬 Scientific Foundation

The platform's methodology is verified by peer-reviewed research:

*   **Izzaddin, A., et al. (2024).** *"A new diagram for performance evaluation of complex models."* Published in **Stochastic Environmental Research and Risk Assessment**.
*   **Regional Assessment:** Multi-model ensemble evaluation of EURO-CORDEX simulations for the Mediterranean basin.

---

## 🛠️ Technological Stack

*   **Geospatial Engine:** Google Earth Engine (Petabyte-scale archives)
*   **AI Framework:** PyTorch Geometric (Graph Neural Networks)
*   **Analytics:** NASA GDDP-CMIP6 & ECMWF ERA5-Land
*   **Interface:** Streamlit Executive UI

---

## 🏛️ Executive Profile

**Aras Izzaddin**  
*Founder & Lead Researcher*  
Technical University of Bari (Poliba)

📧 [arasbotan.izzaddin@poliba.it](mailto:arasbotan.izzaddin@poliba.it)  
🔗 [LinkedIn Profile](https://linkedin.com)  
📑 [ResearchGate Portfolio](https://www.researchgate.net/profile/Aras-Izzaddin)

---
*© 2024 Arasense Intelligence. Scientific IP: Izzaddin et al.*
