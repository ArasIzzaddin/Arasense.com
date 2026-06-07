# Arasense — research track

Peer-reviewed papers produced with the Arasense platform. The science lives here;
the product lives in `src/`. Analysis scripts in each paper folder **import the
platform** (`climate.*`, `validation.*`) so every figure and number is reproducible
from the same tested code that backs the product.

## Why a research track
Arasense is founded on a peer-reviewed method (the Aras Diagram, Izzaddin et al.,
2024). Papers compound the moat:

```
papers → academic credibility → a more trusted platform → more pilots
       → funds/justifies more research → more papers
```

For a credibility-led climate-risk company, peer-reviewed work is not a distraction
from the business — it *is* the moat.

## Papers

| # | Folder | Working title | Status |
| --- | --- | --- | --- |
| 1 | `paper-1-trust-weighting/` | From diagnosis to decision: skill-weighted CMIP6 ensemble projection using the Aras Diagram | outline |
| 2 | *(planned)* | Multi-hazard trust-weighted projections for the Mediterranean | idea |
| 3 | *(planned)* | Where and why CMIP6 models are out-of-skill: a total-error map | idea |

## Folder convention (per paper)
```
paper-N-topic/
  outline.md      # structure, novelty, experiments, figure list, references
  analysis/       # scripts that import the platform and produce results/figures
  figures/        # generated figures
  drafts/         # manuscript drafts
```

## Reproducibility
- Run analyses with the platform deps installed and `PYTHONPATH=src`.
- Heavy Earth Engine runs reuse the platform's result cache; pre-warm with
  `scripts/prewarm.py`.
- Shared bibliography: `references.md`.

## Integrity note
The platform makes results fast; it does not make them rigorous. Publication-grade
work needs the full CMIP6 ensemble, statistical significance, baselines (equal
weight), comparison to established methods (e.g. ClimWIP), and validation
(perfect-model / out-of-sample). Speed is for iteration, not for cutting corners.
