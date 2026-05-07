import ee
import numpy as np
import torch
from torch_geometric.data import Data

from common.gee import initialize_earth_engine


class ArasenseGraphBuilder:
    """
    Builds a hydrological graph from DEM + climate signal.

    Node features (4 total):
        0: elevation      — normalised by 3000 m
        1: slope          — normalised by 90°
        2: precip_mean    — mean daily precip from best CMIP6 model (mm/day),
                            normalised by 50 mm
        3: precip_anomaly — (model_mean - era5_mean) / era5_std
                            bounded to [-3, 3] to avoid extreme outliers

    CHANGES vs original
    -------------------
    - Added `precip_mean` and `precip_anomaly` parameters to
      `build_hydrological_graph()` — both default to 0.0 so existing
      callers keep working with no changes.
    - Node feature tensor now has shape [N, 4] instead of [N, 2].
    - Added `num_node_features` property so GNN can read it dynamically.
    """

    NUM_NODE_FEATURES = 4   # elevation, slope, precip_mean, precip_anomaly

    def __init__(self, project_id: str):
        try:
            initialize_earth_engine(project_id)
        except Exception as e:
            print(f"Error initialising Earth Engine: {e}")
            raise

    def build_hydrological_graph(
        self,
        region,                     # ee.Geometry
        scale: int = 1000,
        precip_mean: float = 0.0,   # NEW — from FloodClimatePipeline
        precip_anomaly: float = 0.0 # NEW — from FloodClimatePipeline
    ) -> tuple:
        """
        Extract DEM and build a D8 flow-direction graph enriched with
        the best-model climate signal.

        Parameters
        ----------
        region         : ee.Geometry
        scale          : DEM resolution in metres
        precip_mean    : mean daily precip from best CMIP6 model (mm/day)
        precip_anomaly : normalised bias of best model vs ERA5

        Returns
        -------
        (Data, (rows, cols))
        """
        print(f"Building hydrological graph at {scale} m resolution...")
        print(f"  Climate features: precip_mean={precip_mean:.3f} mm/day, "
              f"precip_anomaly={precip_anomaly:.3f}")

        # 1. DEM + slope
        # Use bounding box for sampleRectangle — circular geometries cause
        # "fully masked pixels" error because sampleRectangle uses a rectangle
        # internally and the clipped image has masked pixels outside the circle.
        bbox = region.bounds(maxError=1)
        dem        = ee.Image("USGS/SRTMGL1_003").unmask(0)
        slope_img  = ee.Terrain.slope(dem).unmask(0)
        full_img   = (dem.addBands(slope_img)
                        .rename(["elevation", "slope"])
                        .reproject(crs="EPSG:4326", scale=scale))

        pixel_data = full_img.sampleRectangle(bbox, defaultValue=0)
        elevation  = np.array(pixel_data.get("elevation").getInfo())
        slope      = np.array(pixel_data.get("slope").getInfo())

        rows, cols = elevation.shape
        num_nodes  = rows * cols

        # 2. Normalise climate features
        #    precip_mean    → divide by 50 mm (heavy rain threshold)
        #    precip_anomaly → clip to [-3, 3] std devs
        p_mean_norm  = np.full(num_nodes, precip_mean / 50.0, dtype=np.float32)
        p_anom_norm  = np.full(
            num_nodes,
            float(np.clip(precip_anomaly, -3.0, 3.0)) / 3.0,
            dtype=np.float32,
        )

        # 3. Node feature matrix [N, 4]
        x = torch.tensor(
            np.stack([
                elevation.flatten() / 3000.0,
                slope.flatten()     / 90.0,
                p_mean_norm,
                p_anom_norm,
            ], axis=1),
            dtype=torch.float,
        )

        # 4. D8 flow edges — connect each pixel to lower-elevation neighbours
        edge_list = []
        for r in range(rows):
            for c in range(cols):
                curr_idx  = r * cols + c
                curr_elev = elevation[r, c]
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            if elevation[nr, nc] < curr_elev:
                                edge_list.append([curr_idx, nr * cols + nc])

        if edge_list:
            edge_index = (torch.tensor(edge_list, dtype=torch.long)
                            .t().contiguous())
        else:
            edge_index = torch.zeros((2, 0), dtype=torch.long)

        graph_data = Data(x=x, edge_index=edge_index)
        print(f"  Graph: {num_nodes} nodes, {edge_index.shape[1]} edges, "
              f"{self.NUM_NODE_FEATURES} features/node")
        return graph_data, (rows, cols)


if __name__ == "__main__":
    PROJECT_ID = "valid-shine-488311-d6"
    builder    = ArasenseGraphBuilder(PROJECT_ID)
    roi        = ee.Geometry.Rectangle([11.0, 44.2, 12.0, 44.8])
    graph, shape = builder.build_hydrological_graph(
        roi, scale=2000,
        precip_mean=12.5,   # example: 12.5 mm/day from best CMIP6 model
        precip_anomaly=-0.3
    )
    print(f"Node feature shape : {graph.x.shape}")   # → [N, 4]
    print(f"Edge index shape   : {graph.edge_index.shape}")
