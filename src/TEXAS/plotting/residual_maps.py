# TEXAS/plotting/residual_maps.py
"""
Proxy residual map figure — global Eckert III + Mediterranean + Red Sea zooms.

Layout (nrows × 3):
  col 0 : global Eckert III
  col 1 : Mediterranean (LambertConformal)
  col 2 : Red Sea       (LambertConformal)

Kriging strategy — two-resolution approach
  Layer 1 (zorder=2) : 1°    kriged halo  — spatial context, fast
  Layer 2 (zorder=3) : 0.25° true grid    — exact residuals at data cells
  Layer 3 (zorder=4) : coretop markers

The 0.25° true-data layer is built by vectorised np.add.at  (<0.1 s).
Halo kriging (6 panels) is parallelised via joblib when available.
Set env var KRIGE_N_JOBS to override parallelism (1 = serial).
"""

from __future__ import annotations

import os
from typing import List, Optional, Sequence, Tuple, Union

import numpy as np
from scipy.spatial import cKDTree
try:
    from pykrige.ok import OrdinaryKriging
except ImportError:
    OrdinaryKriging = None
import matplotlib.pyplot as plt
import matplotlib.gridspec as mgridspec
import matplotlib.cm as mplcm
import matplotlib.colors as mcolors
import matplotlib.ticker as mticker
import matplotlib.lines as mlines
from matplotlib.patches import Rectangle

# cartopy is an optional map-plotting dependency — only plot_residual_maps needs
# it. Guarding the import keeps `import TEXAS` working with the core install.
try:
    import cartopy.feature as cfeature
    import cartopy.crs as ccrs
    _CARTOPY_AVAILABLE = True
except ImportError:
    cfeature = None
    ccrs = None
    _CARTOPY_AVAILABLE = False

import xarray as xr

try:
    import regionmask
    _REGIONMASK_AVAILABLE = True
    _OCEAN_BASINS_50 = regionmask.defined_regions.natural_earth_v5_0_0.ocean_basins_50
    _REGION_NAME_TO_NUMBER = dict(zip(_OCEAN_BASINS_50.names, _OCEAN_BASINS_50.numbers))
except ImportError:
    regionmask = None
    _REGIONMASK_AVAILABLE = False
    _OCEAN_BASINS_50 = None
    _REGION_NAME_TO_NUMBER = {}

# ── Gray color constants (approximate proplot gray scale equivalents) ─────────
# proplot gray0=white → gray10=black; values below are hex approximations.
_C_GRAY3 = '#b3b3b3'   # was 'gray3' — light gray (land fill)
_C_GRAY5 = '#808080'   # was 'gray5' — medium gray (borders)
_C_GRAY6 = '#666666'   # was 'gray6' — medium-dark gray (secondary text)
_C_GRAY7 = '#4d4d4d'   # was 'gray7' — dark gray (primary text / spines)

try:
    from joblib import Parallel, delayed
    _HAS_JOBLIB = True
except ImportError:
    _HAS_JOBLIB = False

# ── Grid parameters ──────────────────────────────────────────────────────────
# WOA_OFFSET aligns output grids with WOA23 0.25° cell centres.

WOA_OFFSET = 0.125   # WOA23 cell-centre offset from integer degrees

def make_krige_grid(res: float = 1.0):
    """Return (grid_lon, grid_lat) for a given resolution, WOA23-aligned."""
    lon = np.arange(-180 + WOA_OFFSET, 180,  res)
    lat = np.arange( -90 + WOA_OFFSET,  90,  res)
    return lon, lat

# Default grids (used inside helpers when not overridden)
_GRID_LON_1DEG,    _GRID_LAT_1DEG    = make_krige_grid(1.0)
_GRID_LON_025DEG,  _GRID_LAT_025DEG  = make_krige_grid(0.25)

# ── Natural Earth features — preloaded once (only if cartopy is available) ───
if _CARTOPY_AVAILABLE:
    _LAND = cfeature.NaturalEarthFeature(
        'physical', 'land', '110m', facecolor=_C_GRAY3)
    _COASTLINE = cfeature.NaturalEarthFeature(
        'physical', 'coastline', '110m',
        edgecolor=_C_GRAY7, facecolor='none', linewidth=0.5)
    _BORDERS = cfeature.NaturalEarthFeature(
        'cultural', 'admin_0_boundary_lines_land', '110m',
        edgecolor=_C_GRAY5, facecolor='none', linewidth=0.3, linestyle=':')
else:
    _LAND = _COASTLINE = _BORDERS = None


def _require_cartopy() -> None:
    """Raise a clear error if the optional map-plotting deps are missing."""
    if not _CARTOPY_AVAILABLE:
        raise ImportError(
            "plot_residual_maps requires the optional map-plotting dependencies "
            "(cartopy, regionmask), which are not installed. Install them with:\n"
            "    pip install 'texas-psm[maps]'\n"
            "or, in a conda environment:\n"
            "    conda install -c conda-forge cartopy regionmask"
        )

# ── Default regional extents ─────────────────────────────────────────────────
MED_EXTENT = [-10, 43, 25, 50]   # [lon_min, lon_max, lat_min, lat_max]
RS_EXTENT  = [ 31, 45,  9, 30]

# ============================================================================
# Kriging helpers
# _krige_panel_worker must be module-level so joblib/loky can pickle it.
# ============================================================================

