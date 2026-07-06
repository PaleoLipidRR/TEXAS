"""Curvilinear -> regular lat/lon regridding with an xesmf-or-scipy backend.

Uses xesmf (ESMF) when esmpy is importable; otherwise a pure-pip scipy fallback,
so the regrid runs in any environment (including uv, which cannot install esmpy).
"""
from __future__ import annotations

import numpy as np
import xarray as xr
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
from scipy.spatial import Delaunay

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


def _interp_factory(method, points):
    """Return (build_tri, make_interp) so triangulation is reused across time steps."""
    if method in ("bilinear",):
        tri = Delaunay(points)
        return lambda values: LinearNDInterpolator(tri, values, fill_value=np.nan)
    if method in ("nearest", "nearest_s2d", "nearest_d2s"):
        return lambda values: NearestNDInterpolator(points, values)
    raise ValueError(
        f"method={method!r} is not supported by the scipy fallback "
        "(conservative/patch need xesmf/esmpy). Use method='bilinear' "
        "or install esmpy (conda-forge)."
    )


def _regrid_scipy(ds, var_names, grids, method, periodic, squeeze_dims, keep_attrs):
    if isinstance(var_names, str):
        var_names = [var_names]
    lat_dim, lon_dim = grids["lat_dim"], grids["lon_dim"]
    src_lat, src_lon = grids["src_lat"], grids["src_lon"]
    lat_out, lon_out = grids["lat_out"], grids["lon_out"]
    lon_mesh, lat_mesh = np.meshgrid(lon_out, lat_out)
    targets = np.column_stack([lon_mesh.ravel(), lat_mesh.ravel()])

    pts_lon = src_lon.ravel()
    pts_lat = src_lat.ravel()
    points = np.column_stack([pts_lon, pts_lat])
    make_interp = _interp_factory(method, points)

    out_vars = {}
    for var_name in var_names:
        if var_name not in ds:
            continue
        var = ds[var_name]
        if squeeze_dims:
            for d in ([squeeze_dims] if isinstance(squeeze_dims, str) else squeeze_dims):
                if d in var.dims:
                    var = var.squeeze(d)
        time_dim = next((d for d in var.dims if d not in (lat_dim, lon_dim)), None)

        def _one(values2d):
            interp = make_interp(np.asarray(values2d, dtype=float).ravel())
            return interp(targets).reshape(lat_mesh.shape)

        if time_dim and time_dim in var.dims:
            stack = np.stack([_one(var.isel({time_dim: t}).values)
                              for t in range(var.sizes[time_dim])])
            da = xr.DataArray(stack, dims=(time_dim, "lat", "lon"),
                              coords={time_dim: var[time_dim], "lat": lat_out, "lon": lon_out})
        else:
            da = xr.DataArray(_one(var.values), dims=("lat", "lon"),
                              coords={"lat": lat_out, "lon": lon_out})
        if keep_attrs:
            da.attrs = dict(var.attrs)
        out_vars[var_name] = da

    result = xr.Dataset(out_vars)
    if keep_attrs:
        result.attrs = dict(ds.attrs)
    return result
