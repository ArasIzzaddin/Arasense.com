import ee
import numpy as np

from common.gee import initialize_earth_engine


class ArasenseFloodFetcher:
    """
    Fetches Sentinel-1 SAR flood masks from Earth Engine.
    Used for training the GNN surrogate.

    BUG FIXED
    ---------
    Original code returned `np.zeros((33, 40))` when no S1 images were
    found — a hardcoded shape that would silently corrupt training labels
    whenever the graph had a different number of nodes.
    Fix: accept `grid_shape` parameter so the zero mask always matches
    the graph dimensions exactly.
    """

    def __init__(self, project_id: str):
        try:
            initialize_earth_engine(project_id)
        except Exception as e:
            print(f"Error initialising Earth Engine: {e}")
            raise

    def get_flood_mask(
        self,
        region,
        start_date: str,
        end_date: str,
        scale: int = 1000,
        grid_shape: tuple = None,   # FIX: (rows, cols) from graph builder
    ) -> np.ndarray:
        """
        Generate a binary flood mask using Sentinel-1 SAR change detection.

        Parameters
        ----------
        region     : ee.Geometry
        start_date : str  "YYYY-MM-DD"
        end_date   : str  "YYYY-MM-DD"
        scale      : int  resolution in metres — must match graph_builder scale
        grid_shape : tuple (rows, cols) — must match graph node grid exactly

        Returns
        -------
        np.ndarray of shape (rows, cols), dtype uint8, values 0 or 1
        """
        print(f"Generating S1 flood mask {start_date} → {end_date}...")

        s1 = (ee.ImageCollection("COPERNICUS/S1_GRD")
                .filterBounds(region)
                .filter(ee.Filter.eq("instrumentMode", "IW")))

        flood_col = s1.filterDate(start_date, end_date)
        count     = flood_col.size().getInfo()

        if count == 0:
            print(f"  No S1 images found for {start_date}–{end_date}.")
            # FIX: use the actual graph shape, not a hardcoded constant
            if grid_shape is None:
                raise ValueError(
                    "No S1 images found and grid_shape is None. "
                    "Pass grid_shape=(rows, cols) from build_hydrological_graph()."
                )
            print(f"  Returning zero mask of shape {grid_shape}.")
            return np.zeros(grid_shape, dtype=np.uint8)

        post_flood = flood_col.median().select("VV")
        flood_mask = post_flood.lt(-18).rename("flood_mask")
        sampled    = (flood_mask
                        .reproject(crs="EPSG:4326", scale=scale)
                        .unmask(0))

        try:
            pixel_data  = sampled.sampleRectangle(region)
            mask_array  = np.array(
                pixel_data.get("flood_mask").getInfo(), dtype=np.uint8
            )
        except Exception as e:
            print(f"  S1 extraction error: {e}")
            if grid_shape is None:
                raise
            print(f"  Falling back to zero mask of shape {grid_shape}.")
            return np.zeros(grid_shape, dtype=np.uint8)

        # Validate shape matches the graph
        if grid_shape is not None and mask_array.shape != grid_shape:
            print(f"  Warning: S1 mask shape {mask_array.shape} != "
                  f"graph shape {grid_shape}. Resizing.")
            from PIL import Image as PILImage
            mask_pil   = PILImage.fromarray(mask_array)
            mask_array = np.array(
                mask_pil.resize(
                    (grid_shape[1], grid_shape[0]),
                    PILImage.NEAREST
                ), dtype=np.uint8
            )

        print(f"  Flood mask: {mask_array.shape}, "
              f"flooded nodes: {int(np.sum(mask_array))}")
        return mask_array


if __name__ == "__main__":
    PROJECT_ID = "valid-shine-488311-d6"
    fetcher    = ArasenseFloodFetcher(PROJECT_ID)
    er_roi     = ee.Geometry.Rectangle([11.0, 44.2, 12.0, 44.8])
    # Pass grid_shape so placeholder is correctly sized
    mask = fetcher.get_flood_mask(
        er_roi, "2023-05-15", "2023-05-25",
        scale=2000, grid_shape=(30, 50)
    )
    print(f"Flood mask shape : {mask.shape}")
    print(f"Flooded nodes    : {np.sum(mask)}")
