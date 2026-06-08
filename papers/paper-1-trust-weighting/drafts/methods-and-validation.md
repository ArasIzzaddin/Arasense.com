# Paper 1 — Methods & Validation (working draft)

*Draft prose for the methodological core and the perfect-model validation. Numbers
are from the live runs in `../analysis/` (E4, E4b). Multi-city table is filled from
the E4b sweep when it completes.*

---

## 3. Methods

### 3.1 Per-model error decomposition
For each climate model we evaluate its historical series against an observational
reference (ERA5-Land) at the location of interest using the Aras Diagram
(Izzaddin et al., 2024). With μ and σ the mean and standard deviation and r the
Pearson correlation between model and reference, define the bias ratio
β = μ_model/μ_obs, the variability ratio α = σ_model/σ_obs, and the total error

    E = √[(1 − r)² + (β − 1)² + (α − 1)²],     KGE = 1 − E.

E places each model in an interpretable space whose axes (β − 1, α − 1) and radial
extension (1 − r) attribute the error to **bias**, **variability**, and **timing**
respectively — the basis for *why* a model is (un)trusted, not merely *how much*.

### 3.2 Benchmark-anchored trust and skill weights
A model is rejected (zero weight) if its correlation is negative or its KGE falls
below the mean-flow benchmark KGE = −0.41 (Knoben et al., 2019); below this a model
does not beat predicting the observed mean. Surviving models receive a skill weight

    w_i ∝ max(0, KGE_i − (−0.41))^γ,   normalised to Σ w_i = 1,

with sharpness γ (γ = 1 unless stated). The effective ensemble size (inverse
participation ratio of the weights) reports whether one model dominates.

### 3.3 Scoring domain (the key methodological variable)
The series used to compute E can be (a) the **monthly climatology** over the
historical window, or (b) the **annual series of the target metric itself** (e.g.
the annual maximum 1-day precipitation). We treat the scoring domain as an explicit
choice and evaluate both, because — as Section 6 shows — it is decisive.

### 3.4 Weighted projection
The trusted, skill-weighted ensemble is projected to a future window; we report the
change in the target metric, the across-model spread (±1σ), and the share of weight
agreeing on the direction of change. Out-of-skill cases (no model trusted) are
declined rather than projected.

---

## 4. Validation: the perfect-model test
We assess whether trust-weighting improves projections with a leave-one-out
perfect-model test. Each model in turn is treated as pseudo-truth: the remaining
models are scored against its *historical* series, and its *future* metric value is
predicted as (i) the skill-weighted mean and (ii) the equal-weight mean of the
others. We aggregate the RMSE of each predictor against the held-out truth across
all models, and report the improvement of weighting over equal weighting,
(RMSE_equal − RMSE_weighted)/RMSE_equal. A positive value means weighting helps.

The harness is verified on a structured synthetic ensemble in which historical
skill carries future information by construction; there it recovers a +58%
improvement, confirming it can detect a benefit when one exists.

---

## 5. Data and experiments
ERA5-Land reanalysis as the observational reference; the NASA GDDP-CMIP6 downscaled
daily ensemble (33–34 models) under SSP2-4.5 and SSP5-8.5; historical 1995–2014 vs
future 2040–2059; Mediterranean/Italian locations. All processing is server-side
on Google Earth Engine; code is open and tested.

---

## 6. Results: scoring domain decides whether weighting helps

**Monthly-climatology scoring does not improve extreme projections.** At Bologna,
for the annual maximum 1-day precipitation (rx1day), the perfect-model improvement
of weighting over equal weighting is **−0.3%** — i.e. no benefit. The same null
holds for the mean (**+0.0%**). This is consistent with the literature: a model's
skill at the broad climatology is a weak predictor of its skill at projecting a
specific future quantity.

**Aligned scoring recovers a benefit.** Re-scoring trust on each model's *own
annual rx1day series* — aligning the predictor with the predictand — raises the
perfect-model improvement to **+7.6%** at Bologna (RMSE 6.74 vs 7.29). The
information that matters is skill at the target quantity itself, not a generic
climatology.

**Generalisation across cities.** *(filled from `../analysis/e4b_sweep_rx1day.md`)*

> | City | models | monthly | aligned |
> | --- | --- | --- | --- |
> | … | … | … | … |

### Interpretation
Performance weighting is not free skill; its value depends entirely on aligning the
evaluation metric with the projection target. Scored generically it adds nothing
over the ensemble mean; scored on the target's own behaviour it adds a modest but
real improvement. The interpretable decomposition (Section 3.1) and the explicit
out-of-skill declination remain valuable independent of this — they make the basis
of any projection transparent and auditable.

### Honesty / limitations
Results to date are for one region and metric; the multi-city/metric/scenario
sweep, an out-of-sample (held-out period) test, and a comparison to ClimWIP are
required before any general accuracy claim. The improvement, where present, is
modest (single-digit %). We do **not** claim that the currently shipped
monthly-scored product is more accurate than an ensemble mean.