def _krige_panel_worker(
    i: int,
    res_vals: np.ndarray,
    method_label: str,
    lons: np.ndarray,
    lats: np.ndarray,
    grid_lon: np.ndarray,
    grid_lat: np.ndarray,
    n_closest: int,
    max_dist_deg: float,
    grid_res: float,
) -> Tuple[int, np.ma.MaskedArray]:
    """
    Run OrdinaryKriging for one panel and return (index, masked_array).
    All data passed explicitly — no globals captured across process boundaries.
    """
    print(f"  [{i+1}] Kriging halo: {method_label} ...", flush=True)

    if OrdinaryKriging is None:
        raise ImportError("pykrige is required for kriging. Install it: pip install pykrige")

    valid = ~np.isnan(res_vals)
    lons_v, lats_v, vals_v = lons[valid], lats[valid], res_vals[valid]

    ok = OrdinaryKriging(
        lons_v, lats_v, vals_v,
        variogram_model="spherical",
        nlags=20, weight=True,
        verbose=False, enable_plotting=False,
    )
    print(
        f"  [{i+1}] nugget={ok.variogram_model_parameters[0]:.4f}  "
        f"sill={ok.variogram_model_parameters[1]:.4f}  "
        f"range={ok.variogram_model_parameters[2]:.3f}",
        flush=True,
    )

    z_krige, _ = ok.execute(
        "grid", grid_lon, grid_lat,
        backend="loop",
        n_closest_points=n_closest,
    )
    z_data = np.asarray(z_krige).copy()

    # Distance mask — Euclidean in lon/lat degrees
    glon2d, glat2d = np.meshgrid(grid_lon, grid_lat)
    grid_pts = np.column_stack([glon2d.ravel(), glat2d.ravel()])
    data_pts = np.column_stack([lons_v, lats_v])
    dists, _  = cKDTree(data_pts).query(grid_pts, k=1)
    z_mask    = dists.reshape(z_data.shape) > max_dist_deg

    print(f"  [{i+1}] done. unmasked={np.sum(~z_mask)}", flush=True)
    return i, np.ma.array(z_data, mask=z_mask)


def krige_halo_all(
    data: list,
    lons: np.ndarray,
    lats: np.ndarray,
    grid_lon: Optional[np.ndarray] = None,
    grid_lat: Optional[np.ndarray] = None,
    n_closest: int = 5,
    max_dist_deg: float = 10.0,
    grid_res: float = 1.0,
) -> List[np.ma.MaskedArray]:
    """
    Krige the halo for every panel in `data`.

    Uses joblib (loky backend) when available; falls back to serial otherwise.
    Set env var KRIGE_N_JOBS to cap parallelism (1 = force serial).

    Parameters
    ----------
    data : list of (measured, proxy, predicted, residuals, color, label)
    lons, lats : coretop coordinates
    grid_lon, grid_lat : output grid (default: 1° WOA23-aligned)
    """
    if grid_lon is None:
        grid_lon = _GRID_LON_1DEG
    if grid_lat is None:
        grid_lat = _GRID_LAT_1DEG

    tasks = [
        (
            i,
            residuals.values if hasattr(residuals, "values") else np.array(residuals),
            method_label,
        )
        for i, (_, _, _, residuals, _, method_label) in enumerate(data)
    ]

    n_jobs = int(os.environ.get("KRIGE_N_JOBS", min(len(data), os.cpu_count() or 1)))

    common_kw = dict(
        lons=lons, lats=lats,
        grid_lon=grid_lon, grid_lat=grid_lat,
        n_closest=n_closest,
        max_dist_deg=max_dist_deg,
        grid_res=grid_res,
    )

    if _HAS_JOBLIB and n_jobs != 1:
        print(f"Parallel kriging: {len(tasks)} panels on {n_jobs} workers ...")
        results = Parallel(n_jobs=n_jobs, backend="loky")(
            delayed(_krige_panel_worker)(i, res_vals, label, **common_kw)
            for i, res_vals, label in tasks
        )
    else:
        print("Serial kriging ...")
        results = [
            _krige_panel_worker(i, res_vals, label, **common_kw)
            for i, res_vals, label in tasks
        ]

    halo_grids = [None] * len(data)
    for i, z in results:
        halo_grids[i] = z
    return halo_grids


def make_true_grid(
    lons: np.ndarray,
    lats: np.ndarray,
    residuals: np.ndarray,
    grid_lon: Optional[np.ndarray] = None,
    grid_lat: Optional[np.ndarray] = None,
    grid_res: float = 0.25,
) -> np.ma.MaskedArray:
    """
    Place true residuals onto the 0.25° WOA23 grid via vectorised np.add.at.
    Multiple coretops snapping to the same cell are averaged.
    Returns a masked array (unmasked only at data cells).
    """
    if grid_lon is None:
        grid_lon = _GRID_LON_025DEG
    if grid_lat is None:
        grid_lat = _GRID_LAT_025DEG

    valid = ~np.isnan(residuals)
    lons_v, lats_v, vals_v = lons[valid], lats[valid], residuals[valid]

    i_lons = np.clip(
        np.round((lons_v - grid_lon[0]) / grid_res).astype(int),
        0, len(grid_lon) - 1,
    )
    i_lats = np.clip(
        np.round((lats_v - grid_lat[0]) / grid_res).astype(int),
        0, len(grid_lat) - 1,
    )

    z      = np.zeros((len(grid_lat), len(grid_lon)))
    counts = np.zeros((len(grid_lat), len(grid_lon)), dtype=int)
    np.add.at(z,      (i_lats, i_lons), vals_v)
    np.add.at(counts, (i_lats, i_lons), 1)

    has_data = counts > 0
    z[has_data] /= counts[has_data]
    return np.ma.array(z, mask=~has_data)


