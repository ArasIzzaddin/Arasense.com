# Mexico City rx1day investigation — why the atlas number is withheld

**Date:** 2026-07-05 · **Runs:** fast-mode screening (5 models) and full ensemble
(31 trusted of 34), both rx1day, SSP2-4.5, 50 km radius, 1995-2014 vs 2040-2059.
Raw output: `docs/portfolios/mexico-city-full-projection.json`.

## Symptom

- Fast-mode screening: baseline 263 mm, change **−69.2%**, agreement 43%.
- Full ensemble: baseline 231 mm, change **−30.3%**, agreement 39%.

An area-averaged annual-maximum 1-day precipitation baseline of 230-260 mm is
physically implausible for the Basin of Mexico (observed magnitudes are a few
tens of mm). Both numbers are withheld from the Trust Atlas.

## Root cause

Per-model baselines in the full ensemble split into two populations:

| Population | Models (examples) | Baseline rx1day |
| --- | --- | --- |
| Plausible | CESM2 38.8 · MIROC-ES2L 40.1 · HadGEM3-GC31-LL 40.5 · UKESM1-0-LL 44.2 · IPSL-CM6A-LR 46.1 | 33-60 mm |
| Impossible | **BCC-CSM2-MR 1,512.8** · **MPI-ESM1-2-LR 1,373.0** · **NESM3 1,006.1** · CMCC-ESM2 684.0 · NorESM2-MM 616.1 · NorESM2-LM 345.4 · IITM-ESM 330.9 · GFDL-CM4 326.4 | 280-1,513 mm |

TaiESM1 is plausible in the baseline (49.4 mm) but impossible in the future
window (621.9 mm) — the artifact is per-window, not just per-model.

Values of 300-1,500 mm/day over this domain are a known failure mode of
BCSD-style statistical downscaling (NEX-GDDP-CMIP6) over high-relief terrain:
quantile mapping can explode daily extremes where the observed training
climatology has strong elevation gradients. The Basin of Mexico (2,240 m,
ringed by >5,000 m volcanoes) is a textbook trigger.

## Why trust screening did not catch it

Aras Diagram skill weights are earned on mean-climate behaviour. The corrupted
models track monthly climatology well enough to stay "usable" (weights 0.020 to
0.033 — barely below the sane models), while their **daily extremes** are
unphysical. Mean-climate trust does not certify extreme-value sanity.

## Consequence and fix (roadmap)

1. **Published stance:** Mexico City stays withheld in the Trust Atlas, with the
   diagnosed reason stated publicly. Withholding a number we don't believe is
   part of the method.
2. **Pipeline fix (planned):** add a physical-plausibility screen on the hazard
   metric itself before trust weighting — e.g. reject any model whose
   window-level rx1day exceeds a sane multiple of the observed ERA5-Land value
   for the same footprint (both windows). Trust must be earned on the extremes
   being projected, not only on the means.
3. **Paper relevance:** this is a concrete, demonstrable case for
   metric-specific trust screening — a strong honest-methods exhibit for the
   trust-weighting paper and for technical reviewers.
