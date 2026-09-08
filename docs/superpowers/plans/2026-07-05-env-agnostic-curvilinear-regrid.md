# Env-agnostic curvilinear regridding — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give TEXAS a curvilinear→lat/lon regridder that uses `xesmf` when `esmpy` is available and a pure-pip `scipy` fallback when it is not, so SI_code3 runs under any environment (including the uv `.venv`, which cannot install esmpy).

**Architecture:** A new `src/TEXAS/utils/regrid.py` module exposes one public function, `regrid_curvilinear_to_latlon`, that prepares the source/target grids, dispatches to an xesmf or scipy backend, and assembles an `xr.Dataset`. The scipy backend flattens the curvilinear source to points, pads the longitude seam for periodicity, and interpolates with `scipy.interpolate` (triangulation built once, reused across time steps). SI_code3 imports the function instead of defining it inline.

**Tech Stack:** numpy, scipy (`LinearNDInterpolator`/`NearestNDInterpolator`/`Delaunay`), xarray — all existing core deps. `xesmf`/`esmpy` remain optional (`regrid` extra / conda).

## Global Constraints

- No new dependencies. Fallback uses only numpy/scipy/xarray (already core deps).
- Public API signature must match the current notebook function plus a `backend` param, so the notebook call sites are unchanged.
- The xesmf path must stay byte-identical to the current notebook implementation (conda users' published figures unaffected).
- Seam-pad constant: `_SEAM_PAD_DEG = 5.0`.
- Target axes built with `np.arange(range[0], range[1] + target_res/2, target_res)` for both backends.
- Do NOT edit the open notebook file programmatically — provide the one-line swap for the user to paste.
- Every commit stages only the specific files it names (the working tree holds unrelated modified figures/CSVs/notebooks that must not be swept in).

---

### Task 1: Grid preparation helper `_prepare_grids`

**Files:**
- Create: `src/TEXAS/utils/regrid.py`
- Test: `tests/test_regrid.py`

**Interfaces:**
- Produces: `_prepare_grids(ds, lat_name, lon_name, target_res, lat_range, lon_range) -> dict` with keys `lat_name, lon_name, lat_dim, lon_dim, src_lat (2-D ndarray), src_lon (2-D ndarray), lat_out (1-D), lon_out (1-D)`. Longitudes converted to the `lon_range` convention.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_regrid.py
import numpy as np
import pytest
import xarray as xr
from TEXAS.utils.regrid import _prepare_grids


def _curvilinear_ds():
    # 2-D (rectilinear-as-curvilinear) source grid, lon in [0, 360)
    jj, ii = np.meshgrid(np.linspace(-80, 80, 9), np.linspace(0, 350, 12), indexing="ij")
    return xr.Dataset(
        {"TEMP": (("nj", "ni"), jj.copy())},          # field == latitude
        coords={"TLAT": (("nj", "ni"), jj), "TLONG": (("nj", "ni"), ii)},
    )


def test_prepare_grids_autodetects_and_builds_target():
    ds = _curvilinear_ds()
    g = _prepare_grids(ds, None, None, target_res=1.0,
                       lat_range=(-90, 90), lon_range=(0, 360))
    assert g["lat_name"] == "TLAT" and g["lon_name"] == "TLONG"
    assert g["src_lat"].shape == (9, 12) and g["src_lon"].shape == (9, 12)
    # target axes use arange(range0, range1 + res/2, res)
    assert g["lat_out"][0] == -90.0 and g["lat_out"][-1] == 90.0
    assert g["lon_out"][0] == 0.0 and g["lon_out"][-1] == 360.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_regrid.py::test_prepare_grids_autodetects_and_builds_target -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'TEXAS.utils.regrid'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/TEXAS/utils/regrid.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_regrid.py::test_prepare_grids_autodetects_and_builds_target -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/TEXAS/utils/regrid.py tests/test_regrid.py
git commit -m "feat(regrid): grid preparation helper for curvilinear regridding"
```

---

### Task 2: scipy fallback core `_regrid_scipy` (linear, non-periodic)

**Files:**
- Modify: `src/TEXAS/utils/regrid.py`
- Test: `tests/test_regrid.py`

**Interfaces:**
- Consumes: `_prepare_grids` (Task 1).
- Produces: `_regrid_scipy(ds, var_names, grids, method, periodic, squeeze_dims, keep_attrs) -> xr.Dataset` where `grids` is the dict from `_prepare_grids`. Result has dims `(<time?>, lat, lon)` with `lat`/`lon` coords from `grids`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_regrid.py
from TEXAS.utils.regrid import _regrid_scipy, _prepare_grids


def test_regrid_scipy_reproduces_linear_field():
    ds = _curvilinear_ds()  # TEMP == latitude
    grids = _prepare_grids(ds, None, None, 2.0, (-90, 90), (0, 360))
    out = _regrid_scipy(ds, ["TEMP"], grids, method="bilinear",
                        periodic=False, squeeze_dims=None, keep_attrs=True)
    assert set(out["TEMP"].dims) == {"lat", "lon"}
    # interior target point: value must equal its latitude (linear field, linear interp)
    val = out["TEMP"].sel(lat=0.0, lon=180.0).item()
    assert abs(val - 0.0) < 1e-6
    val2 = out["TEMP"].sel(lat=40.0, lon=100.0).item()
    assert abs(val2 - 40.0) < 1e-6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_regrid.py::test_regrid_scipy_reproduces_linear_field -v`
Expected: FAIL — `ImportError: cannot import name '_regrid_scipy'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/TEXAS/utils/regrid.py
import xarray as xr
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
from scipy.spatial import Delaunay


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_regrid.py::test_regrid_scipy_reproduces_linear_field -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/TEXAS/utils/regrid.py tests/test_regrid.py
git commit -m "feat(regrid): scipy curvilinear fallback (linear/nearest, time-aware)"
```

---

### Task 3: periodic seam padding + conservative-method error

**Files:**
- Modify: `src/TEXAS/utils/regrid.py` (`_regrid_scipy`)
- Test: `tests/test_regrid.py`

**Interfaces:**
- Consumes/extends `_regrid_scipy` (Task 2). Same signature.

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/test_regrid.py
def test_periodic_padding_bridges_the_seam():
    # field varying with longitude; a target point near the 0/360 seam
    jj, ii = np.meshgrid(np.linspace(-10, 10, 5), np.linspace(2, 358, 20), indexing="ij")
    ds = xr.Dataset({"TEMP": (("nj", "ni"), np.cos(np.deg2rad(ii)))},
                    coords={"TLAT": (("nj", "ni"), jj), "TLONG": (("nj", "ni"), ii)})
    grids = _prepare_grids(ds, None, None, 1.0, (-10, 10), (0, 360))
    out = _regrid_scipy(ds, ["TEMP"], grids, method="bilinear",
                        periodic=True, squeeze_dims=None, keep_attrs=False)
    # at lon=0 (inside the seam gap of the unpadded source [2,358]) value must be finite
    assert np.isfinite(out["TEMP"].sel(lat=0.0, lon=0.0).item())


def test_conservative_method_raises_in_scipy_backend():
    ds = _curvilinear_ds()
    grids = _prepare_grids(ds, None, None, 2.0, (-90, 90), (0, 360))
    with pytest.raises(ValueError, match="conservative"):
        _regrid_scipy(ds, ["TEMP"], grids, method="conservative",
                      periodic=False, squeeze_dims=None, keep_attrs=False)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_regrid.py -k "seam or conservative" -v`
Expected: `test_periodic_padding_bridges_the_seam` FAILs (NaN at seam); `test_conservative...` FAILs only if the ValueError message lacks "conservative" — it currently says "conservative/patch", so it should already match. Confirm both behaviors after Step 3.

- [ ] **Step 3: Add seam padding to `_regrid_scipy`**

Replace the point-construction block (between `make_interp = ...` setup) — i.e. change:

```python
    pts_lon = src_lon.ravel()
    pts_lat = src_lat.ravel()
    points = np.column_stack([pts_lon, pts_lat])
    make_interp = _interp_factory(method, points)
```

to:

```python
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
```

And update `_one` to append the padded values (so value arrays match the padded point count):

```python
        def _one(values2d):
            flat = np.asarray(values2d, dtype=float).ravel()
            if _pad_idx is not None:
                flat = np.concatenate([flat, flat[_pad_idx[0]], flat[_pad_idx[1]]])
            interp = make_interp(flat)
            return interp(targets).reshape(lat_mesh.shape)
```

Note: `_interp_factory` is called with the padded `points`, so `conservative` still raises before any interpolation — the ValueError message already contains "conservative".

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_regrid.py -k "seam or conservative" -v`
Expected: PASS (both)

- [ ] **Step 5: Commit**

```bash
git add src/TEXAS/utils/regrid.py tests/test_regrid.py
git commit -m "feat(regrid): periodic seam padding; conservative -> ValueError"
```

---

### Task 4: public `regrid_curvilinear_to_latlon` + backend dispatch + xesmf path

**Files:**
- Modify: `src/TEXAS/utils/regrid.py`
- Test: `tests/test_regrid.py`

**Interfaces:**
- Consumes: `_prepare_grids`, `_regrid_scipy`.
- Produces: `_esmf_available() -> bool`; `regrid_curvilinear_to_latlon(ds, var_names, lat_name=None, lon_name=None, target_res=0.5, lat_range=(-90,90), lon_range=(0,360), method='bilinear', periodic=True, squeeze_dims=None, keep_attrs=True, backend='auto') -> xr.Dataset`.

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/test_regrid.py
from TEXAS.utils.regrid import regrid_curvilinear_to_latlon, _esmf_available


def test_backend_scipy_forces_fallback():
    ds = _curvilinear_ds()
    out = regrid_curvilinear_to_latlon(ds, "TEMP", target_res=2.0, backend="scipy")
    assert abs(out["TEMP"].sel(lat=30.0, lon=200.0).item() - 30.0) < 1e-6


def test_backend_auto_uses_scipy_when_esmpy_absent():
    ds = _curvilinear_ds()
    if _esmf_available():
        pytest.skip("esmpy present; auto would use xesmf")
    with pytest.warns(UserWarning, match="fallback"):
        out = regrid_curvilinear_to_latlon(ds, "TEMP", target_res=2.0, backend="auto")
    assert set(out["TEMP"].dims) == {"lat", "lon"}


def test_backend_xesmf_raises_without_esmpy():
    ds = _curvilinear_ds()
    if _esmf_available():
        pytest.skip("esmpy present; xesmf would succeed")
    with pytest.raises(ImportError, match="esmpy"):
        regrid_curvilinear_to_latlon(ds, "TEMP", target_res=2.0, backend="xesmf")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_regrid.py -k backend -v`
Expected: FAIL — `ImportError: cannot import name 'regrid_curvilinear_to_latlon'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to src/TEXAS/utils/regrid.py
import warnings


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_regrid.py -k backend -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/TEXAS/utils/regrid.py tests/test_regrid.py
git commit -m "feat(regrid): public regrid_curvilinear_to_latlon with backend dispatch"
```

---

### Task 5: export from package + run full suite + notebook swap

**Files:**
- Modify: `src/TEXAS/__init__.py`
- Test: `tests/test_regrid.py`

**Interfaces:**
- Consumes: `regrid_curvilinear_to_latlon` (Task 4).
- Produces: top-level `TEXAS.regrid_curvilinear_to_latlon`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_regrid.py
def test_exported_at_top_level():
    import TEXAS
    assert hasattr(TEXAS, "regrid_curvilinear_to_latlon")
    assert "regrid_curvilinear_to_latlon" in TEXAS.__all__
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_regrid.py::test_exported_at_top_level -v`
Expected: FAIL — `AssertionError` (attr missing)

- [ ] **Step 3: Add the export**

In `src/TEXAS/__init__.py`, after the environment-diagnostic import block (the `from .utils.doctor import doctor` lines), add:

```python
# ─── Regridding ──────────────────────────────────────────────────────────
from .utils.regrid import regrid_curvilinear_to_latlon
```

And in the `__all__` list, after `"RECOMMENDED_CMDSTAN_VERSION",`, add:

```python
    # regridding
    "regrid_curvilinear_to_latlon",
```

- [ ] **Step 4: Run the FULL suite to verify nothing regressed**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (all prior tests + the new `tests/test_regrid.py`)

- [ ] **Step 5: Commit**

```bash
git add src/TEXAS/__init__.py tests/test_regrid.py
git commit -m "feat(regrid): export regrid_curvilinear_to_latlon at top level"
```

- [ ] **Step 6: Provide the notebook swap (do NOT edit the .ipynb programmatically)**

Tell the user: in SI_code3 cell 44, delete the inline `def regrid_curvilinear_to_latlon(...):` definition and replace it with:

```python
from TEXAS import regrid_curvilinear_to_latlon
```

Call sites are unchanged. Under the uv `.venv` (no esmpy) it uses the scipy fallback with a one-time warning; under conda (esmpy present) it is byte-identical to before. To force the exact ESMF path where esmpy exists, pass `backend='xesmf'`.

---

## Self-Review

- **Spec coverage:** module + public API (Task 4), backend auto/xesmf/scipy (Task 4), scipy flatten+interp (Task 2), periodic seam pad `_SEAM_PAD_DEG=5.0` (Task 3), method map + conservative ValueError (Tasks 2–3), coord auto-detect/validation/lon conversion (Task 1), triangulation reuse across time (Task 2, `Delaunay` + `LinearNDInterpolator(tri, values)`), tests incl. analytic field / periodic / conservative / backend selection / structure (Tasks 1–5), export (Task 5), notebook swap + fidelity note (Task 5 Step 6 + docstring in Task 4). All spec sections mapped.
- **Placeholder scan:** none — every code step contains full code.
- **Type consistency:** `_prepare_grids` returns the dict consumed unchanged by `_regrid_scipy`/`_regrid_xesmf`; `regrid_curvilinear_to_latlon` signature matches the spec and the notebook; `_esmf_available`/`_regrid_xesmf`/`_regrid_scipy` names consistent across tasks.
- **Fidelity note updated:** the docstring (Task 4) additionally names NaN/land boundaries as a fallback-difference source, consistent with the scipy triangulation approach (Task 2 builds the triangulation from all source points; NaN data values propagate to adjacent triangles).