def load_or_build_halo_cache(
    cache_path: str,
    data: list,
    lons: np.ndarray,
    lats: np.ndarray,
    grid_lon: Optional[np.ndarray] = None,
    grid_lat: Optional[np.ndarray] = None,
    n_closest: int = 5,
    max_dist_deg: float = 10.0,
    grid_res: float = 1.0,
    recompute=False,
) -> List[np.ma.MaskedArray]:
    """
    Load halo grids from ``cache_path`` (.npz), or recompute and save if needed.

    Parameters
    ----------
    recompute : bool or ``'auto'``
        - ``False``  : load from cache; raise ``FileNotFoundError`` if not found.
        - ``True``   : always recompute and overwrite the cache.
        - ``'auto'`` : load from cache if it exists, otherwise compute and save.
    """
    if grid_lon is None:
        grid_lon = _GRID_LON_1DEG
    if grid_lat is None:
        grid_lat = _GRID_LAT_1DEG

    if recompute != True:  # False or 'auto'
        if os.path.exists(cache_path):
            cache = np.load(cache_path)
            # Try new format first (halo_data_), fall back to old format (data_)
            try:
                halo_grids = [
                    np.ma.array(cache[f"halo_data_{i}"], mask=cache[f"halo_mask_{i}"])
                    for i in range(len(data))
                ]
            except KeyError:
                # Fall back to old format
                halo_grids = [
                    np.ma.array(cache[f"data_{i}"], mask=cache[f"mask_{i}"])
                    for i in range(len(data))
                ]
            print(f"Loaded halo cache ← {cache_path}")
            return halo_grids
        if recompute == False:
            raise FileNotFoundError(
                f"Cache not found at:\n  {cache_path}\n"
                "Pass recompute=True to generate it, or recompute='auto' to "
                "compute-and-cache automatically."
            )
        # recompute='auto' and cache missing — fall through to compute

    halo_grids = krige_halo_all(
        data, lons, lats, grid_lon, grid_lat,
        n_closest=n_closest, max_dist_deg=max_dist_deg, grid_res=grid_res,
    )
    np.savez(
        cache_path,
        **{f"data_{i}": halo_grids[i].data for i in range(len(data))},
        **{f"mask_{i}": halo_grids[i].mask for i in range(len(data))},
    )
    print(f"Saved halo cache → {cache_path}")
    return halo_grids


def load_or_build_grids_cache(
    cache_path: str,
    data: list,
    lons: np.ndarray,
    lats: np.ndarray,
    grid_lon_halo: Optional[np.ndarray] = None,
    grid_lat_halo: Optional[np.ndarray] = None,
    grid_lon_true: Optional[np.ndarray] = None,
    grid_lat_true: Optional[np.ndarray] = None,
    n_closest: int = 5,
    max_dist_deg: float = 10.0,
    grid_res: float = 1.0,
    recompute=False,
) -> Tuple[List[np.ma.MaskedArray], List[np.ma.MaskedArray]]:
    """
    Load halo + true grids from cache, or recompute and save if needed.

    Returns (halo_grids, true_grids)
    """
    if grid_lon_halo is None:
        grid_lon_halo = _GRID_LON_1DEG
    if grid_lat_halo is None:
        grid_lat_halo = _GRID_LAT_1DEG
    if grid_lon_true is None:
        grid_lon_true = _GRID_LON_025DEG
    if grid_lat_true is None:
        grid_lat_true = _GRID_LAT_025DEG

    if recompute != True:  # False or 'auto'
        if os.path.exists(cache_path):
            cache = np.load(cache_path)
            halo_grids = [
                np.ma.array(cache[f"halo_data_{i}"], mask=cache[f"halo_mask_{i}"])
                for i in range(len(data))
            ]
            true_grids = [
                np.ma.array(cache[f"true_data_{i}"], mask=cache[f"true_mask_{i}"])
                for i in range(len(data))
            ]
            print(f"Loaded grids cache ← {cache_path}")
            return halo_grids, true_grids
        if recompute == False:
            raise FileNotFoundError(
                f"Cache not found at:\n  {cache_path}\n"
                "Pass recompute=True to generate it, or recompute='auto' to "
                "compute-and-cache automatically."
            )
        # recompute='auto' and cache missing — fall through to compute

    # Compute both halo and true grids
    halo_grids = krige_halo_all(
        data, lons, lats, grid_lon_halo, grid_lat_halo,
        n_closest=n_closest, max_dist_deg=max_dist_deg, grid_res=grid_res,
    )
    
    true_grids = []
    for _, _, _, residuals, _, _ in data:
        res_vals = residuals.values if hasattr(residuals, "values") else np.array(residuals)
        true_grids.append(
            make_true_grid(lons, lats, res_vals, grid_lon_true, grid_lat_true)
        )
    
    # Save both to cache
    np.savez(
        cache_path,
        **{f"halo_data_{i}": halo_grids[i].data for i in range(len(data))},
        **{f"halo_mask_{i}": halo_grids[i].mask for i in range(len(data))},
        **{f"true_data_{i}": true_grids[i].data for i in range(len(data))},
        **{f"true_mask_{i}": true_grids[i].mask for i in range(len(data))},
    )
    print(f"Saved grids cache → {cache_path}")
    return halo_grids, true_grids


# ============================================================================
# Drawing helpers
# ============================================================================

def _extent_mask(lons, lats, extent):
    lon0, lon1, lat0, lat1 = extent
    return (lons >= lon0) & (lons <= lon1) & (lats >= lat0) & (lats <= lat1)


def _regionmask_mask(lons, lats, region_name):
    if not _REGIONMASK_AVAILABLE:
        return None
    if region_name not in _REGION_NAME_TO_NUMBER:
        return None

    lon_xr = xr.DataArray(lons, dims='points')
    lat_xr = xr.DataArray(lats, dims='points')
    region_ids = _OCEAN_BASINS_50.mask(lon_xr, lat_xr).values
    return region_ids == _REGION_NAME_TO_NUMBER[region_name]


