# Env-agnostic curvilinear regridding

**Date:** 2026-07-05
**Status:** approved (design)
**Goal:** Let every manuscript notebook run under any environment — including the
pure-pip/uv `.venv` that cannot install `esmpy` — by giving TEXAS a curvilinear→lat/lon
regridder that uses `xesmf` where available and a pure-pip fallback where it is not.

## Problem

`notebooks/manuscripts/SI_code3_paleo_showcases.ipynb` (cell 44) defines
`regrid_curvilinear_to_latlon`, which regrids a **curvilinear** source grid (2-D
`TLAT`/`TLONG` coordinates from CESM/POP ocean output) onto a regular lat/lon grid via
`xesmf` (bilinear, periodic). `xesmf` needs `esmpy`, which is **not on PyPI** (it wraps a
compiled ESMF C library), so it is installable only via conda-forge. The uv `.venv`
therefore cannot run this cell, so SI_code3 is not env-agnostic.

The user requires the regrid to **recompute in any environment** (not a shipped cached
product), accepting that a pure-pip fallback will differ slightly from `xesmf`.

`xarray.interp` is not an option: it handles only rectilinear source grids, not the 2-D
curvilinear source here.

## Approach (chosen: A)

Move the function into the package as `TEXAS.utils.regrid`, with backend auto-detection:
`xesmf` when `esmpy` imports, else `scipy.interpolate.LinearNDInterpolator`. No new
dependencies (scipy is already core). Rejected alternatives: `pyresample` fallback (more
geospatially faithful but adds `pyresample`/`pykdtree`); inline-in-notebook (untested,
non-reusable).

## Module & public API — `src/TEXAS/utils/regrid.py`

```python
regrid_curvilinear_to_latlon(
    ds, var_names, lat_name=None, lon_name=None,
    target_res=0.5, lat_range=(-90, 90), lon_range=(0, 360),
    method='bilinear', periodic=True, squeeze_dims=None, keep_attrs=True,
    backend='auto',
) -> xr.Dataset
```

Same signature as the current notebook function plus `backend`. Exported at top level:
`from TEXAS import regrid_curvilinear_to_latlon` (and in `__all__`).

Internal helpers: `_esmf_available() -> bool`, `_regrid_xesmf(...)`, `_regrid_scipy(...)`.

## Backend selection

- `backend='auto'` (default): if `_esmf_available()` → `_regrid_xesmf` (unchanged from the
  current notebook implementation, byte-identical results); else → `_regrid_scipy`, emitting
  a one-time `UserWarning` that the approximate pip-only fallback is active.
- `backend='xesmf'`: force xesmf; raise `ImportError` with an install hint if esmpy missing.
- `backend='scipy'`: force the pip-only path (used by tests, and by users who want
  determinism across machines regardless of esmpy).

## scipy fallback — `_regrid_scipy`

1. Reuse the existing coordinate auto-detection (`TLAT/TLONG/lat/lon/...`), the 2-D-coord
   validation, and the 0–360 ↔ −180–180 longitude conversion.
2. Flatten the curvilinear source to 1-D `(lat, lon, value)` point arrays; drop NaN (land)
   source points before triangulating.
3. **Periodic seam:** when `periodic`, duplicate source points within a fixed pad band of
   each longitude edge (`seam_pad_deg = 5.0°`, a module constant), shifted ±360°, so linear
   interpolation spans the 0/360 seam instead of leaving a NaN gash. Target points remain
   within `lon_range`. (5° comfortably exceeds typical ocean-model cell widths, so the seam
   is always bridged; over-padding only adds a few duplicate points and is harmless.)
4. Build the target mesh with the same `np.arange(lat_range[0], lat_range[1]+target_res/2,
   target_res)` (and lon) as the xesmf path, so both backends produce identical target axes.
5. Method map: `'bilinear' → LinearNDInterpolator`; `'nearest'`/`'nearest_s2d'` →
   `NearestNDInterpolator`; `'conservative'`/`'patch'` → `ValueError` (needs xesmf).
6. Build the triangulation **once** and reuse across all time steps (the Delaunay build is
   the expensive part); loop time steps applying the interpolator. Target points outside the
   source convex hull → `NaN` (matches how ocean fields have undefined regions).
7. Assemble the `xr.DataArray`/`Dataset` exactly like the xesmf branch: same dims
   (`[time?, lat, lon]`), coords assigned from the target grid, attrs preserved when
   `keep_attrs`.

## Data flow

`ds` (curvilinear, 2-D lat/lon + data vars) → validate/auto-detect coords → build target
grid → select backend → per var: loop time steps → interpolate → concat over time → assign
coords → `xr.Dataset`. Output shape is identical across backends.

## Error handling

- `conservative`/`patch` under the scipy backend → `ValueError`: "conservative regridding
  requires xesmf/esmpy (conda-forge); use method='bilinear' or install esmpy."
- Coordinate auto-detect failure / non-2-D coords → existing `ValueError`s (carried over).
- `backend='xesmf'` with esmpy absent → `ImportError` with the conda-forge install hint.

## Testing (TDD) — `tests/test_regrid.py`

Real behavior, no esmpy required (exercises the fallback so it runs in CI):

- **Analytic-field accuracy:** synthetic warped curvilinear source grid carrying an
  analytic field linear in latitude (`T = a*lat + b`). Because scipy `linear` reproduces a
  linear field exactly, assert regridded ≈ analytic at interior target points to tight
  tolerance.
- **Method mapping:** `method='bilinear'` and `'nearest'` succeed; `'conservative'` raises
  `ValueError`.
- **Periodic seam:** a field defined across the 0/360 boundary regrids with no NaN band at
  the seam when `periodic=True` (and, as a contrast, a seam gap is allowed when
  `periodic=False`).
- **Output structure:** result has `(lat, lon)` dims, target coords set, source attrs
  preserved when `keep_attrs=True`.
- **Backend selection:** `backend='scipy'` forces the fallback; `backend='auto'` selects
  scipy when esmpy is absent. The xesmf branch is `pytest.mark.skipif`-guarded on
  `_esmf_available()`.

## Notebook change

SI_code3 cell 44: delete the inline `def regrid_curvilinear_to_latlon(...)` and replace with
`from TEXAS import regrid_curvilinear_to_latlon`. All call sites are unchanged (identical
signature). The open notebook is edited by the user, not by the agent — provide the exact
one-line swap.

## Fidelity note (docstring + notebook markdown)

The conda/esmpy path is unchanged and byte-identical to the current published figures. The
pip-only path is a close **linear** approximation that differs most at the periodic seam and
near the poles (planar Delaunay on lon/lat vs. xesmf's spherical grid-cell bilinear
weights). `backend='xesmf'` forces the exact path when reproducibility is critical.

## Out of scope

- Conservative/patch regridding without esmpy (explicitly unsupported → `ValueError`).
- Rectilinear-source regridding (use `xarray.interp`).
- Shipping precomputed regridded products (user chose recompute-anywhere).
- Adding `pyresample` or any new dependency.
