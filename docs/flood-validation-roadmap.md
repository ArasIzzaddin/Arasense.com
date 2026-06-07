# Arasense Flood Validation Roadmap

## Current Position

The flood module is a validation-stage screening pilot. It should be used to explore flood-sensitive terrain and climate-driven risk signals, not to make operational flood forecasts.

The first validation geography is Emilia-Romagna / Bologna because the current training setup, interface defaults, and saved GNN model are aligned with northern Italy.

## Validation Goal

Create a defensible pilot case study showing how Arasense combines:

- Climate-model precipitation diagnostics
- Terrain graph structure
- Sentinel-1 satellite flood evidence
- GNN screening probabilities

The output should be a short technical report and a repeatable demo workflow.

## Case Study Checklist

1. Select one known Emilia-Romagna flood event window.
2. Run Sentinel-1 flood-mask extraction for the event period.
3. Run the terrain-only flood graph for the same bounding box.
4. Run the climate-driven flood pilot for the same area.
5. Compare GNN high-probability nodes with Sentinel-1 flooded cells.
6. Record where the model agrees, misses flooding, or overflags risk.
7. Repeat at two or three spatial scales to test sensitivity.
8. Save screenshots, JSON outputs, and key metrics.

## Metrics To Track

- Sentinel-1 image count
- Flooded cell count and percentage
- Graph node and edge count
- GNN flagged node percentage
- Spatial overlap between GNN high-probability nodes and Sentinel-1 mask
- False-positive areas that may reflect terrain susceptibility rather than observed flooding
- False-negative areas where the satellite mask detects flooding but the GNN does not

## Product Rule

Use this language until validation is stronger:

> Arasense is validating a climate-driven flood screening module through regional pilot studies, starting with Emilia-Romagna. The module supports early-stage risk screening and should be combined with satellite evidence, local data, and hydraulic expertise before operational use.

Avoid these claims for now:

- Real-time flood prediction
- Global flood forecasting
- Replacement for hydraulic models
- Validated accuracy outside pilot geographies
- Guaranteed speedup over engineering models

## Next Milestone

Produce one Bologna / Emilia-Romagna flood pilot report with maps, methods, limitations, and a clear conclusion about where the current module is useful and where it needs more training data.
