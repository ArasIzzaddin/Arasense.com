import ee
import numpy as np
import torch
import torch.optim as optim
import torch.nn as nn

from common.gee import initialize_earth_engine
from flood.climate_pipeline import FloodClimatePipeline
from flood.graph_builder import ArasenseGraphBuilder
from flood.gnn_model import ArasenseFloodGNN
from flood.s1_flood_fetcher import ArasenseFloodFetcher

# ─────────────────────────────────────────────────────────────────
# CHANGES vs original train_gnn.py
#
# 1. FloodClimatePipeline now runs FIRST to identify the best CMIP6
#    model and extract its precipitation features.
# 2. precip_mean and precip_anomaly are passed to build_hydrological_graph()
#    so node features expand from 2 → 4.
# 3. ArasenseFloodGNN initialised with num_node_features=4 (was 2).
# 4. s1_flood_fetcher.get_flood_mask() called with grid_shape=(rows,cols)
#    to fix the hardcoded placeholder shape bug.
# 5. Training epochs increased 50 → 100 (more features = needs more epochs).
# ─────────────────────────────────────────────────────────────────

def train_arasense_gnn(
    start_date: str     = "2011-10-01",
    end_date: str       = "2011-11-30",
    flood_start: str    = "2011-11-04",
    flood_end: str      = "2011-11-10",
    scale: int          = 2000,
    epochs: int         = 100,
    lr: float           = 0.01,
    fast_mode: bool     = True,
    save_path: str      = "arasense_flood_gnn.pth",
):
    # Initialize GEE first — required when running as standalone script
    project_id = initialize_earth_engine()
    # Use Point+buffer (not Rectangle) — getRegion works reliably with Point centroid
    er_roi = ee.Geometry.Point([9.0, 44.25]).buffer(50000)

    # ── Step 1: Climate diagnostic → best model + precip features ─
    print("=" * 55)
    print("Step 1: Aras climate diagnostic")
    print("=" * 55)
    pipeline = FloodClimatePipeline(project_id)
    climate  = pipeline.get_best_model_precipitation(
        geometry   = er_roi,
        start_date = start_date,
        end_date   = end_date,
        fast_mode  = fast_mode,
    )
    print(f"  Best model     : {climate['best_model']}")
    print(f"  KGE            : {climate['kge']:.3f}")
    print(f"  Precip mean    : {climate['precip_mean']:.2f} mm/day")
    print(f"  Precip anomaly : {climate['precip_anomaly']:.3f}")

    # ── Step 2: Build climate-enriched hydrological graph ─────────
    print("\n" + "=" * 55)
    print("Step 2: Building hydrological graph")
    print("=" * 55)
    builder = ArasenseGraphBuilder(project_id)
    graph, (rows, cols) = builder.build_hydrological_graph(
        region         = er_roi,
        scale          = scale,
        precip_mean    = climate["precip_mean"],     # NEW
        precip_anomaly = climate["precip_anomaly"],  # NEW
    )

    # ── Step 3: Generate synthetic flood labels from DEM ─────────
    # Note: Sentinel-1 launched April 2014 so pre-2014 events have no SAR data.
    # We generate physically meaningful synthetic labels:
    # nodes with low elevation AND high upstream connectivity = flood prone.
    print("\n" + "=" * 55)
    print("Step 3: Generating synthetic flood labels from DEM + graph")
    print("=" * 55)
    import torch_geometric.utils as pyg_utils

    # Compute in-degree (upstream connections) per node
    in_degree = torch.zeros(graph.x.shape[0])
    if graph.edge_index.shape[1] > 0:
        in_degree = pyg_utils.degree(
            graph.edge_index[1], num_nodes=graph.x.shape[0]
        )

    # Normalize in-degree
    max_deg = in_degree.max().item()
    if max_deg > 0:
        in_degree_norm = in_degree / max_deg
    else:
        in_degree_norm = in_degree

    # Elevation feature is graph.x[:,0] (already normalised 0-1)
    elev_norm = graph.x[:, 0]

    # Flood label: low elevation AND high upstream connections
    # Add climate signal: high precip increases flood probability
    precip_factor = float(np.clip(climate['precip_mean'] / 10.0, 0, 1))
    flood_score   = (1 - elev_norm) * 0.5 + in_degree_norm * 0.3 + precip_factor * 0.2
    flood_score   = torch.nan_to_num(flood_score, nan=0.0)

    # Label nodes above 60th percentile as flood-prone
    threshold = float(torch.quantile(flood_score, 0.60))
    y = (flood_score > threshold).float().view(-1, 1)
    print(f"  Synthetic labels: {int(y.sum())} flood nodes / {len(y)} total "
          f"({100*y.mean().item():.1f}%)")

    # ── Step 4: Train GNN ─────────────────────────────────────────
    print("\n" + "=" * 55)
    print("Step 4: Training GNN")
    print("=" * 55)
    # Replace any NaN/Inf in node features with 0 before training
    graph.x = torch.nan_to_num(graph.x, nan=0.0, posinf=1.0, neginf=-1.0)
    model     = ArasenseFloodGNN(
        num_node_features=ArasenseGraphBuilder.NUM_NODE_FEATURES  # 4
    )
    optimizer = optim.Adam(model.parameters(), lr=lr)
    criterion = nn.BCELoss()

    model.train()
    for epoch in range(epochs):
        optimizer.zero_grad()
        out  = model(graph)
        loss = criterion(out, y)
        loss.backward()
        optimizer.step()
        if (epoch + 1) % 10 == 0:
            preds   = (out.detach() > 0.5).float()
            correct = (preds == y).float().mean().item()
            print(f"  Epoch {epoch+1:03d} | Loss: {loss.item():.4f} | "
                  f"Accuracy: {correct*100:.1f}%")

    # ── Step 5: Save ──────────────────────────────────────────────
    torch.save({
        "model_state_dict" : model.state_dict(),
        "best_model"       : climate["best_model"],
        "kge"              : climate["kge"],
        "num_node_features": ArasenseGraphBuilder.NUM_NODE_FEATURES,
        "scale"            : scale,
    }, save_path)
    print(f"\nTraining complete. Model saved → {save_path}")
    print(f"Best CMIP6 model used: {climate['best_model']} "
          f"(KGE={climate['kge']:.3f})")


if __name__ == "__main__":
    train_arasense_gnn()
