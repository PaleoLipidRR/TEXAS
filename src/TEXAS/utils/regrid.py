"""Curvilinear -> regular lat/lon regridding with an xesmf-or-scipy backend.

Uses xesmf (ESMF) when esmpy is importable; otherwise a pure-pip scipy fallback,
so the regrid runs in any environment (including uv, which cannot install esmpy).
"""
from __future__ import annotations

import warnings
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
    if periodic:
        lo, hi = float(np.min(lon_out)), float(np.max(lon_out))
        left = pts_lon <= lo + _SEAM_PAD_DEG
        right = pts_lon >= hi - _SEAM_PAD_DEG
        pts_lon = np.concatenate([pts_lon, pts_lon[left] + (hi - lo), pts_lon[right] - (hi - lo)])
        pts_lat = np.concatenate([pts_lat, pts_lat[left], pts_lat[right]])
        _pad_idx = (np.where(left)[0], np.where(right)[0])
    else:
        _pad_idx = None
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
            flat = np.asarray(values2d, dtype=float).ravel()
            if _pad_idx is not None:
                flat = np.concatenate([flat, flat[_pad_idx[0]], flat[_pad_idx[1]]])
            interp = make_interp(flat)
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


def _esmf_available() -> bool:
    try:
        import esmpy  # noqa: F401
        return True
    except ImportError:
        return False


def _regrid_xesmf(ds, var_names, grids, method, periodic, squeeze_dims, keep_attrs):
    import xesmf as xe
    if isinstance(var_names, str):
        var_names = [var_names]
    lat_dim, lon_dim = grids["lat_dim"], grids["lon_dim"]
    ds_in = xr.Dataset({"lat": ((lat_dim, lon_dim), grids["src_lat"]),
                        "lon": ((lat_dim, lon_dim), grids["src_lon"])})
    ds_out = xr.Dataset({"lat": (["lat"], grids["lat_out"]),
                         "lon": (["lon"], grids["lon_out"])})
    regridder = xe.Regridder(ds_in, ds_out, method, periodic=periodic)
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
        if time_dim and time_dim in var.dims:
            chunks = [regridder(var.isel({time_dim: t})) for t in range(var.sizes[time_dim])]
            da = xr.concat(chunks, dim=time_dim).assign_coords({time_dim: var[time_dim]})
        else:
            da = regridder(var)
        da = da.assign_coords({"lat": ds_out.lat, "lon": ds_out.lon})
        if keep_attrs:
            da.attrs = dict(var.attrs)
        out_vars[var_name] = da
    result = xr.Dataset(out_vars)
    if keep_attrs:
        result.attrs = dict(ds.attrs)
    return result


def regrid_curvilinear_to_latlon(
    ds, var_names, lat_name=None, lon_name=None,
    target_res=0.5, lat_range=(-90, 90), lon_range=(0, 360),
    method="bilinear", periodic=True, squeeze_dims=None, keep_attrs=True,
    backend="auto",
):
    """Regrid a curvilinear (2-D lat/lon) source dataset onto a regular lat/lon grid.

    backend: 'auto' uses xesmf when esmpy is importable, else a pure-pip scipy
    fallback (a close *linear* approximation that differs from xesmf most at the
    periodic seam, near the poles, and near NaN/land boundaries). 'xesmf' forces
    ESMF (raises ImportError without esmpy). 'scipy' forces the fallback.
    """
    grids = _prepare_grids(ds, lat_name, lon_name, target_res, lat_range, lon_range)
    if backend == "auto":
        backend = "xesmf" if _esmf_available() else "scipy"
        if backend == "scipy":
            warnings.warn(
                "esmpy not found — using the scipy pure-pip regridding fallback "
                "(approximate; differs from xesmf at the seam/poles). Pass "
                "backend='xesmf' with esmpy installed for the exact result.",
                UserWarning, stacklevel=2,
            )
    if backend == "xesmf":
        if not _esmf_available():
            raise ImportError(
                "backend='xesmf' requires esmpy, which is not installed. Install it "
                "via conda-forge (`conda install -c conda-forge esmpy`) or use "
                "backend='scipy'."
            )
        return _regrid_xesmf(ds, var_names, grids, method, periodic, squeeze_dims, keep_attrs)
    if backend == "scipy":
        return _regrid_scipy(ds, var_names, grids, method, periodic, squeeze_dims, keep_attrs)
    raise ValueError(f"Unknown backend={backend!r}; expected 'auto', 'xesmf', or 'scipy'.")
