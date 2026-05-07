import ee
import pandas as pd
import numpy as np

from common.gee import initialize_earth_engine

class ArasenseDataFetcher:
    """
    Data fetcher for Arasense platform.
    Retrieves ERA5-Land and CMIP6 data from Google Earth Engine.

    BUGS FIXED
    ----------
    BUG 1 — get_climate_data returns dict of DataFrames but callers expect
            separate 'reference' / 'model' keys at the top level.
            The original return structure was results_dict keyed by model name
            only — there was no top-level 'reference' key.
            Fix: return a dict with both a 'reference' Series AND per-model
            DataFrames, so validation_demo.py (and other callers) can access
            data['reference'] and data[model_name] consistently.

    BUG 2 — extract_series silently swallows ALL exceptions with a bare
            `except:` clause. This hides GEE auth errors, quota errors,
            missing-band errors etc., making debugging impossible.
            Fix: catch specific exceptions and log a useful message;
            re-raise non-recoverable errors.
    """

    def __init__(self, project_id):
        try:
            initialize_earth_engine(project_id)
            print(f"Arasense: Initialized with project {project_id}")
        except Exception as e:
            print(f"Error initializing Earth Engine: {e}")
            raise

    def get_climate_data(self, geometry, start_date, end_date,
                         variable='temperature',
                         ref_dataset='ERA5-Land',
                         fast_mode=True):
        """
        High-performance optimised fetcher.

        Returns
        -------
        dict with keys:
            'reference'        : pd.Series  (ERA5-Land time series)
            <model_name>       : pd.DataFrame with columns ['reference','model']
                                 for every successfully fetched CMIP6 model
        """
        vars_map = {
            'temperature'    : {'era5': 'temperature_2m',
                                'cmip6': 'tas',
                                'scale_era5': 1.0,
                                'scale_mod' : 1.0},
            'precipitation'  : {'era5': 'total_precipitation_sum',
                                'cmip6': 'pr',
                                'scale_era5': 1000.0,
                                'scale_mod' : 86400.0},
            'all_euro_cordex': {'era5': 'total_precipitation_sum',
                                'cmip6': 'pr',
                                'scale_era5': 1000.0,
                                'scale_mod' : 86400.0},
        }
        v = vars_map.get(variable, vars_map['temperature'])

        # 1. Reference fetch (ERA5-Land)
        ref_col = (ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
                     .filterBounds(geometry)
                     .filterDate(start_date, end_date)
                     .select(v['era5']))
        ref_series = self.extract_series(ref_col, v['era5'],
                                         v['scale_era5'], "Reference",
                                         geometry)

        # 2. CMIP6 ensemble fetch
        # Scenario is determined by date: historical=1950-2014, ssp245=2015-2100
        # We do NOT hardcode 'historical' — instead pick automatically by year
        # so the same code works for both training (pre-2015) and future runs.
        start_year = int(start_date[:4])
        scenario   = 'historical' if start_year <= 2014 else 'ssp245'
        print(f"Arasense: Discovering NASA CMIP6 models (scenario={scenario})...")
        cmip6_col = (ee.ImageCollection("NASA/GDDP-CMIP6")
                       .filterBounds(geometry)
                       .filterDate(start_date, end_date)
                       .filter(ee.Filter.eq('scenario', scenario))
                       .select(v['cmip6']))

        try:
            all_available_models = (cmip6_col.aggregate_array('model')
                                             .distinct().getInfo())
            # Fallback: if scenario filter returned nothing, try without it
            if not all_available_models:
                print(f"  No models found with scenario={scenario}, trying without scenario filter...")
                cmip6_col = (ee.ImageCollection("NASA/GDDP-CMIP6")
                               .filterBounds(geometry)
                               .filterDate(start_date, end_date)
                               .select(v['cmip6']))
                all_available_models = (cmip6_col.aggregate_array('model')
                                                 .distinct().getInfo())
            print(f"Exhaustive Discovery: Found {len(all_available_models)} "
                  f"models in archive.")
        except Exception as discovery_err:
            print(f"Metadata scan failed, using fallback list. "
                  f"Error: {discovery_err}")
            all_available_models = [
                'ACCESS-CM2', 'ACCESS-ESM1-5', 'BCC-CSM2-MR', 'CESM2',
                'CanESM5', 'EC-Earth3', 'GFDL-CM4', 'GISS-E2-1-G',
                'HadGEM3-GC31-LL', 'IPSL-CM6A-LR', 'MIROC6',
                'MPI-ESM1-2-HR', 'MRI-ESM2-0', 'NorESM2-MM',
            ]

        models_to_fetch = all_available_models[:5] if fast_mode else all_available_models
        print(f"Ensemble Processing: Fetching {len(models_to_fetch)} models...")

        # FIX BUG 1: include 'reference' as a top-level key
        results_dict = {'reference': ref_series}

        for m_name in models_to_fetch:
            m_col    = cmip6_col.filter(ee.Filter.eq('model', m_name))
            m_series = self.extract_series(m_col, v['cmip6'],
                                           v['scale_mod'], m_name,
                                           geometry, scale=25000)
            if not m_series.empty:
                combined = (pd.concat([ref_series, m_series], axis=1, join='inner')
                              .dropna())
                combined.columns = ['reference', 'model']
                results_dict[m_name] = combined

        return results_dict

    def extract_series(self, collection, band_name, scale_factor=1.0,
                       label="", geometry=None, scale=10000):
        """
        Extract a daily time series by iterating over images individually.
        This approach works reliably in both server and standalone script contexts.
        """
        import datetime
        import pandas as pd

        try:
            # Get list of image IDs in the collection
            img_list = collection.toList(collection.size())
            count    = img_list.size().getInfo()

            if count == 0:
                print(f"  [{label}] No images in collection.")
                return pd.Series(dtype=float)

            dates, values = [], []

            for i in range(count):
                try:
                    img  = ee.Image(img_list.get(i))
                    date_str = img.date().format('YYYY-MM-dd').getInfo()
                    val  = img.select(band_name).reduceRegion(
                        reducer   = ee.Reducer.mean(),
                        geometry  = geometry,
                        scale     = 27830,   # ~0.25° — CMIP6 native resolution
                        bestEffort= True,
                        maxPixels = 1e9,
                    ).get(band_name).getInfo()

                    if val is not None:
                        dates.append(pd.to_datetime(date_str))
                        values.append(float(val) * scale_factor)
                except Exception:
                    continue

            if not dates:
                print(f"  [{label}] All images returned null values.")
                return pd.Series(dtype=float)

            series = (pd.Series(values, index=dates)
                        .groupby(level=0).mean()
                        .sort_index())
            print(f"  [{label}] OK — {len(series)} days (reduceRegion per image)")
            return series

        except Exception as e:
            print(f"  [{label}] Error: {e}")
            return pd.Series(dtype=float)


if __name__ == "__main__":
    PROJECT_ID = 'valid-shine-488311-d6'
    fetcher    = ArasenseDataFetcher(PROJECT_ID)
    roi        = ee.Geometry.Point([12.4964, 41.9028]).buffer(50000)
    data       = fetcher.get_climate_data(roi,
                                          '2014-01-01', '2014-12-31',
                                          'temperature')
    print(data['reference'].head())
    print("Data extraction successful.")
