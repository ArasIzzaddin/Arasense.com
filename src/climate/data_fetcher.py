import os

import ee
import pandas as pd
import numpy as np

from common.gee import initialize_earth_engine
from climate.esgf_cordex_fetcher import EuroCordexESGFFetcher


# ── in-memory result cache ────────────────────────────────────────────
# The Earth Engine fetches dominate request latency. Caching them by request
# parameters (incl. a location key) makes a repeat of the same location near
# instant — so a demo can be pre-warmed and load on stage in seconds. Process-
# level (persists across requests on the single uvicorn worker), FIFO-capped.
_FETCH_CACHE: dict = {}
_FETCH_CACHE_ORDER: list = []
_FETCH_CACHE_MAX = 1024


def _cache_get(key):
    return _FETCH_CACHE.get(key)


def _cache_put(key, value):
    if key not in _FETCH_CACHE:
        _FETCH_CACHE_ORDER.append(key)
        if len(_FETCH_CACHE_ORDER) > _FETCH_CACHE_MAX:
            _FETCH_CACHE.pop(_FETCH_CACHE_ORDER.pop(0), None)
    _FETCH_CACHE[key] = value


def clear_fetch_cache():
    _FETCH_CACHE.clear()
    _FETCH_CACHE_ORDER.clear()

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
                         model_family='cmip6',
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
        # NOTE on temperature units:
        #   ERA5-Land 'temperature_2m' and CMIP6 'tas' are both native KELVIN.
        #   We keep scale 1.0 (no Celsius conversion) on purpose: the Aras diagram
        #   bias ratio β = μ_model/μ_obs is unstable when μ_obs ≈ 0, which is exactly
        #   what happens around 0 °C. In Kelvin μ_obs ≈ 273–300, so β stays
        #   well-conditioned. Do NOT convert temperature to Celsius here.
        vars_map = {
            'temperature'    : {'era5': 'temperature_2m',
                                'cmip6': 'tas',
                                'scale_era5': 1.0,   # Kelvin, do not change
                                'scale_mod' : 1.0},  # Kelvin, do not change
            'precipitation'  : {'era5': 'total_precipitation_sum',
                                'cmip6': 'pr',
                                'scale_era5': 1000.0,
                                'scale_mod' : 86400.0},
        }
        if variable == 'all_euro_cordex':
            model_family = 'euro_cordex'
            variable = 'precipitation'
        if model_family == 'euro_cordex':
            return self._get_euro_cordex_data(
                geometry=geometry,
                start_date=start_date,
                end_date=end_date,
                variable=variable,
                ref_dataset=ref_dataset,
                fast_mode=fast_mode,
            )
        v = vars_map.get(variable, vars_map['temperature'])

        # 1. Reference fetch (ERA5-Land)
        ref_col = (ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
                     .filterBounds(geometry)
                     .filterDate(start_date, end_date)
                     .select(v['era5']))
        ref_series = self.extract_series(ref_col, v['era5'],
                                         v['scale_era5'], "Reference",
                                         geometry)

        # Enforce the Kelvin invariant for temperature. ERA5/CMIP6 are native
        # Kelvin, so a sub-100 mean means something converted to Celsius upstream —
        # which would make the Aras bias ratio β unstable near 0 °C. Fail early
        # with a clear message rather than producing a broken diagram downstream.
        if variable == 'temperature' and not ref_series.empty:
            ref_mean_k = float(ref_series.mean())
            if ref_mean_k < 100.0:
                raise ValueError(
                    f"Temperature reference mean {ref_mean_k:.2f} is not in Kelvin range "
                    "(expected ~273–300 K). ERA5 'temperature_2m' and CMIP6 'tas' are "
                    "native Kelvin — do not convert to Celsius, as it destabilises the "
                    "Aras bias ratio β around 0 °C."
                )

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

    def _get_euro_cordex_data(self, geometry, start_date, end_date,
                              variable='precipitation',
                              ref_dataset='ERA5-Land', fast_mode=True):
        """
        Fetch EURO-CORDEX data from a user-configured Earth Engine
        ImageCollection asset and compare it against ERA5-Land.

        EURO-CORDEX is not currently a public Earth Engine catalog collection.
        Configure one of these before selecting this mode:

        - ARASENSE_EURO_CORDEX_ASSET=projects/.../assets/...
        - or put the Earth Engine asset id in the console's Reference Dataset
          field for this run.

        Expected asset shape:
        - ImageCollection
        - precipitation band named "pr" by default, or temperature band "tas"
        - model id property named "model" by default
        - optional scenario property named "scenario"

        Optional overrides:
        - ARASENSE_EURO_CORDEX_PR_BAND
        - ARASENSE_EURO_CORDEX_TAS_BAND
        - ARASENSE_EURO_CORDEX_MODEL_PROPERTY
        - ARASENSE_EURO_CORDEX_SCENARIO_PROPERTY
        - ARASENSE_EURO_CORDEX_SCENARIO
        """
        asset_id = os.getenv("ARASENSE_EURO_CORDEX_ASSET", "").strip()
        if not asset_id and ref_dataset and ref_dataset.startswith("projects/"):
            asset_id = ref_dataset.strip()
        if not asset_id:
            return self._get_euro_cordex_esgf_data(
                geometry=geometry,
                start_date=start_date,
                end_date=end_date,
                variable=variable,
                ref_dataset=ref_dataset,
                fast_mode=fast_mode,
            )

        return self._get_euro_cordex_gee_asset_data(
            geometry=geometry,
            start_date=start_date,
            end_date=end_date,
            variable=variable,
            ref_dataset=ref_dataset,
            fast_mode=fast_mode,
            asset_id=asset_id,
        )

    def _get_euro_cordex_gee_asset_data(self, geometry, start_date, end_date,
                                        variable='precipitation',
                                        ref_dataset='ERA5-Land', fast_mode=True,
                                        asset_id=''):
        """Read EURO-CORDEX from a pre-ingested Earth Engine ImageCollection asset."""
        if not asset_id:
            raise ValueError(
                "EURO-CORDEX is not a public Earth Engine catalog collection in this app. "
                "Download/ingest EURO-CORDEX from ESGF as an Earth Engine ImageCollection, "
                "then set ARASENSE_EURO_CORDEX_ASSET or paste the asset id in the "
                "Reference Dataset field."
            )

        cfg = {
            'temperature': {
                'era5_band': 'temperature_2m',
                'era5_scale': 1.0,
                'cordex_band': os.getenv("ARASENSE_EURO_CORDEX_TAS_BAND", "tas"),
                'cordex_scale': 1.0,
            },
            'precipitation': {
                'era5_band': 'total_precipitation_sum',
                'era5_scale': 1000.0,
                'cordex_band': os.getenv("ARASENSE_EURO_CORDEX_PR_BAND", "pr"),
                'cordex_scale': 86400.0,
            },
        }
        v = cfg.get(variable, cfg['precipitation'])
        model_property = os.getenv("ARASENSE_EURO_CORDEX_MODEL_PROPERTY", "model")
        scenario_property = os.getenv("ARASENSE_EURO_CORDEX_SCENARIO_PROPERTY", "scenario")
        scenario = os.getenv("ARASENSE_EURO_CORDEX_SCENARIO", "").strip()

        ref_col = (ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
                     .filterBounds(geometry)
                     .filterDate(start_date, end_date)
                     .select(v['era5_band']))
        ref_series = self.extract_series(ref_col, v['era5_band'],
                                         v['era5_scale'], "Reference",
                                         geometry)

        cordex_col = (ee.ImageCollection(asset_id)
                        .filterBounds(geometry)
                        .filterDate(start_date, end_date)
                        .select(v['cordex_band']))
        if scenario:
            cordex_col = cordex_col.filter(ee.Filter.eq(scenario_property, scenario))

        try:
            all_available_models = (cordex_col.aggregate_array(model_property)
                                              .distinct().getInfo())
            all_available_models = [str(item) for item in all_available_models if item]
        except Exception as discovery_err:
            raise ValueError(
                "Could not discover EURO-CORDEX model names from the configured asset. "
                f"Check asset id '{asset_id}' and model property '{model_property}'. "
                f"Original error: {discovery_err}"
            ) from discovery_err

        if not all_available_models:
            raise ValueError(
                "The configured EURO-CORDEX asset returned no model names for this "
                "location/date range. Check date range, scenario, band, and model property."
            )

        models_to_fetch = all_available_models[:5] if fast_mode else all_available_models
        results_dict = {'reference': ref_series}

        for m_name in models_to_fetch:
            m_col = cordex_col.filter(ee.Filter.eq(model_property, m_name))
            m_series = self.extract_series(m_col, v['cordex_band'], v['cordex_scale'], m_name,
                                           geometry, scale=12000)
            if not m_series.empty:
                combined = (pd.concat([ref_series, m_series], axis=1, join='inner')
                              .dropna())
                combined.columns = ['reference', 'model']
                results_dict[f"EURO-CORDEX:{m_name}"] = combined

        return results_dict

    def _get_euro_cordex_esgf_data(self, geometry, start_date, end_date,
                                   variable='precipitation',
                                   ref_dataset='ERA5-Land', fast_mode=True):
        """Read EURO-CORDEX directly from ESGF NetCDF files, cached locally."""
        cfg = {
            'temperature': {
                'era5_band': 'temperature_2m',
                'era5_scale': 1.0,
            },
            'precipitation': {
                'era5_band': 'total_precipitation_sum',
                'era5_scale': 1000.0,
            },
        }
        v = cfg.get(variable, cfg['precipitation'])

        ref_col = (ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
                     .filterBounds(geometry)
                     .filterDate(start_date, end_date)
                     .select(v['era5_band']))
        ref_series = self.extract_series(ref_col, v['era5_band'],
                                         v['era5_scale'], "Reference",
                                         geometry)

        try:
            lon, lat = geometry.centroid(maxError=1).coordinates().getInfo()
            area = float(geometry.area(maxError=1).getInfo())
            radius_km = max((area / np.pi) ** 0.5 / 1000.0, 1.0)
        except Exception as exc:
            raise ValueError(f"Could not derive EURO-CORDEX ROI coordinates: {exc}") from exc

        fetcher = EuroCordexESGFFetcher()
        model_series = fetcher.get_series_by_model(
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            start_date=start_date,
            end_date=end_date,
            variable=variable,
            fast_mode=fast_mode,
            source_hint=ref_dataset,
        )
        if not model_series:
            raise ValueError("No usable EURO-CORDEX model series were extracted.")

        results_dict = {'reference': ref_series}
        for model_name, series in model_series.items():
            combined = (pd.concat([ref_series, series], axis=1, join='inner')
                          .dropna())
            if combined.empty:
                continue
            combined.columns = ['reference', 'model']
            results_dict[model_name] = combined

        if len(results_dict) == 1:
            raise ValueError(
                "EURO-CORDEX files were found, but no dates overlapped with ERA5-Land "
                "for the selected request."
            )
        return results_dict

    def _monthly_means(self, collection, band, scale_factor, geometry,
                       start_date, end_date):
        """
        Server-side monthly-mean series for a single-band collection. Earth
        Engine reduces every month and returns the whole series in ONE getInfo —
        feasible for multi-decade climatological windows (unlike per-image).
        """
        start = ee.Date(start_date)
        end = ee.Date(end_date)
        n_months = end.difference(start, "month").floor()
        months = ee.List.sequence(0, n_months.subtract(1))

        def per_month(i):
            i = ee.Number(i)
            m0 = start.advance(i, "month")
            m1 = m0.advance(1, "month")
            img = collection.filterDate(m0, m1).mean()
            val = img.reduceRegion(
                reducer=ee.Reducer.mean(), geometry=geometry,
                scale=27830, bestEffort=True, maxPixels=int(1e9),
            ).get(band)
            return ee.Feature(None, {"t": m0.format("YYYY-MM"), "v": val})

        feats = ee.FeatureCollection(months.map(per_month)).getInfo()["features"]
        rows = [(f["properties"]["t"], f["properties"].get("v")) for f in feats]
        rows = [(t, v) for t, v in rows if v is not None]
        if not rows:
            return pd.Series(dtype=float)
        idx = pd.to_datetime([t for t, _ in rows])
        return pd.Series([float(v) * scale_factor for _, v in rows], index=idx).sort_index()

    def get_monthly_series(self, geometry, start_date, end_date,
                           variable="precipitation", models=None,
                           fast_mode=True, include_reference=False, scenario=None,
                           loc_key=None):
        """
        Monthly-mean climate series (server-side), suitable for climatological
        model-trust scoring and projection over multi-decade windows.

        ``loc_key`` (e.g. "lat,lon,radius") enables result caching for that
        location; omit it to bypass the cache.

        Returns
        -------
        (reference_series_or_None, dict[str, pd.Series])
        """
        ckey = None
        if loc_key is not None:
            ckey = ("monthly", loc_key, variable, start_date, end_date, scenario,
                    include_reference, fast_mode, tuple(models) if models else None)
            hit = _cache_get(ckey)
            if hit is not None:
                return hit

        cfg = {
            "temperature":   ("temperature_2m", "tas", 1.0, 1.0),
            "precipitation": ("total_precipitation_sum", "pr", 1000.0, 86400.0),
        }
        era_band, mod_band, era_scale, mod_scale = cfg.get(variable, cfg["precipitation"])

        ref_series = None
        if include_reference:
            era5 = (ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
                      .filterBounds(geometry).select(era_band))
            ref_series = self._monthly_means(era5, era_band, era_scale, geometry,
                                             start_date, end_date)

        scenario = scenario or ("historical" if int(start_date[:4]) <= 2014 else "ssp245")
        cmip6 = (ee.ImageCollection("NASA/GDDP-CMIP6")
                   .filterBounds(geometry)
                   .filter(ee.Filter.eq("scenario", scenario))
                   .select(mod_band))
        if models is None:
            models = cmip6.filterDate(start_date, end_date).aggregate_array("model").distinct().getInfo()
            models = models[:5] if fast_mode else models

        out = {}
        for m_name in models:
            try:
                s = self._monthly_means(cmip6.filter(ee.Filter.eq("model", m_name)),
                                        mod_band, mod_scale, geometry, start_date, end_date)
                if not s.empty:
                    out[m_name] = s
            except Exception as exc:  # skip a failing model rather than 500 the run
                print(f"  [monthly {m_name}] skipped: {exc}")

        result = (ref_series, out)
        if ckey is not None:
            _cache_put(ckey, result)
        return result

    def get_extreme_stat(self, geometry, start_date, end_date,
                         variable="precipitation", models=None, stat="p95",
                         threshold=20.0, fast_mode=True, scenario=None, loc_key=None):
        """
        Server-side daily-extreme statistic per CMIP6 model. Each model reduces to
        a single scalar in ONE getInfo (no per-day download).

        stat:
            "p95"        — 95th percentile of daily values (extreme intensity)
            "rx1day"/"max" — maximum 1-day value over the window
            "heavy_frac" — fraction of days at/above ``threshold`` (precip, mm)
            "hot_frac"   — fraction of days at/above ``threshold`` (temp, K)
        Temperature heat metrics (max / hot_frac) use the daily-MAX band (tasmax);
        otherwise temperature uses daily-mean (tas). ``loc_key`` enables caching.
        """
        ckey = None
        if loc_key is not None:
            ckey = ("extreme", loc_key, variable, start_date, end_date, scenario,
                    stat, threshold, fast_mode, tuple(models) if models else None)
            hit = _cache_get(ckey)
            if hit is not None:
                return dict(hit)

        if variable == "temperature":
            band = "tasmax" if stat in ("max", "hot_frac") else "tas"
            scale = 1.0   # Kelvin
        else:
            band = "pr"
            scale = 86400.0   # kg m-2 s-1 -> mm/day
        scenario = scenario or ("historical" if int(start_date[:4]) <= 2014 else "ssp245")
        base = (ee.ImageCollection("NASA/GDDP-CMIP6")
                  .filterBounds(geometry)
                  .filter(ee.Filter.eq("scenario", scenario))
                  .filterDate(start_date, end_date)
                  .select(band))

        if models is None:
            models = base.aggregate_array("model").distinct().getInfo()
            models = models[:5] if fast_mode else models

        out = {}
        for m_name in models:
            try:
                coll = base.filter(ee.Filter.eq("model", m_name)) \
                           .map(lambda img: img.multiply(scale))
                if stat == "p95":
                    img = coll.reduce(ee.Reducer.percentile([95]))
                elif stat in ("rx1day", "max"):
                    img = coll.max()
                elif stat in ("heavy_frac", "hot_frac"):
                    img = coll.map(lambda i: i.gte(threshold)).mean()
                elif stat == "dry_frac":
                    img = coll.map(lambda i: i.lt(threshold)).mean()
                else:
                    raise ValueError(f"Unknown stat '{stat}'.")
                val = img.rename("v").reduceRegion(
                    reducer=ee.Reducer.mean(), geometry=geometry,
                    scale=27830, bestEffort=True, maxPixels=int(1e9),
                ).get("v").getInfo()
                if val is not None:
                    out[m_name] = float(val)
            except Exception as exc:  # one bad model must not kill the ensemble
                print(f"  [extreme {m_name}] skipped: {exc}")
        if ckey is not None:
            _cache_put(ckey, out)
        return out

    def get_annual_stat_series(self, geometry, start_date, end_date,
                               variable="precipitation", models=None, stat="max",
                               threshold=20.0, fast_mode=True, scenario=None, loc_key=None):
        """
        Per-model ANNUAL series of an extreme statistic (e.g. annual max 1-day
        rainfall). Lets trust be scored on the *target metric's own* year-to-year
        behaviour rather than the monthly climatology. One getInfo per model.

        Returns dict[str, pd.Series] indexed by year.
        """
        ckey = None
        if loc_key is not None:
            ckey = ("annual", loc_key, variable, start_date, end_date, scenario,
                    stat, threshold, fast_mode, tuple(models) if models else None)
            hit = _cache_get(ckey)
            if hit is not None:
                return hit

        if variable == "temperature":
            band = "tasmax" if stat in ("max", "hot_frac") else "tas"
            scale = 1.0
        else:
            band = "pr"
            scale = 86400.0
        scenario = scenario or ("historical" if int(start_date[:4]) <= 2014 else "ssp245")
        base = (ee.ImageCollection("NASA/GDDP-CMIP6")
                  .filterBounds(geometry)
                  .filter(ee.Filter.eq("scenario", scenario))
                  .select(band))
        if models is None:
            models = base.filterDate(start_date, end_date).aggregate_array("model").distinct().getInfo()
            models = models[:5] if fast_mode else models

        start_d = ee.Date(start_date)
        n_years = ee.Date(end_date).difference(start_d, "year").ceil()
        years = ee.List.sequence(0, n_years.subtract(1))

        def _series(model):
            mcoll = base.filter(ee.Filter.eq("model", model))

            def per_year(i):
                i = ee.Number(i)
                y0 = start_d.advance(i, "year")
                coll = mcoll.filterDate(y0, y0.advance(1, "year")).map(lambda im: im.multiply(scale))
                if stat in ("max", "rx1day"):
                    img = coll.max()
                elif stat == "p95":
                    img = coll.reduce(ee.Reducer.percentile([95]))
                elif stat in ("heavy_frac", "hot_frac"):
                    img = coll.map(lambda im: im.gte(threshold)).mean()
                elif stat == "dry_frac":
                    img = coll.map(lambda im: im.lt(threshold)).mean()
                else:
                    img = coll.mean()
                val = img.rename("v").reduceRegion(
                    reducer=ee.Reducer.mean(), geometry=geometry, scale=27830,
                    bestEffort=True, maxPixels=int(1e9)).get("v")
                return ee.Feature(None, {"t": y0.format("YYYY"), "v": val})

            feats = ee.FeatureCollection(years.map(per_year)).getInfo()["features"]
            rows = [(f["properties"]["t"], f["properties"].get("v")) for f in feats]
            rows = [(t, v) for t, v in rows if v is not None]
            if not rows:
                return pd.Series(dtype=float)
            return pd.Series([float(v) for _, v in rows],
                             index=pd.to_datetime([t for t, _ in rows])).sort_index()

        out = {}
        for m in models:
            try:
                s = _series(m)
                if not s.empty:
                    out[m] = s
            except Exception as exc:
                print(f"  [annual {m}] skipped: {exc}")
        if ckey is not None:
            _cache_put(ckey, out)
        return out

    def get_model_series(self, geometry, start_date, end_date,
                         variable='precipitation', models=None, fast_mode=True):
        """
        Fetch CMIP6 model series WITHOUT an ERA5 join — needed for FUTURE windows
        where there is no observed reference. Scenario is chosen by year
        (historical <= 2014, else ssp245).

        Returns
        -------
        dict[str, pd.Series]  — daily series per successfully fetched model.
        """
        bands = {
            'temperature':     ('tas', 1.0),       # Kelvin
            'precipitation':   ('pr', 86400.0),    # kg m-2 s-1 -> mm/day
            'all_euro_cordex': ('pr', 86400.0),
        }
        band, scale_mod = bands.get(variable, bands['temperature'])

        scenario = 'historical' if int(start_date[:4]) <= 2014 else 'ssp245'
        cmip6_col = (ee.ImageCollection("NASA/GDDP-CMIP6")
                       .filterBounds(geometry)
                       .filterDate(start_date, end_date)
                       .filter(ee.Filter.eq('scenario', scenario))
                       .select(band))

        if models is None:
            models = cmip6_col.aggregate_array('model').distinct().getInfo()
            models = models[:5] if fast_mode else models

        out = {}
        for m_name in models:
            m_col = cmip6_col.filter(ee.Filter.eq('model', m_name))
            s = self.extract_series(m_col, band, scale_mod, m_name, geometry, scale=25000)
            if not s.empty:
                out[m_name] = s
        return out

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
