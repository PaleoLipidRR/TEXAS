"""Curvilinear -> regular lat/lon regridding with an xesmf-or-scipy backend.

Uses xesmf (ESMF) when esmpy is importable; otherwise a pure-pip scipy fallback,
so the regrid runs in any environment (including uv, which cannot install esmpy).
"""
from __future__ import annotations

import numpy as np

_SEAM_PAD_DEG = 5.0
_LAT_CANDIDATES = ["TLAT", "lat", "latitude", "LAT", "Lat"]
_LON_CANDIDATES = ["TLONG", "lon", "longitude", "LON", "Lon", "LONG"]


def _prepare_grids(ds, lat_name, lon_name, target_res, lat_range, lon_range):
    if lat_name is None:
        lat_name = next((c for c in _LAT_CANDIDATES if c in ds), None)
    if lon_name is None:
        lon_name = next((c for c in _LON_CANDIDATES if c in ds), None)
    if lat_name is None or lon_name is None:
        raise ValueError(
            f"Could not auto-detect lat/lon coordinates. Available: {list(ds.variables)}. "
            "Pass lat_name and lon_name explicitly."
        )
    lat_dims, lon_dims = ds[lat_name].dims, ds[lon_name].dims
    if lat_dims != lon_dims:
        raise ValueError(f"lat/lon have different dims: {lat_dims} vs {lon_dims}")
    if len(lat_dims) != 2:
        raise ValueError(f"Expected 2-D curvilinear coords, got {len(lat_dims)}-D: {lat_dims}")
    lat_dim, lon_dim = lat_dims
    src_lat = np.asarray(ds[lat_name].values, dtype=float).copy()
    src_lon = np.asarray(ds[lon_name].values, dtype=float).copy()
    if lon_range[0] < 0 and src_lon.min() >= 0:
        src_lon = np.where(src_lon > 180, src_lon - 360, src_lon)
    elif lon_range[0] >= 0 and src_lon.min() < 0:
        src_lon = np.where(src_lon < 0, src_lon + 360, src_lon)
    lat_out = np.arange(lat_range[0], lat_range[1] + target_res / 2, target_res)
    lon_out = np.arange(lon_range[0], lon_range[1] + target_res / 2, target_res)
    return {
        "lat_name": lat_name, "lon_name": lon_name,
        "lat_dim": lat_dim, "lon_dim": lon_dim,
        "src_lat": src_lat, "src_lon": src_lon,
        "lat_out": lat_out, "lon_out": lon_out,
    }