def _fill_map(
    ax,
    z_halo: np.ma.MaskedArray,
    z_true: np.ma.MaskedArray,
    lons: np.ndarray,
    lats: np.ndarray,
    norm,
    grid_lon_halo: np.ndarray,
    grid_lat_halo: np.ndarray,
    grid_lon_true: np.ndarray,
    grid_lat_true: np.ndarray,
    extent=None,
    cmap: str = "RdBu_r",
    scatter_s: float = 10,
    scatter_lw: float = 0.4,
):
    """Render halo + true-data layers and coretop markers onto a Cartopy axes."""
    if extent is not None:
        ax.set_extent(extent, crs=ccrs.PlateCarree())
        m = _extent_mask(lons, lats, extent)
        sc_lons, sc_lats = lons[m], lats[m]

        # Subset grid arrays to extent + buffer. Also: do NOT rasterize zoom
        # panels — PDF output drops rasterized bitmaps inside a Cartopy axes
        # that has set_extent (the bitmap loses its clip path and goes white).
        # After subsetting the grid is small enough for vector rendering.
        _buf = 5.0
        lon0, lon1, lat0, lat1 = extent
        _lh = (grid_lon_halo >= lon0 - _buf) & (grid_lon_halo <= lon1 + _buf)
        _rh = (grid_lat_halo >= lat0 - _buf) & (grid_lat_halo <= lat1 + _buf)
        _lt = (grid_lon_true >= lon0 - _buf) & (grid_lon_true <= lon1 + _buf)
        _rt = (grid_lat_true >= lat0 - _buf) & (grid_lat_true <= lat1 + _buf)
        grid_lon_halo = grid_lon_halo[_lh]
        grid_lat_halo = grid_lat_halo[_rh]
        z_halo        = z_halo[np.ix_(_rh, _lh)]
        grid_lon_true = grid_lon_true[_lt]
        grid_lat_true = grid_lat_true[_rt]
        z_true        = z_true[np.ix_(_rt, _lt)]
        _rasterized = False
    else:
        sc_lons, sc_lats = lons, lats
        _rasterized = True

    ax.pcolormesh(
        grid_lon_halo, grid_lat_halo, z_halo,
        cmap=cmap, norm=norm,
        transform=ccrs.PlateCarree(), zorder=2, rasterized=_rasterized,
    )

    ax.pcolormesh(
        grid_lon_true, grid_lat_true, z_true,
        cmap=cmap, norm=norm,
        transform=ccrs.PlateCarree(), zorder=3, rasterized=_rasterized,
    )

    ax.scatter(
        sc_lons, sc_lats,
        c="k", marker="+", s=scatter_s, linewidths=scatter_lw,
        transform=ccrs.PlateCarree(), zorder=6,
    )

    ax.add_feature(_LAND,      zorder=4)
    ax.add_feature(_COASTLINE, zorder=5)
    ax.add_feature(_BORDERS,   zorder=5)


def _circled_number(
    ax, x, y, number,
    fontsize=10, pad=0.3,
    facecolor="white", edgecolor="k",
    linewidth=0.8, zorder=99, transform=None,
    clip_on=False,
):
    """Place a circled number annotation on *ax*."""
    if transform is None:
        transform = ccrs.PlateCarree()
    ax.text(
        x, y, str(number),
        ha="center", va="center",
        fontsize=fontsize, fontweight="bold", color=edgecolor,
        transform=transform, zorder=zorder, clip_on=clip_on,
        bbox=dict(
            boxstyle=f"circle,pad={pad}",
            facecolor=facecolor, edgecolor=edgecolor, linewidth=linewidth,
        ),
    )


def _section_header(
    fig, axs,
    row_left: int, row_right: int,
    y_axfrac: float,
    label: str,
    color=_C_GRAY5, fontsize=13, lw=0.8,
):
    """
    Bold label right-aligned to axs[row_right, -1], with a horizontal rule
    extending to the left edge of axs[row_left, 0].
    Must be called after fig.canvas.draw() so transforms are finalised.
    """
    fig_w, fig_h = fig.get_size_inches() * fig.dpi

    ref_ax = axs[row_right, -1]
    _, y_disp   = ref_ax.transAxes.transform((0, y_axfrac))
    y_frac      = y_disp / fig_h

    x0_disp, _  = axs[row_left,  0].transAxes.transform((0, 0))
    x1_disp, _  = ref_ax.transAxes.transform((1, 0))
    x0_frac     = x0_disp / fig_w
    x1_frac     = x1_disp / fig_w

    txt = fig.text(
        x1_frac, y_frac, f"  {label}",
        ha="right", va="bottom",
        fontsize=fontsize, fontweight="bold", color=color,
        transform=fig.transFigure, zorder=11,
    )

    bbox = txt.get_window_extent(renderer=fig.canvas.get_renderer())
    line = mlines.Line2D(
        [x0_frac, bbox.x0 / fig_w], [y_frac, y_frac],
        transform=fig.transFigure,
        color=color, linewidth=lw, zorder=10, clip_on=False,
    )
    fig.add_artist(line)


# ============================================================================
# Main figure function
# ============================================================================

