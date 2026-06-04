# Arasense Methodology

*How Arasense decides which climate models to trust, and turns that into local risk evidence.*

This document describes the scientific core of the platform. It is written to be
defensible: every step maps to peer-reviewed methods and to tested code in this
repository.

---

## 1. The problem

For any location and variable there are dozens of CMIP6 climate models, and they
disagree. The common responses — pick a single "best" model by one score, or
average the whole ensemble — either discard information or blend skilful models
with broken ones. The result is a risk estimate that is hard to defend to a
regulator, an insurer, or a board.

Arasense addresses this with an explicit **model-trust layer**: score every model,
explain *why* it is right or wrong, keep only the ones that earn trust, and weight
them by skill before producing a downstream risk signal.

---

## 2. The Aras Diagram (model error decomposition)

**Reference:** Izzaddin, A., et al. (2024). *A new diagram for performance
evaluation of complex models.* *Stochastic Environmental Research and Risk
Assessment (SERRA).*

For a model series relative to an observed reference, define:

| Quantity | Definition | Meaning |
| --- | --- | --- |
| α (variability ratio) | σ_model / σ_obs | amplitude / spread match |
| β (bias ratio) | μ_model / μ_obs | systematic mean match |
| r | Pearson correlation | timing / phase match |

The diagram plots each model at **(β − 1, α − 1)**, so the origin is a perfect
model. Two distances summarise the error:

```
E_αβ   = sqrt( (β − 1)² + (α − 1)² )                  # bias + variability error  (circle)
E_total = sqrt( (1 − r)² + (β − 1)² + (α − 1)² )       # total error               (triangle)
KGE     = 1 − E_total                                  # Kling–Gupta efficiency
```

The total-error point lies radially outward from E_αβ; the segment between them is
the correlation (phase) contribution. Unlike a single skill score, this separates
**how much** error a model has from **what kind** — bias, variability, or timing.

> Implementation: `src/climate/aras_eval.py`. The implementation is verified
> equivalent to the canonical reference implementation
> (`github.com/ArasIzzaddin/Aras_diagram`) and pinned by tests in
> `tests/test_aras_eval.py`.

---

## 3. The Model Trust Engine

The decomposition above is turned into a decision in `src/climate/trust_engine.py`.

### 3.1 Trust tiers
Each model is classified by KGE (and correlation sign):

| Tier | Rule |
| --- | --- |
| trusted | KGE ≥ 0.75 |
| usable | 0.50 ≤ KGE < 0.75 |
| weak | −0.41 ≤ KGE < 0.50 |
| reject | KGE < −0.41 **or** r < 0 |

The reject threshold **KGE = −0.41** is the *mean-flow benchmark* of Knoben,
Freer & Woods (2019): a model below it does not beat simply predicting the
observed mean, so it earns zero weight. A negative correlation means the model
gets the temporal pattern backwards and is likewise rejected.

### 3.2 Error attribution
For each model the total squared error is split into its three components and the
dominant one is reported, so the engine can say *which error to fix first*:

```
bias share        = (β − 1)²        / E_total²
variability share = (α − 1)²        / E_total²
phase share       = (1 − r)²        / E_total²
```

### 3.3 Skill weights
Kept models receive a weight proportional to their skill above the benchmark,
normalised to sum to 1 (a sharpness exponent can concentrate weight on the best
models):

```
weight_i ∝ max(0, KGE_i − (−0.41)) ^ sharpness
```

An **effective ensemble size** (inverse participation ratio of the weights)
reports whether one model dominates or trust is spread evenly.

---

## 4. Trust-driven local risk (flood vertical)

`src/flood/climate_pipeline.py` applies the trust weights to build a
**skill-weighted ensemble precipitation** signal from the trusted models only.
Rejected models contribute nothing; if every model is out-of-skill the pipeline
refuses to proceed rather than emit a misleading number.

The flood graph receives, per node:
- ensemble mean precipitation, and
- an **across-model spread** — an uncertainty signal a single-best-model approach
  cannot provide.

> **Scope statement.** The flood module is **validation-stage screening**, not
> engineering-grade flood forecasting. It supports rapid, exploratory regional
> assessment and should be validated against local events, Sentinel-1 evidence,
> and hydraulic/field data before any operational use.

---

## 5. Validation protocol

Regional case studies are scored against a Sentinel-1 derived flood mask using
standard categorical (contingency-table) verification, in
`src/validation/evidence_pack.py`:

| Score | Definition | Reads as |
| --- | --- | --- |
| POD (recall) | TP / (TP + FN) | fraction of observed flood detected |
| Precision | TP / (TP + FP) | fraction of warnings that were correct |
| FAR | FP / (TP + FP) | fraction of warnings that were wrong |
| CSI / IoU | TP / (TP + FP + FN) | overlap of predicted and observed |
| F1 | 2TP / (2TP + FP + FN) | balance of POD and precision |
| Frequency bias | (TP + FP) / (TP + FN) | >1 over-warns, <1 under-warns |

The reference pilot is the **2023 Emilia-Romagna / Bologna flood**. The plan is to
build 3–5 defensible regional case studies before any broader operational claim.

---

## 6. Numerical robustness

- **Kelvin invariant.** The bias ratio β = μ_model/μ_obs is unstable when
  μ_obs ≈ 0 (e.g. temperature in °C, anomalies). Temperature is kept in Kelvin
  throughout (`src/climate/data_fetcher.py`), and the engine refuses to compute a
  bias ratio for a zero-mean reference rather than emitting infinity.
- **Variability guard.** A constant reference (σ_obs ≈ 0) makes α undefined and is
  rejected with a clear error.
- Input-domain failures surface as HTTP 400, not 500.

---

## 7. Reproducibility

The numerical core is covered by an automated test suite
(`python -m pytest`, configured via `pytest.ini`) that pins the Aras Diagram
math to the formulas above and exercises the trust engine, the trust-driven flood
pipeline, and the validation scoring. The suite runs in CI on every push and pull
request (`.github/workflows/tests.yml`).

---

## References

- Izzaddin, A., et al. (2024). *A new diagram for performance evaluation of
  complex models.* Stochastic Environmental Research and Risk Assessment.
- Gupta, H. V., Kling, H., Yilmaz, K. K., & Martinez, G. F. (2009). *Decomposition
  of the mean squared error and NSE performance criteria.* Journal of Hydrology.
- Knoben, W. J. M., Freer, J. E., & Woods, R. A. (2019). *Technical note: Inherent
  benchmark or not? Comparing Nash–Sutcliffe and Kling–Gupta efficiency scores.*
  Hydrology and Earth System Sciences.
