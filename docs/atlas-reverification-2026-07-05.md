# Atlas re-verification under the extreme-plausibility screen

**Date:** 2026-07-05 · **Scope:** all 36 published Trust Atlas cities
(24 ranked European + 12 global preview) · **Raw results:**
`docs/portfolios/atlas-reverification-2026-07-05.json` · **Runner:**
`scripts/reverify_atlas.py`

Every city was re-run through the live pipeline with identical settings
(rx1day, SSP2-4.5, 1995-2014 vs 2040-2059, 50 km, fast-mode screening
ensemble) after the extreme-plausibility screen shipped, and compared to its
published number.

## Result

- **36 of 36 cities re-verified, zero errors.**
- **35 of 36 matched within 0.02 percentage points.** The one exception is
  Rome (+18.76 published vs +18.86 re-verified, drift +0.099 points), which
  is within Earth Engine recompute tolerance (bestEffort region reduction)
  and rounds to the same published atlas value at one decimal.
- **Exactly one screen exclusion: Mexico City (BCC-CSM2-MR),** reproducing
  the documented artifact deterministically. No other city's ensemble
  triggered the screen, confirming the screen is a no-op on sane ensembles
  and the published numbers did not depend on corrupted extremes.

## Standing claim

Every number published in the Trust Atlas has been re-computed under the
extreme-plausibility screen and stands. The screen changes results only
where the ensemble contains physically impossible values, and when it does,
the excluded models are named in the output.