def plot_residual_maps(
    data: list,
    lons: np.ndarray,
    lats: np.ndarray,
    *,
    # Tags for auto cache naming
    temp_param: Optional[str] = None,   # e.g. "SST", "t_sf2tc_avg"
    y_param: Optional[str] = None,      # e.g. "scaledRI", "scaledRI_cren3"
    residual_tag: str,                  # required — e.g. "proxy_res", "temp_res"
    # Kriging / cache
    cache_path: Optional[str] = None,   # explicit override; auto-generated if None
    recompute=False,                    # False | True | 'auto'
    krige_res: float = 1.0,
    max_dist_deg: float = 10.0,
    n_closest: int = 5,
    # Colour scale
    vlim: float = 0.15,
    vmin: Optional[float] = None,   # explicit lower bound (overrides vlim)
    vmax: Optional[float] = None,   # explicit upper bound (overrides vlim)
    boundary_step: float = 0.025,
    cmap: str = "RdBu_r",
    colorbar_label: str = "Proxy Residuals",
    colorbar_ticks: Optional[Sequence] = None,   # explicit tick values; auto if None
    # Regional extents [lon_min, lon_max, lat_min, lat_max]
    med_extent: Sequence = MED_EXTENT,
    rs_extent: Sequence = RS_EXTENT,
    # Section headers: list of (row_left, row_right, label)
    section_headers: Optional[List[Tuple[int, int, str]]] = None,
    # Annotations on global panel: list of (lon, lat, label_str)
    annotations: Optional[List[Tuple[float, float, str]]] = None,
    # Metrics — precomputed or auto-calculated from data
    metrics=None,
    # Per-row annotation string (replaces R²/RMSE when provided)
    row_annotations: Optional[List[str]] = None,
    # Figure settings
    fig_width: float = 7,
    hspace: Optional[Union[List[float], float]] = 0.04,   # matplotlib hspace (fraction of row height)
    show_grid: bool = True,
    # Zoom panel annotation (RMSE only by default; R² omitted as it is often
    # negative for regional subsets evaluated with a global calibration)
    zoom_show_rmse: bool = True,
    zoom_show_median_sigma: bool = False,
    # Metrics formatting
    rmse_fmt: str = ".3f",           # e.g. ".1f" for temperature residuals
    rmse_unit: str = "",             # e.g. "°C" for temperature residuals
    # Save
    save_dir: Optional[str] = None,
    fname: Optional[str] = None,
    dpi: int = 400,
):
    """
    Draw the proxy residual maps figure.

    Parameters
    ----------
    data : list of 6-tuples
        Each entry: (measured, proxy, predicted, residuals, color, method_label)
        ``residuals`` and other array-likes may be pandas Series or np.ndarray.
    lons, lats : np.ndarray
        Coretop coordinates.
    temp_param : str, optional
        Temperature column name (e.g. ``"SST"``, ``"t_sf2tc_avg"``).
        Used with ``y_param`` to auto-generate the cache filename.
    y_param : str, optional
        Proxy column name (e.g. ``"scaledRI"``, ``"scaledRI_cren3"``).
        Used with ``temp_param`` to auto-generate the cache filename.
    residual_tag : str
        Short identifier for the type of residuals being kriged (e.g.
        ``"proxy_res"``, ``"temp_res"``).  Baked into the auto-generated
        cache filename to prevent collisions between calls with the same
        ``temp_param``/``y_param`` but different residual content.
    cache_path : str, optional
        Explicit path to the .npz grids cache.  When omitted and both
        ``temp_param`` and ``y_param`` are set, auto-generated as
        ``data/cache/kriged_grids_{res}deg_{dist}dmax_woa23_{temp_param}_{y_param}_{residual_tag}.npz``
        inside the project root. Now caches both halo and true grids for faster plotting.
    recompute : bool or ``'auto'``
        - ``False``  : load grids from cache; raise ``FileNotFoundError`` if not found.
        - ``True``   : always re-krige and recompute grids, then overwrite the cache.
        - ``'auto'`` : load from cache if it exists, otherwise compute and save.
    metrics : list of (r2, rmse), optional
        Pre-computed metrics.  If None, auto-calculated via r2_score.
        Ignored when ``row_annotations`` is provided.
    row_annotations : list of str, optional
        One annotation string per row, placed where R²/RMSE would normally
        appear.  When provided, metrics are not computed and positions 1/2
        in each data tuple (measured, predicted) may be None.
    section_headers : list of (row_left, row_right, label), optional
        Section dividers drawn above the specified row range.
    annotations : list of (lon, lat, number_str), optional
        Circled numbers placed on every global panel.
    show_grid : bool, default True
        If False, disables the map gridlines on all panels.
    save_dir, fname : str, optional
        If both are provided, saves .png and .pdf.

    Returns
    -------
    fig, axs
    """
    _require_cartopy()
    from sklearn.metrics import r2_score

    nrows = len(data)

    # ── Grids ──────────────────────────────────────────────────────────────
    grid_lon_halo, grid_lat_halo = make_krige_grid(krige_res)
    grid_lon_true, grid_lat_true = make_krige_grid(0.25)

    # ── Halo + True grids (cached) ──────────────────────────────────────────
    if cache_path is None and temp_param is not None and y_param is not None:
        from TEXAS.utils.paths import CACHE_DIR
        _tag = f"{temp_param}_{y_param}_{residual_tag}"
        cache_path = str(
            CACHE_DIR / f"kriged_grids_{krige_res}deg_{int(max_dist_deg)}dmax_woa23_{_tag}.npz"
        )
        print(f"Auto cache path: {cache_path}")

    if cache_path is not None:
        halo_grids, true_grids = load_or_build_grids_cache(
            cache_path, data, lons, lats,
            grid_lon_halo=grid_lon_halo, grid_lat_halo=grid_lat_halo,
            grid_lon_true=grid_lon_true, grid_lat_true=grid_lat_true,
            n_closest=n_closest, max_dist_deg=max_dist_deg,
            grid_res=krige_res, recompute=recompute,
        )
    else:
        halo_grids = krige_halo_all(
            data, lons, lats,
            grid_lon_halo, grid_lat_halo,
            n_closest=n_closest, max_dist_deg=max_dist_deg,
            grid_res=krige_res,
        )
        true_grids = []
        for _, _, _, residuals, _, _ in data:
            res_vals = residuals.values if hasattr(residuals, "values") else np.array(residuals)
            true_grids.append(
                make_true_grid(lons, lats, res_vals, grid_lon_true, grid_lat_true)
            )
    
    print(f"Grids loaded/built ({len(halo_grids)} halo + {len(true_grids)} true panels)")

    # ── Metrics ────────────────────────────────────────────────────────────
    if row_annotations is not None:
        metrics = [(None, None)] * len(data)   # placeholders; not rendered
    elif metrics is None:
        metrics = []
        for _, measured, predicted, residuals, _, _ in data:
            res_vals  = residuals.values if hasattr(residuals, "values") else np.array(residuals)
            meas_vals = measured.values  if hasattr(measured,  "values") else np.array(measured)
            pred_vals = predicted.values if hasattr(predicted, "values") else np.array(predicted)
            idx  = ~np.isnan(res_vals) & ~np.isnan(meas_vals)
            r2   = r2_score(meas_vals[idx], pred_vals[idx])
            rmse = np.sqrt(np.mean(res_vals[idx] ** 2))
            metrics.append((r2, rmse))

    def _region_metrics(ext, meas_vals, pred_vals, region_name=None):
        mask = None
        if region_name is not None:
            mask = _regionmask_mask(lons, lats, region_name)
        if mask is None:
            mask = (
                (lons >= ext[0]) & (lons <= ext[1]) &
                (lats >= ext[2]) & (lats <= ext[3])
            )
        meas_raw = meas_vals[mask]
        pred_raw = pred_vals[mask]
        valid = ~np.isnan(meas_raw) & ~np.isnan(pred_raw)
        if valid.sum() < 2:
            return None, None
        meas = meas_raw[valid]
        pred = pred_raw[valid]
        return r2_score(meas, pred), np.sqrt(np.mean((meas - pred) ** 2))

    def _region_median(ext, vals, region_name=None):
        mask = None
        if region_name is not None:
            mask = _regionmask_mask(lons, lats, region_name)
        if mask is None:
            mask = (
                (lons >= ext[0]) & (lons <= ext[1]) &
                (lats >= ext[2]) & (lats <= ext[3])
            )
        vals_raw = vals[mask]
        valid = ~np.isnan(vals_raw)
        if valid.sum() < 1:
            return None
        return np.median(vals_raw[valid])

    # ── Colour scale ────────────────────────────────────────────────────────
    if vmin is not None and vmax is not None:
        boundaries = np.arange(vmin, vmax + 1e-9, boundary_step)
    else:
        boundaries = np.arange(-vlim, vlim + 1e-9, boundary_step)
    norm_res   = mcolors.BoundaryNorm(boundaries, ncolors=256)

    # ── Figure layout ──────────────────────────────────────────────────────
    proj_global   = ccrs.EckertIII(central_longitude=-100)
    proj_regional = ccrs.EckertIII(central_longitude=0)

    _CBAR_STRIP_IN = 0.3    # inches reserved at figure bottom for colorbar + label
    _TOP_PAD_IN    = 0.3    # inches at top (for section headers)

    _gap_sum = (
        float(hspace) * (nrows - 1)
        if isinstance(hspace, (int, float))
        else sum(hspace)
    ) if nrows > 1 else 0.0
    
    row_height = ((fig_width * 2 / 4.75) / 1.65) * 0.95   # ← must exist above this block
    fig_height = row_height * (nrows + _gap_sum) + _CBAR_STRIP_IN + _TOP_PAD_IN

    _bot_frac = _CBAR_STRIP_IN / fig_height
    _top_frac = 1.0 - _TOP_PAD_IN / fig_height

    fig = plt.figure(figsize=(fig_width, fig_height))
    fig.subplots_adjust(bottom=_bot_frac, top=_top_frac, left=0.005, right=0.995)

    # ── Normalise hspace → list of (nrows-1) gap sizes ─────────────────────
    # GridSpec only accepts a scalar for hspace, so variable gaps are encoded
    # via interleaved invisible spacer rows in height_ratios instead.
    if nrows > 1:
        if isinstance(hspace, (int, float)):
            _gaps = [float(hspace)] * (nrows - 1)
        else:
            _gaps = list(hspace)
            if len(_gaps) != nrows - 1:
                raise ValueError(
                    f"hspace list length must equal nrows-1={nrows - 1}, "
                    f"got {len(_gaps)}"
                )
    else:
        _gaps = []   # single row — no gaps needed

    # Interleave: [data_row, spacer, data_row, spacer, ..., data_row]
    # Total GridSpec rows = 2*nrows - 1
    _height_ratios: List[float] = []
    for _r in range(nrows):
        _height_ratios.append(1.0)
        if _r < nrows - 1:
            _height_ratios.append(_gaps[_r])

    gs = mgridspec.GridSpec(
        2 * nrows - 1, 3, figure=fig,
        width_ratios=[1.5, 1.3, 0.8],
        height_ratios=_height_ratios,
        wspace=0, hspace=0,   # all spacing encoded in height_ratios
    )

    def _gs_row(r: int) -> int:
        """Map logical data row → GridSpec row index (skipping spacers)."""
        return r * 2

    axs = np.empty((nrows, 3), dtype=object)
    for row in range(nrows):
        axs[row, 0] = fig.add_subplot(gs[_gs_row(row), 0], projection=proj_global)
        axs[row, 1] = fig.add_subplot(gs[_gs_row(row), 1], projection=proj_regional)
        axs[row, 2] = fig.add_subplot(gs[_gs_row(row), 2], projection=proj_regional)

    # ── Per-column gridlines ────────────────────────────────────────────────
    if show_grid:
        for ax in axs[:, 0]:
            gl = ax.gridlines(draw_labels=False, linewidth=0.3, color='0.75', alpha=0.6)
            gl.xlocator = mticker.FixedLocator(range(-180, 181, 30))
            gl.ylocator = mticker.FixedLocator(range(-90, 91, 30))
        for ax in axs[:, 1]:
            gl = ax.gridlines(draw_labels=False, linewidth=0.3, color='0.75', alpha=0.6)
            gl.xlocator = mticker.FixedLocator(range(-180, 181, 10))
            gl.ylocator = mticker.FixedLocator(range(-90, 91, 10))
    # col 2 (Red Sea): no gridlines

    row_labels = list("abcdefghijklmnopqrstuvwxyz")

    # ── Main drawing loop ───────────────────────────────────────────────────
    for i, (
        (_, measured, predicted, residuals, color, method_label),
        (r2, rmse),
        z_halo,
        z_true,
    ) in enumerate(zip(data, metrics, halo_grids, true_grids)):

        ax_global = axs[i, 0]
        ax_med    = axs[i, 1]
        ax_rs     = axs[i, 2]

        fill_kw = dict(
            norm=norm_res,
            grid_lon_halo=grid_lon_halo, grid_lat_halo=grid_lat_halo,
            grid_lon_true=grid_lon_true, grid_lat_true=grid_lat_true,
            cmap=cmap,
        )

        # col 0: global
        _fill_map(ax_global, z_halo, z_true, lons, lats,
                  scatter_s=10, scatter_lw=0.4, **fill_kw)
        for ext in [med_extent, rs_extent]:
            ax_global.add_patch(Rectangle(
                (ext[0], ext[2]), ext[1] - ext[0], ext[3] - ext[2],
                linewidth=1.1, edgecolor="k", facecolor="none",
                transform=ccrs.PlateCarree(), zorder=7,
            ))

        if measured is not None and predicted is not None:
            meas_vals = measured.values  if hasattr(measured,  "values") else np.array(measured)
            pred_vals = predicted.values if hasattr(predicted, "values") else np.array(predicted)
            _, med_rmse = _region_metrics(
                med_extent, meas_vals, pred_vals, region_name="Mediterranean Sea"
            )
            _, rs_rmse  = _region_metrics(
                rs_extent, meas_vals, pred_vals, region_name="Red Sea"
            )
        else:
            med_rmse = rs_rmse = None

        if residuals is not None:
            res_vals = residuals.values if hasattr(residuals, "values") else np.array(residuals)
            med_median_sigma = _region_median(med_extent, res_vals, "Mediterranean Sea")
            rs_median_sigma = _region_median(rs_extent, res_vals, "Red Sea")
        else:
            med_median_sigma = rs_median_sigma = None

        if annotations:
            for lon, lat, num in annotations:
                _circled_number(ax_global, lon, lat, num,
                                fontsize=10, pad=0.1,
                                facecolor="white", edgecolor="k")

        # col 1: Mediterranean — fill map first, then annotate so Cartopy's
        # set_extent() clip-path is established before text artists are added.
        _fill_map(ax_med, z_halo, z_true, lons, lats,
                  extent=list(med_extent), scatter_s=14, scatter_lw=0.5, **fill_kw)
        if zoom_show_rmse and med_rmse is not None:
            ax_med.text(
                0.02, 0.02,
                f"RMSE {med_rmse:{rmse_fmt}}{rmse_unit}",
                transform=ax_med.transAxes, fontsize=10,
                ha="left", va="bottom", zorder=12, clip_on=False,
                color='white'
                # bbox=dict(facecolor="white", alpha=0.85, edgecolor="none"),
            )
        if zoom_show_median_sigma and med_median_sigma is not None:
            ax_med.text(
                0.02, 0.98,
                f"Median σ {med_median_sigma:.1f}{rmse_unit}",
                transform=ax_med.transAxes, fontsize=10,
                ha="left", va="top", zorder=12, clip_on=False,
                color='white'
            )
        if annotations:
            for j, (_, _, num) in enumerate(annotations[:1]):   # ① only
                _circled_number(ax_med, 0.9, 1.0, num,
                                fontsize=12, pad=0.1,
                                transform=ax_med.transAxes,
                                facecolor="white", edgecolor="k")

        # col 2: Red Sea — same: fill first, then annotate.
        _fill_map(ax_rs, z_halo, z_true, lons, lats,
                  extent=list(rs_extent), scatter_s=14, scatter_lw=0.5, **fill_kw)
        if zoom_show_rmse and rs_rmse is not None:
            ax_rs.text(
                0.02, 0.02,
                f"{rs_rmse:{rmse_fmt}}{rmse_unit}",
                transform=ax_rs.transAxes, fontsize=10,
                ha="left", va="bottom", zorder=12, clip_on=False,
                color='white'
                # bbox=dict(facecolor="white", alpha=0.85, edgecolor="none"),
            )
        if zoom_show_median_sigma and rs_median_sigma is not None:
            ax_rs.text(
                0.02, 0.98,
                f"Median σ {rs_median_sigma:.1f}{rmse_unit}",
                transform=ax_rs.transAxes, fontsize=10,
                ha="left", va="top", zorder=12, clip_on=False,
                color='white'
            )
        if annotations and len(annotations) >= 2:
            _circled_number(ax_rs, 0.9, 1.0, annotations[1][2],
                            fontsize=12, pad=0.1,
                            transform=ax_rs.transAxes,
                            facecolor="white", edgecolor="k")

        # Row label + method + metrics
        ax_global.text(
            -0.05, 0.68, f"row {row_labels[i]}",
            transform=ax_global.transAxes,
            fontsize=16, fontweight="bold", ha="right", va="bottom", color=_C_GRAY7,
        )
        ax_global.text(
            -0.05, 0.65, method_label,
            transform=ax_global.transAxes,
            fontsize=9, fontweight="bold", ha="right", va="top", color=_C_GRAY6,
        )
        if row_annotations is not None:
            ann_text = row_annotations[i]
        else:
            ann_text = f"$\\mathbf{{R^2}}$ {r2:.2f}\n$\\mathbf{{RMSE}}$ {rmse:{rmse_fmt}}{rmse_unit}"
        ax_global.text(
            -0.05, 0.3, ann_text,
            transform=ax_global.transAxes,
            fontsize=9, ha="right", va="center", color=_C_GRAY6,
        )

    # ── Global axes formatting ──────────────────────────────────────────────
    for ax in axs.flat:
        ax.tick_params(labelleft=False, left=False, labelcolor=_C_GRAY7,
                       colors=_C_GRAY7)
        for spine in ax.spines.values():
            spine.set_linewidth(1.2)
            spine.set_color(_C_GRAY7)
            spine.set_zorder(10)

    # ── 1. Equalise Red Sea panel height to Mediterranean ───────────────────────
    for i in range(nrows):
        pos_med = axs[i, 1].get_position()
        pos_rs  = axs[i, 2].get_position()
        cy = pos_rs.y0 + pos_rs.height / 2
        axs[i, 2].set_position(
            [pos_rs.x0, cy - pos_med.height / 2, pos_rs.width, pos_med.height]
        )

    # ── 2. Repack rows to remove Cartopy internal whitespace ────────────────────
    # After aspect-ratio enforcement, axs[r,0].get_position().height is the
    # *actual* rendered map height (smaller than the GridSpec cell).
    # We rebuild y-positions from scratch using a controlled gap in inches.

    _ROW_GAP_IN      = 0.1   # tight gap between normal rows (inches)
    _SECTION_GAP_IN  = 0.5   # larger gap at section break (inches)

    # Resolve per-gap inch values from the hspace argument
    if nrows > 1:
        if isinstance(hspace, (int, float)):
            _gap_inches = [_ROW_GAP_IN] * (nrows - 1)
        else:
            # treat any value > 0.01 as a section break, else tight gap
            _gap_inches = [
                _SECTION_GAP_IN if g > 0.01 else _ROW_GAP_IN
                for g in hspace
            ]
    else:
        _gap_inches = []

    _gap_fracs = [g / fig_height for g in _gap_inches]

    # Actual rendered row heights in figure fraction (from col 0 after draw)
    _row_h = [axs[r, 0].get_position().height for r in range(nrows)]

    # Stack rows top-down starting from _top_frac
    y_cursor = _top_frac
    for r in range(nrows):
        h = _row_h[r]
        y0 = y_cursor - h
        for c in range(3):
            pos = axs[r, c].get_position()
            axs[r, c].set_position([pos.x0, y0, pos.width, h])
        y_cursor = y0
        if r < nrows - 1:
            y_cursor -= _gap_fracs[r]
            
    # ── 2b. Repack columns to remove Cartopy horizontal whitespace ──────────
    _COL_GAP_IN = 0.005   # gap between columns in inches
    _LEFT_MARGIN = 0.005
    _RIGHT_MARGIN = 0.005

    # Actual rendered widths per column (from row 0, which is fully drawn)
    _col_w = [axs[0, c].get_position().width for c in range(3)]
    _total_gap_frac = 2 * (_COL_GAP_IN / fig_width)
    _available_frac = 1.0 - _LEFT_MARGIN - _RIGHT_MARGIN - _total_gap_frac

    if sum(_col_w) > 0 and _available_frac > 0:
        _scale = min(1.0, _available_frac / sum(_col_w))
        _col_w = [w * _scale for w in _col_w]

    x_cursor = _LEFT_MARGIN
    for c in range(3):
        w = _col_w[c]
        for r in range(nrows):
            pos = axs[r, c].get_position()
            axs[r, c].set_position([x_cursor, pos.y0, w, pos.height])
        x_cursor += w + _COL_GAP_IN / fig_width   # fig_width in inches → fraction


    # ── 3. Colorbar — anchored dynamically below repacked last row ──────────────
    fig.canvas.draw()
    _cbar_gap_in = 0.1          # gap between last row bottom and colorbar top
    _cbar_h_in   = 0.18          # colorbar bar thickness

    pos_last  = axs[-1, 0].get_position()
    cbar_top  = pos_last.y0 - _cbar_gap_in / fig_height
    cbar_bot  = cbar_top - _cbar_h_in / fig_height

    cbar_ax = fig.add_axes([0.22, cbar_bot, 0.56, _cbar_h_in / fig_height])
    pcm_ref = axs[0, 0].collections[0]
    sm = mplcm.ScalarMappable(cmap=pcm_ref.get_cmap(), norm=norm_res)
    sm.set_array([])
    if colorbar_ticks is not None:
        tick_values = np.asarray(colorbar_ticks)
    else:
        tick_values = np.linspace(boundaries[0], boundaries[-1], min(7, len(boundaries)))
    cb = fig.colorbar(
        sm, cax=cbar_ax, orientation="horizontal",
        label=colorbar_label, extend="both", ticks=tick_values,
    )
    cb.ax.tick_params(labelsize=8, rotation=0)
    cb.minorticks_off()
    
    # ── Trim figure canvas to content after colorbar placement ──────────────────
    fig.canvas.draw()
    _BOTTOM_MARGIN_IN = 0
    cbar_pos = cbar_ax.get_position()
    # y0 of colorbar in figure-inches
    cbar_bottom_in = cbar_pos.y0 * fig_height
    # new figure height = everything above cbar bottom + small margin below it
    new_fig_height = fig_height - cbar_bottom_in + _BOTTOM_MARGIN_IN
    fig.set_size_inches(fig_width, new_fig_height, forward=True)
    fig.canvas.draw()

    # Section headers ──────────────────────────
    if section_headers:
        for row_left, row_right, label in section_headers:
            _section_header(fig, axs, row_left, row_right,
                            y_axfrac=1.15, label=label)

    # ── Save ────────────────────────────────────────────────────────────────
    if save_dir and fname:
        for ext in ("png", "pdf"):
            out = os.path.join(save_dir, f"{fname}.{ext}")
            fig.savefig(out, dpi=dpi, facecolor="white", bbox_inches="tight")
        print(f"Saved → {os.path.join(save_dir, fname)}")

    return fig, axs
