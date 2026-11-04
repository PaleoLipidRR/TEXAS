# TEXAS/data/ocean_lookup.py
"""
Utilities for looking up modern ocean properties at paleo drill-site locations.

Typical use: provide the modern lat/lon of a sediment core and extract the
time-invariant modern nitrate climatology at that location to use as the NO₃
predictor in an invT reconstruction.

**Which product the nitrate comes from.** The ``ocean_prop_ds`` field mixes
two sources, and its own ``history`` attribute records which is which: the
nitrate variables (``no3_sf2tc_avg``, ``no3_tc``) are climatological annual
means (1993–2022) of the **CMEMS Global Ocean Biogeochemistry Hindcast**, and
the temperature variables are WOA23. So the default NO₃ lookup is a CMEMS
value on the WOA23 0.25° grid — the "associated CMEMS ocean nitrate product"
of the manuscript's Appendix C — not a WOA23 nitrate climatology. (The
manuscript uses WOA23 nitrate only for the per-site NO₃ *uncertainty* of the
EIV calibration, SI Text S2, which is a different file.) The function used to
be called ``lookup_no3_from_woa`` for that reason; the name is kept as a
deprecated alias.

The ``ocean_prop_ds`` dataset is NOT bundled in the wheel —
at ~20 MB it is too large for that (see ``tests/test_bundled_posteriors.py``'s
5 MB ceiling) — but it is downloadable on demand from Zenodo via
:func:`get_ocean_prop_ds`, which fetches and caches it automatically. It can
also still be generated locally via the preprocessing notebook (SI_code0).
Either way, pass the resulting xr.Dataset (with a ``(lat, lon)`` grid) to the
functions here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional, Union

import numpy as np
import xarray as xr

from ..utils.regrid import resolve_latlon_names


def get_ocean_prop_ds(
    cache_dir: Optional[Union[str, Path]] = None,
    force: bool = False,
) -> xr.Dataset:
    """
    Load the ``ocean_prop_ds`` ocean-properties field, downloading it from
    Zenodo on first use.

    This is the same dataset produced locally by ``SI_code00_PreProcessing``
    (``ds06_calculated_ocean_properties.nc``) — a gridded ``(lat, lon)``
    dataset carrying, among other variables, the thermocline-depth-integrated
    CMEMS nitrate climatology (``no3_sf2tc_avg``) alongside WOA23 temperature
    on the WOA23 0.25° grid. The download is cached
    (``~/.texas/data/spreadsheets/`` for pip installs, ``data/spreadsheets/``
    in the repo) so it only happens once; pass *force=True* to re-download.

    Parameters
    ----------
    cache_dir : Path or str, optional
        Directory to download/look for the file in.  Defaults to the
        standard training-data spreadsheets directory.
    force : bool
        Re-download even if the file is already cached.

    Returns
    -------
    xr.Dataset
        Opened with ``xr.open_dataset`` — suitable to pass directly as
        *ocean_dataset* to :func:`lookup_modern_no3` or as *no3_dataset* to
        :func:`~TEXAS.predict.predict_T_from_proxyObs`.
    """
    from ..utils.download import download_ocean_properties
    path = download_ocean_properties(dest_dir=cache_dir, force=force)
    return xr.open_dataset(path)


def lookup_modern_no3(
    lat: Union[float, np.ndarray],
    lon: Union[float, np.ndarray],
    ocean_dataset: xr.Dataset,
    variable: str = "no3_sf2tc_avg",
    method: Literal["linear", "nearest"] = "linear",
    *,
    lat_name: Optional[str] = None,
    lon_name: Optional[str] = None,
) -> np.ndarray:
    """
    Look up modern NO₃ at one or more lat/lon coordinates from the
    ``ocean_prop_ds`` ocean-properties Dataset.

    The dataset is typically the preprocessed ``ocean_prop_ds`` generated in
    SI_code00 (or fetched by :func:`get_ocean_prop_ds`), which contains the
    thermocline-depth-integrated **CMEMS** nitrate climatology on the regular
    WOA23 ``(lat, lon)`` grid.  The returned value(s) are time-invariant
    (climatological mean) and intended as a modern-ocean proxy for the NO₃
    correction in paleo reconstructions.

    Parameters
    ----------
    lat : float or array-like
        Latitude(s) in decimal degrees (−90 to 90).  Pass a scalar for a
        single drill site; pass an array of length N to match N observations.
    lon : float or array-like
        Longitude(s) in decimal degrees.  Both −180–180 and 0–360 conventions
        are accepted — the function normalizes to match the dataset's convention
        automatically.
    ocean_dataset : xr.Dataset
        The ``ocean_prop_ds`` field (or any dataset) on a regular
        latitude/longitude grid containing *variable*. The axis names are detected (``lat``/``lon``,
        ``latitude``/``longitude``, ``LAT``/``LON``, ...); pass *lat_name* /
        *lon_name* to override.
    variable : str
        Name of the NO₃ variable to extract.  Default ``"no3_sf2tc_avg"``
        (thermocline depth-integrated CMEMS annual mean from SI_code00).
    method : {"linear", "nearest"}
        Interpolation method.  ``"linear"`` (default) performs bilinear
        interpolation and is preferred for smooth fields.  ``"nearest"`` snaps
        to the closest grid cell and is useful when the dataset is sparse or
        has NaN-masked shelves.
    lat_name : str, optional
        Latitude coordinate name.  Auto-detected when omitted.
    lon_name : str, optional
        Longitude coordinate name.  Auto-detected when omitted.

    Returns
    -------
    np.ndarray
        NO₃ value(s) in µmol/L.  Shape matches the scalar/array input:
        a 0-d array for scalar inputs, 1-d array of length N for array inputs.
        NaN is returned for locations outside the dataset's valid range (e.g.
        continental shelves masked in the CMEMS product).

    Raises
    ------
    KeyError
        If *variable* is not found in *ocean_dataset*.
    ValueError
        If the latitude/longitude axes cannot be resolved, or the resolved
        names are coordinates but not dimensions.

    Examples
    --------
    Single drill site:

    >>> no3_val = lookup_modern_no3(15.3, -23.7, ocean_prop_ds)
    >>> # returns scalar-equivalent float; broadcasts to all N obs automatically
    >>> result = predict_T_from_proxyObs(..., no3=no3_val)

    Multi-site stack (per-obs lookup):

    >>> no3_arr = lookup_modern_no3(core_df["lat"].values,
    ...                              core_df["lon"].values,
    ...                              ocean_prop_ds)
    >>> result = predict_T_from_proxyObs(..., no3=no3_arr)
    """
    # ── Resolve the grid axes ─────────────────────────────────────────────────
    # utils/regrid.py already knows the spellings these grids arrive under; the
    # lookup used to hard-code "lat"/"lon" and fail on anything else.
    lat_name, lon_name = resolve_latlon_names(ocean_dataset, lat_name, lon_name)
    if lat_name not in ocean_dataset.dims or lon_name not in ocean_dataset.dims:
        raise ValueError(
            f"ocean_dataset must be on a regular grid: {lat_name!r} and "
            f"{lon_name!r} are coordinates but not dimensions. "
            f"Found dims: {list(ocean_dataset.dims)}"
        )
    if variable not in ocean_dataset:
        raise KeyError(
            f"Variable '{variable}' not found in ocean_dataset. "
            f"Available: {list(ocean_dataset.data_vars)}"
        )

    da: xr.DataArray = ocean_dataset[variable]

    # ── Normalize longitude convention ────────────────────────────────────────
    # Dataset may use 0–360; input may use −180–180 (or vice-versa).
    # Detect the dataset's convention from its lon coordinate range.
    ds_lon = da[lon_name].values
    ds_uses_0_360 = float(ds_lon.max()) > 180.0

    lon_arr = np.asarray(lon, dtype=float)
    if ds_uses_0_360:
        # Normalize input to 0–360
        lon_arr = lon_arr % 360.0
    else:
        # Normalize input to −180–180
        lon_arr = ((lon_arr + 180.0) % 360.0) - 180.0

    lat_arr = np.asarray(lat, dtype=float)
    scalar_input = lat_arr.ndim == 0

    # ── Interpolate ───────────────────────────────────────────────────────────
    if scalar_input:
        result = da.interp(
            {lat_name: float(lat_arr), lon_name: float(lon_arr)},
            method=method,
        )
        out = np.asarray(result.values, dtype=float)
    else:
        # Vectorised interpolation: build coordinate DataArrays so xarray
        # performs point-wise (not grid) interpolation.
        lat_da = xr.DataArray(lat_arr, dims="obs")
        lon_da = xr.DataArray(lon_arr, dims="obs")
        result = da.interp({lat_name: lat_da, lon_name: lon_da}, method=method)
        out = np.asarray(result.values, dtype=float)

    # ── Warn on NaN (masked shelf / land) ────────────────────────────────────
    n_nan = int(np.isnan(out).sum()) if out.ndim > 0 else int(np.isnan(out))
    if n_nan > 0:
        import warnings
        warnings.warn(
            f"lookup_modern_no3: {n_nan} location(s) returned NaN — likely "
            "on a continental shelf or land mask in the nitrate product. "
            "Consider using method='nearest' or check your lat/lon values.",
            UserWarning,
            stacklevel=2,
        )

    return out


def lookup_no3_from_woa(
    lat: Union[float, np.ndarray],
    lon: Union[float, np.ndarray],
    woa_dataset: xr.Dataset,
    variable: str = "no3_sf2tc_avg",
    method: Literal["linear", "nearest"] = "linear",
    *,
    lat_name: Optional[str] = None,
    lon_name: Optional[str] = None,
) -> np.ndarray:
    """
    Deprecated alias of :func:`lookup_modern_no3`.

    The name was wrong: the default ``no3_sf2tc_avg`` variable is the CMEMS
    nitrate climatology, not WOA23 (see the module docstring). Kept so existing
    calls keep working; emits a :class:`DeprecationWarning`.
    """
    import warnings
    warnings.warn(
        "lookup_no3_from_woa is deprecated: the nitrate it reads is the CMEMS "
        "climatology, not WOA23. Use lookup_modern_no3(lat, lon, ocean_dataset) "
        "instead; the behavior is identical.",
        DeprecationWarning, stacklevel=2,
    )
    return lookup_modern_no3(
        lat, lon, woa_dataset, variable, method,
        lat_name=lat_name, lon_name=lon_name,
    )
