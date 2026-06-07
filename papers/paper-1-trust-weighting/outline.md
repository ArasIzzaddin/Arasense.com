# Paper 1 — outline (methods)

**Working title:**
*From diagnosis to decision: skill-weighted CMIP6 ensemble projection using the
Aras Diagram error decomposition.*

Alternatives:
- *Trust-weighted climate projections: extending the Aras Diagram to
  performance-based ensemble weighting across hazards.*
- *Which models to trust, and how much: an error-decomposition approach to CMIP6
  ensemble weighting.*

**Target journals:** *Stochastic Environmental Research and Risk Assessment*
(SERRA — home of the original Aras Diagram), *Geoscientific Model Development*
(GMD — methods + code), *Earth System Dynamics* (ESD), or *Climate Dynamics*.

**Authors:** A. Izzaddin (+ co-authors / advisors as appropriate).

---

## One-sentence contribution
The Aras Diagram (Izzaddin et al., 2024) diagnoses a single model's error; this
paper turns that **two-dimensional error decomposition (bias, variability, timing)
into a transparent, benchmark-anchored scheme for weighting and projecting a CMIP6
ensemble**, and shows it across three hazards and two emission scenarios.

## Novelty (state explicitly — reviewers will look for it)
1. A **performance-weighting** scheme grounded in an interpretable, peer-reviewed
   error decomposition (not a black-box skill score) — each model's weight is
   traceable to *why* it is (un)trusted: bias vs. variability vs. timing.
2. A **benchmark-anchored rejection** (KGE = −0.41 mean-flow benchmark, Knoben et
   al. 2019): models that don't beat the climatological mean get zero weight.
3. **Honest declination**: locations/variables where no model earns trust are
   reported as out-of-skill rather than projected — a property most weighting
   schemes lack.
4. A **multi-hazard, reproducible** application (flood-rainfall, heat, drought)
   with open, tested code.

---

## Abstract (draft skeleton, ~200 words)
Problem (ensemble disagreement, equal-weight averaging blends skilful and
unskilful models) → gap (weighting schemes are often opaque or performance-only) →
method (Aras Diagram total error → tiers, skill weights, benchmark rejection →
weighted projection) → experiments (Mediterranean/Italy, full CMIP6, SSP2-4.5 &
SSP5-8.5, three hazards) → key results (extremes intensify with high model
agreement while mean change is small/uncertain; weighting changes the projected
signal and narrows/ągrounds uncertainty vs equal weight; comparison to ClimWIP) →
significance (transparent, reproducible, declines out-of-skill).

## 1. Introduction
- CMIP6 ensemble spread; the cost of equal-weight averaging for risk decisions.
- Brief on existing weighting (REA, Bayesian, ClimWIP — performance + independence).
- The interpretability gap: weights you can't explain are hard to defend.
- This paper's contribution (the four points above). End with paper roadmap.

## 2. Background
- 2.1 The Taylor diagram and its limits; the Aras Diagram (Izzaddin et al., 2024):
  α (variability), β (bias), r (timing); total error E = √[(1−r)²+(β−1)²+(α−1)²]; KGE.
- 2.2 Performance weighting and its critiques (overconfidence; the perfect-model
  test; model interdependence/genealogy — Knutti et al. 2017; Sanderson et al. 2015).

## 3. Methods
- 3.1 Per-model scoring: total Aras error and its bias/variability/timing split.
- 3.2 Trust tiers and the mean-flow benchmark (Knoben et al. 2019); rejection rule.
- 3.3 Skill weights (∝ skill above benchmark, sharpness exponent); effective
  ensemble size (inverse participation ratio).
- 3.4 Weighted projection: change in a hazard metric historical→future, with
  across-model spread and sign-agreement. Trust scored on the **historical
  climatology** (monthly); extremes computed from daily data.
- 3.5 Scenarios (shared trust baseline) and hazards/indicators (rx1day, heavy-rain
  freq, p95; Tmax, hot-day freq; dry-day freq).
- 3.6 *(Extension to discuss)* model independence weighting — currently
  performance-only; outline how genealogy/independence could be added.

## 4. Data
- ERA5-Land (reference) and NASA GDDP-CMIP6 (downscaled, full ensemble, historical
  + ssp245/ssp585). Bands, units (Kelvin invariant), windows (1995–2014 vs
  2040–2059), region(s). Earth Engine processing; reproducibility.

## 5. Experiments
- E1: trust scoring of the full ensemble across the region (which models, why).
- E2: weighted vs **equal-weight** projection — does weighting change the signal/spread?
- E3: comparison to an established scheme (**ClimWIP**) — agreement and differences.
- E4: **validation** — perfect-model / leave-one-out test (treat one model as
  "truth", check the weighting recovers it / improves the projection); out-of-sample
  skill over a held-out period.
- E5: multi-hazard + two scenarios; where the ensemble is out-of-skill.

## 6. Results
- Trust maps / tables; dominant error mode by region.
- Weighted vs equal-weight projected changes + uncertainty (tables + maps).
- Validation outcomes (perfect-model, out-of-sample).
- Multi-hazard, multi-scenario summary; out-of-skill cases.

## 7. Discussion
- Interpretability advantage; what the error decomposition reveals.
- Overconfidence and independence caveats; how the benchmark mitigates.
- Limitations (performance-only weighting; downscaled-data resolution; CDD not
  served; flood-event model excluded).

## 8. Conclusions
- Restate contribution; the case for transparent, benchmark-anchored weighting.

## Code & data availability
Open, tested repository (CI); ERA5-Land and NASA GDDP-CMIP6 via Google Earth Engine.

---

## Figures / tables (proposed)
- F1: the Aras Diagram with the full ensemble for one site (the moat, visual).
- F2: trust tiers + skill weights (the Model Trust Report).
- F3: weighted vs equal-weight projected change + uncertainty band, per hazard.
- F4: validation — perfect-model / out-of-sample skill.
- F5: comparison to ClimWIP (scatter / map of weight differences).
- F6: multi-hazard, two-scenario summary; out-of-skill mask.
- T1: hazards/indicators and definitions. T2: data sources/windows.

## Key references (to cite)
Izzaddin et al. (2024, SERRA) · Gupta et al. (2009) · Knoben et al. (2019) ·
Taylor (2001) · Knutti et al. (2017) · Brunner et al. (2020, ClimWIP) ·
Sanderson et al. (2015) · Tebaldi & Knutti (2007) · Giorgi & Mearns (2002, REA) ·
Eyring et al. (2016, CMIP6) · Eyring et al. (2019, ESMValTool) · IPCC AR6 WG1.

---

## What the platform already provides (so writing is fast)
- Full-ensemble trust scoring, weights, error attribution → F1, F2, T1.
- Weighted projections, scenarios, multi-hazard, out-of-skill handling → F3, F6.
- Reproducible, tested code → Code & data availability.

## What still needs building for publication-grade
- ✅ **E4 (perfect-model validation)** — **built**: `src/validation/perfect_model.py`
  (tested; +58% RMSE improvement on a structured synthetic ensemble) +
  `analysis/e4_perfect_model.py` (real full-ensemble runner). *Still to add:
  out-of-sample skill over a held-out historical period.*
- **E2 (equal-weight baseline)** and **E3 (ClimWIP comparison)** — add an equal-weight
  projection option and implement/adopt ClimWIP weights for comparison.
- Full-ensemble runs over a regular spatial grid (not just point cities) for maps.
