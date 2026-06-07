# Validation Evidence Pack — Emilia-Romagna / Bologna — May 2023 flood

_Climate window 2023-05-01 → 2023-05-18 · Sentinel-1 window 2023-05-17 → 2023-05-27_

> Validation-stage flood **screening**, compared against a Sentinel-1 threshold mask. Useful for pilot evaluation, not engineering-grade flood forecasting.

## Skill vs. Sentinel-1 observed flood mask

| Metric | Value | Reading |
| --- | --- | --- |
| Critical Success Index (CSI / IoU) | **0.0%** | overlap of predicted vs. observed |
| Probability of Detection (POD / recall) | 100.0% | share of observed flood captured |
| Precision | 0.0% | share of warnings that were correct |
| False Alarm Ratio (FAR) | 100.0% | share of warnings that were wrong |
| F1 score | 0.1% | balance of POD and precision |
| Frequency bias | 2049.60 | >1 over-warns, <1 under-warns |
| Cell agreement | 0.0% | overall correct cells |

Confusion cells — TP 10 · FP 20486 · FN 0 · TN 0.

## Climate signal driving the screen

- Driver: **ERA5-Land reanalysis (observed)** — event hindcast from observed rainfall, not a free-running climate model.
- Event precip: 15.217 mm/day (climatology 3.01 mm/day, anomaly 2.0678 sigma).

---
_Note: Validation-stage screening pilot for the May 2023 Emilia-Romagna flood (main flooding 16-17 May 2023)._
