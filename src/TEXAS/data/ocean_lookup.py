# TEXAS/data/ocean_lookup.py
"""
Utilities for looking up modern ocean properties at paleo drill-site locations.

Typical use: provide the modern lat/lon of a sediment core and extract the
time-invariant WOA23 nitrate climatology at that location to use as the NO₃
predictor in an invT reconstruction.

The WOA23-derived dataset is NOT bundled with TEXAS — it is generated in the
preprocessing notebook (SI_code1) and loaded by the user.  Pass the resulting
xr.Dataset (with a ``(lat, lon)`` grid) to the functions here.
"""

from __future__ import annotations

from typing import Literal, Union

import numpy as np
import xarray as xr


def lookup_no3_from_woa(
    lat: Union[float, np.ndarray],
    lon: Union[float, np.ndarray],
    woa_dataset: xr.Dataset,
    variable: str = "no3_sf2tc_avg",
    method: Literal["linear", "nearest"] = "linear",
) -> np.ndarray:
    """
    Look up modern NO₃ at one or more lat/lon coordinates from a WOA23-derived
    xarray Dataset.

    The dataset is typically the preprocessed ``ocean_prop_ds`` generated in
    SI_code1, which contains thermocline-depth-integrated WOA23 climatology on
    a regular ``(lat, lon)`` grid.  The returned value(s) are time-invariant
    (climatological mean) and intended as a modern-ocean proxy for the NO₃
    correction in paleo reconstructions.

    Parameters
    ----------
    lat : float or array-like
        Latitude(s) in decimal degrees (−90 to 90).  Pass a scalar for a
        single drill site; pass an array of length N to match N observations.
    lon : float or array-like
        Longitude(s) in decimal degrees.  Both −180–180 and 0–360 conventions
        are accepted — the function normalises to match the dataset's convention
        automatically.
    woa_dataset : xr.Dataset
        WOA23-derived dataset with a ``(lat, lon)`` grid containing *variable*.
        Dimensions must be named ``"lat"`` and ``"lon"``.
    variable : str
        Name of the NO₃ variable to extract.  Default ``"no3_sf2tc_avg"``
        (thermocline depth-integrated annual average from SI_code1).
    method : {"linear", "nearest"}
        Interpolation method.  ``"linear"`` (default) performs bilinear
        interpolation and is preferred for smooth fields.  ``"nearest"`` snaps
        to the closest grid cell and is useful when the dataset is sparse or
        has NaN-masked shelves.

    Returns
    -------
    np.ndarray
        NO₃ value(s) in µmol/L.  Shape matches the scalar/array input:
        a 0-d array for scalar inputs, 1-d array of length N for array inputs.
        NaN is returned for locations outside the dataset's valid range (e.g.
        continental shelves masked in WOA23).

    Raises
    ------
    KeyError
        If *variable* is not found in *woa_dataset*.
    ValueError
        If *woa_dataset* does not have ``"lat"`` and ``"lon"`` dimensions.

    Examples
    --------
    Single drill site:

    >>> no3_val = lookup_no3_from_woa(15.3, -23.7, ocean_prop_ds)
    >>> # returns scalar-equivalent float; broadcasts to all N obs automatically
    >>> result = predict_T_from_proxyObs(..., no3=no3_val)

    Multi-site stack (per-obs lookup):

    >>> no3_arr = lookup_no3_from_woa(core_df["lat"].values,
    ...                                core_df["lon"].values,
    ...                                ocean_prop_ds)
    >>> result = predict_T_from_proxyObs(..., no3=no3_arr)
    """
    # ── Validate dataset ──────────────────────────────────────────────────────
    if "lat" not in woa_dataset.dims or "lon" not in woa_dataset.dims:
        raise ValueError(
            "woa_dataset must have 'lat' and 'lon' dimensions. "
            f"Found: {list(woa_dataset.dims)}"
        )
    if variable not in woa_dataset:
        raise KeyError(
            f"Variable '{variable}' not found in woa_dataset. "
            f"Available: {list(woa_dataset.data_vars)}"
        )

    da: xr.DataArray = woa_dataset[variable]

    # ── Normalise longitude convention ────────────────────────────────────────
    # Dataset may use 0–360; input may use −180–180 (or vice-versa).
    # Detect the dataset's convention from its lon coordinate range.
    ds_lon = da["lon"].values
    ds_uses_0_360 = float(ds_lon.max()) > 180.0

    lon_arr = np.asarray(lon, dtype=float)
    if ds_uses_0_360:
        # Normalise input to 0–360
        lon_arr = lon_arr % 360.0
    else:
        # Normalise input to −180–180
        lon_arr = ((lon_arr + 180.0) % 360.0) - 180.0

    lat_arr = np.asarray(lat, dtype=float)
    scalar_input = lat_arr.ndim == 0

    # ── Interpolate ───────────────────────────────────────────────────────────
    if scalar_input:
        result = da.interp(
            lat=float(lat_arr),
            lon=float(lon_arr),
            method=method,
        )
        out = np.asarray(result.values, dtype=float)
    else:
        # Vectorised interpolation: build coordinate DataArrays so xarray
        # performs point-wise (not grid) interpolation.
        lat_da = xr.DataArray(lat_arr, dims="obs")
        lon_da = xr.DataArray(lon_arr, dims="obs")
        result = da.interp(lat=lat_da, lon=lon_da, method=method)
        out = np.asarray(result.values, dtype=float)

    # ── Warn on NaN (masked shelf / land) ────────────────────────────────────
    n_nan = int(np.isnan(out).sum()) if out.ndim > 0 else int(np.isnan(out))
    if n_nan > 0:
        import warnings
        warnings.warn(
            f"lookup_no3_from_woa: {n_nan} location(s) returned NaN — likely "
            "on a continental shelf or land mask in the WOA23 dataset. "
            "Consider using method='nearest' or check your lat/lon values.",
            UserWarning,
            stacklevel=2,
        )

    return out
