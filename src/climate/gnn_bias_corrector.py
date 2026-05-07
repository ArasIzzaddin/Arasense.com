import math

import numpy as np
import torch
import torch.nn.functional as F
from torch_geometric.data import Data
from torch_geometric.nn import GCNConv


class ClimateBiasCorrectionGNN(torch.nn.Module):
    """
    Small temporal graph model for climate-series bias correction.
    Nodes represent time steps; edges connect neighbouring dates so the model
    can learn local temporal structure while correcting the raw model signal.

    BUGS FIXED
    ----------
    BUG 1 — _build_graph added self-loops (idx, idx) in the edge list.
             Self-loops are fine for GCNConv BUT the original code added them
             WITHOUT the corresponding reverse edge, making the adjacency
             matrix asymmetric and causing silent performance degradation.
             GCNConv with add_self_loops=True (the default) will add them
             again anyway, so the manually added duplicates are redundant.
             Fix: remove explicit self-loop edges; let GCNConv handle them
             via its default add_self_loops=True parameter.
    """

    def __init__(self, num_node_features: int, hidden_dim: int = 32):
        super().__init__()
        self.conv1 = GCNConv(num_node_features, hidden_dim)
        self.conv2 = GCNConv(hidden_dim, hidden_dim)
        self.out   = torch.nn.Linear(hidden_dim, 1)

    def forward(self, data: Data) -> torch.Tensor:
        x, edge_index = data.x, data.edge_index
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = F.dropout(x, p=0.1, training=self.training)
        x = self.conv2(x, edge_index)
        x = F.relu(x)
        return self.out(x).squeeze(-1)


class ClimateBiasCorrector:
    def __init__(self, epochs: int = 250, learning_rate: float = 0.01):
        self.epochs        = epochs
        self.learning_rate = learning_rate

    def _build_graph(self, raw_values: np.ndarray) -> tuple[Data, dict]:
        count     = len(raw_values)
        positions = np.arange(count, dtype=np.float32)
        denom     = max(count - 1, 1)
        phase     = positions / denom
        centered  = raw_values - np.mean(raw_values)
        spread    = float(np.std(raw_values))
        spread    = spread if spread > 1e-6 else 1.0
        normalized_raw = centered / spread

        features = np.stack(
            [
                normalized_raw,
                phase,
                np.sin(2 * math.pi * phase),
                np.cos(2 * math.pi * phase),
            ],
            axis=1,
        )

        # FIX BUG 1: only bidirectional neighbour edges;
        # GCNConv adds self-loops automatically via add_self_loops=True
        edges = []
        for idx in range(count):
            if idx > 0:
                edges.append((idx, idx - 1))
                edges.append((idx - 1, idx))   # ensure symmetry
            if idx < count - 1:
                edges.append((idx, idx + 1))
                edges.append((idx + 1, idx))   # ensure symmetry

        # Deduplicate (the loop above creates each forward+backward pair
        # twice for interior nodes)
        edges = list(set(edges))

        edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
        data       = Data(
            x          = torch.tensor(features, dtype=torch.float32),
            edge_index = edge_index,
        )
        metadata = {
            "raw_mean": float(np.mean(raw_values)),
            "raw_std" : spread,
        }
        return data, metadata

    def correct(self,
                reference_values: list[float],
                raw_model_values: list[float]) -> dict:
        if len(reference_values) != len(raw_model_values):
            raise ValueError(
                "reference and model series must have identical lengths.")
        if len(reference_values) < 3:
            raise ValueError(
                "at least three aligned time steps are required for GNN correction.")

        reference = np.asarray(reference_values, dtype=np.float32)
        raw_model = np.asarray(raw_model_values, dtype=np.float32)
        graph, metadata = self._build_graph(raw_model)

        reference_mean = float(np.mean(reference))
        reference_std  = float(np.std(reference))
        reference_std  = reference_std if reference_std > 1e-6 else 1.0
        target = torch.tensor(
            (reference - reference_mean) / reference_std,
            dtype=torch.float32)

        nn_model  = ClimateBiasCorrectionGNN(
            num_node_features=graph.x.shape[1])
        optimizer = torch.optim.Adam(
            nn_model.parameters(), lr=self.learning_rate)

        nn_model.train()
        for _ in range(self.epochs):
            optimizer.zero_grad()
            prediction = nn_model(graph)
            loss       = F.mse_loss(prediction, target)
            loss.backward()
            optimizer.step()

        nn_model.eval()
        with torch.no_grad():
            corrected_normalized = nn_model(graph).cpu().numpy()

        corrected_values = (corrected_normalized * reference_std) + reference_mean
        raw_mae       = float(np.mean(np.abs(raw_model  - reference)))
        corrected_mae = float(np.mean(np.abs(corrected_values - reference)))

        return {
            "method"          : "GNN temporal graph correction",
            "epochs"          : int(self.epochs),
            "learning_rate"   : float(self.learning_rate),
            "raw_mae"         : raw_mae,
            "corrected_mae"   : corrected_mae,
            "improvement_pct" : float(
                ((raw_mae - corrected_mae) / raw_mae) * 100.0)
                if raw_mae > 1e-9 else 0.0,
            "raw_mean"        : metadata["raw_mean"],
            "corrected_mean"  : float(np.mean(corrected_values)),
            "reference_mean"  : reference_mean,
            "corrected_values": [float(v) for v in corrected_values],
        }
