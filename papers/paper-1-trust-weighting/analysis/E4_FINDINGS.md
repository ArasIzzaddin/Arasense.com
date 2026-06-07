# E4 — perfect-model validation: findings (honest record)

**Test:** leave-one-out perfect-model test on the real CMIP6 ensemble at Bologna
(44.494, 11.343), SSP2-4.5, historical 1995–2014 vs future 2040–2059. For each
model treated as "truth", the other models are scored on their historical skill
(Model Trust Engine) and used to predict the truth model's future value;
skill-weighted RMSE is compared to equal-weight RMSE.

## Results (full ensemble, 33 models)

| Target | RMSE weighted | RMSE equal | Improvement | Weighting better |
| --- | --- | --- | --- | --- |
| `rx1day` (max 1-day rainfall) | 7.318 | 7.292 | **−0.3%** | 11 / 33 |
| `mean` (precipitation) | 0.126 | 0.126 | **+0.0%** | 17 / 33 |

(Synthetic control: on a *structured* ensemble where historical skill does carry
future information, the same harness measures **+58%** — so the null on real data
is a property of the ensemble, not a bug in the test.)

## Interpretation (honest)
- **Trust-weighting by historical skill did not improve future projections over a
  plain ensemble mean** — for the mean *or* the extreme, at this location.
- This is consistent with a known, genuinely debated result in the literature:
  **historical performance is a weak predictor of future projection accuracy**
  (the motivation for emergent constraints; the reason performance-weighting
  schemes such as ClimWIP are contested).

## E4b — aligned scoring (the fix works)
Re-running the perfect-model test for `rx1day` but scoring trust on each model's
**annual max-1-day rainfall series** (1995–2014) — aligning the predictor with the
predictand — instead of the monthly climatology:

| Trust scored on | RMSE weighted | RMSE equal | Improvement |
| --- | --- | --- | --- |
| monthly climatology | 7.318 | 7.292 | −0.3% (null) |
| **annual target-metric series** | **6.738** | 7.292 | **+7.6%** |

**Finding:** performance weighting *does* improve the extreme projection, but only
when models are scored on their skill at the **target quantity itself**, not a
generic climatology. Predictor–predictand alignment is the key. (Raw:
`e4b_bologna_rx1day.json`.) Caveat: one location/metric/scenario — generalise
across regions, metrics, and scenarios for the paper.

## Consequences (what we will and will not claim)
- **Do NOT claim** that the *currently shipped* (monthly-scored) trust-weighting
  produces a more accurate central projection than the ensemble mean — E4 does not
  support it.
- **DO** pursue **aligned scoring** (score on the target metric's own historical
  series): E4b shows a real +7.6% RMSE gain for rx1day. Adopt it in the product
  for extreme metrics, then re-validate across regions before claiming accuracy.
- **Defensible value of the platform/method:**
  1. **Interpretable model diagnosis** — the Aras Diagram attributes each model's
     error to bias / variability / timing.
  2. **Screening** — rejecting anti-correlated / below-benchmark models.
  3. **Honest uncertainty** — explicit across-model spread and agreement.
- **Next scientific step:** score trust on the *target metric's own* historical
  skill (e.g. annual-maximum series for rx1day) rather than monthly climatology,
  and re-run E4 to see whether aligned scoring recovers any improvement. Also
  evaluate out-of-sample over a held-out historical period.

Raw outputs: `e4_bologna_rx1day.json`, `e4_bologna_mean.json`.
