"""Prepare E-OBS NetCDF files for Google Earth Engine ingestion.

This script converts a daily E-OBS NetCDF variable into one GeoTIFF per day.
Upload those GeoTIFFs to an Earth Engine ImageCollection asset, then set
ARASENSE_EOBS_ASSET to that collection id.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


def _coord_name(ds: xr.Dataset, names: tuple[str, ...]) -> str:
    for name in names:
        if name in ds.coords or name in ds.dims:
            return name
    raise ValueError(f"Could not find any coordinate from {names}.")


def _variable_name(ds: xr.Dataset, requested: str | None, kind: str) -> str:
    if requested:
        if requested not in ds:
            raise ValueError(f"Variable '{requested}' not found. Available: {list(ds.data_vars)}")
        return requested
    candidates = {
        "precipitation": ("rr", "precipitation", "pr"),
        "temperature": ("tg", "temperature", "tas", "tmean"),
    }[kind]
    for name in candidates:
        if name in ds:
            return name
    raise ValueError(f"Could not infer {kind} variable. Available: {list(ds.data_vars)}")


def _band_name(kind: str, var_name: str) -> str:
    if kind == "precipitation":
        return "precipitation"
    return {
        "tg": "temperature",
        "tn": "temperature_min",
        "tx": "temperature_max",
    }.get(var_name, "temperature")


def _write_geotiff(path: Path, arr, lon, lat, nodata: float) -> None:
    try:
        import rasterio
        from rasterio.transform import from_bounds
    except ImportError as exc:
        raise ValueError("GeoTIFF export requires rasterio. Install requirements.txt first.") from exc

    data = np.asarray(arr, dtype="float32")
    lon = np.asarray(lon, dtype="float64")
    lat = np.asarray(lat, dtype="float64")

    if lat[0] < lat[-1]:
        data = np.flipud(data)
        lat = lat[::-1]

    west = float(lon.min())
    east = float(lon.max())
    south = float(lat.min())
    north = float(lat.max())
    lon_res = abs(float(lon[1] - lon[0])) if len(lon) > 1 else 0.1
    lat_res = abs(float(lat[1] - lat[0])) if len(lat) > 1 else 0.1
    transform = from_bounds(
        west - lon_res / 2,
        south - lat_res / 2,
        east + lon_res / 2,
        north + lat_res / 2,
        data.shape[1],
        data.shape[0],
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        nodata=nodata,
        compress="deflate",
    ) as dst:
        dst.write(np.where(np.isfinite(data), data, nodata).astype("float32"), 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="E-OBS NetCDF file.")
    parser.add_argument("--output-dir", required=True, help="Folder for GeoTIFFs and manifest JSON.")
    parser.add_argument("--kind", choices=["precipitation", "temperature"], required=True)
    parser.add_argument("--variable", help="NetCDF variable name, e.g. rr or tg.")
    parser.add_argument("--asset-prefix", required=True, help="Earth Engine image asset prefix.")
    parser.add_argument("--start-date", help="Optional YYYY-MM-DD filter.")
    parser.add_argument("--end-date", help="Optional YYYY-MM-DD filter.")
    parser.add_argument("--max-days", type=int, help="Optional limit for testing.")
    parser.add_argument("--nodata", type=float, default=-9999.0)
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    ds = xr.open_dataset(args.input)
    try:
        time_name = _coord_name(ds, ("time",))
        lat_name = _coord_name(ds, ("latitude", "lat"))
        lon_name = _coord_name(ds, ("longitude", "lon"))
        var_name = _variable_name(ds, args.variable, args.kind)

        da = ds[var_name]
        if args.start_date or args.end_date:
            da = da.sel({time_name: slice(args.start_date, args.end_date)})
        if args.max_days:
            da = da.isel({time_name: slice(0, args.max_days)})

        band = _band_name(args.kind, var_name)
        rows = []
        times = pd.to_datetime(da[time_name].values)
        for idx, timestamp in enumerate(times):
            day = pd.Timestamp(timestamp).strftime("%Y-%m-%d")
            safe_day = day.replace("-", "")
            values = da.isel({time_name: idx}).values
            if args.kind == "temperature":
                values = values.astype("float32") + 273.15
            else:
                values = values.astype("float32")

            tif = out_dir / f"eobs_{band}_{safe_day}.tif"
            _write_geotiff(tif, values, ds[lon_name].values, ds[lat_name].values, args.nodata)
            rows.append(
                {
                    "date": day,
                    "band": band,
                    "file": str(tif),
                    "asset_id": f"{args.asset_prefix.rstrip('/')}/eobs_{band}_{safe_day}",
                }
            )

        manifest = out_dir / f"eobs_{band}_upload_manifest.json"
        manifest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"Wrote {len(rows)} GeoTIFFs")
        print(f"Manifest: {manifest}")
    finally:
        ds.close()


if __name__ == "__main__":
    main()
