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
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np
from scipy.spatial import cKDTree
from pykrige.ok import OrdinaryKriging
import matplotlib.pyplot as plt
import matplotlib.gridspec as mgridspec
import matplotlib.cm as mplcm
import matplotlib.colors as mcolors
import matplotlib.ticker as mticker
import matplotlib.lines as mlines
from matplotlib.patches import Rectangle
import cartopy.feature as cfeature
import cartopy.crs as ccrs

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

# ── Natural Earth features — preloaded once ──────────────────────────────────
_LAND = cfeature.NaturalEarthFeature(
    'physical', 'land', '110m', facecolor=_C_GRAY3)
_COASTLINE = cfeature.NaturalEarthFeature(
    'physical', 'coastline', '110m',
    edgecolor=_C_GRAY7, facecolor='none', linewidth=0.5)
_BORDERS = cfeature.NaturalEarthFeature(
    'cultural', 'admin_0_boundary_lines_land', '110m',
    edgecolor=_C_GRAY5, facecolor='none', linewidth=0.3, linestyle=':')

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


# ============================================================================
# Drawing helpers
# ============================================================================

def _extent_mask(lons, lats, extent):
    lon0, lon1, lat0, lat1 = extent
    return (lons >= lon0) & (lons <= lon1) & (lats >= lat0) & (lats <= lat1)


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
    else:
        sc_lons, sc_lats = lons, lats

    pcm1 = ax.pcolormesh(
        grid_lon_halo, grid_lat_halo, z_halo,
        cmap=cmap, norm=norm,
        transform=ccrs.PlateCarree(), zorder=2, rasterized=True,
    )
    pcm1.set_rasterized(True)

    pcm2 = ax.pcolormesh(
        grid_lon_true, grid_lat_true, z_true,
        cmap=cmap, norm=norm,
        transform=ccrs.PlateCarree(), zorder=3, rasterized=True,
    )
    pcm2.set_rasterized(True)

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
    color="gray5", fontsize=13, lw=0.8,
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
    # ProPlot figure settings
    fig_width: float = 7,
    hspace: Optional[List] = None,   # default: [1,1,4,1,1] for 6 rows; pass explicitly for other row counts
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
        Explicit path to the .npz halo cache.  When omitted and both
        ``temp_param`` and ``y_param`` are set, auto-generated as
        ``data/cache/kriged_halo_{res}deg_{dist}dmax_woa23_{temp_param}_{y_param}.npz``
        inside the project root.
    recompute : bool or ``'auto'``
        - ``False``  : load from cache; raise ``FileNotFoundError`` if not found.
        - ``True``   : always re-krige and overwrite the cache.
        - ``'auto'`` : load if cache exists, otherwise compute and save.
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
    save_dir, fname : str, optional
        If both are provided, saves .png and .pdf.

    Returns
    -------
    fig, axs
    """
    import proplot as plot
    from sklearn.metrics import r2_score

    nrows = len(data)

    # ── Grids ──────────────────────────────────────────────────────────────
    grid_lon_halo, grid_lat_halo = make_krige_grid(krige_res)
    grid_lon_true, grid_lat_true = make_krige_grid(0.25)

    # ── Halo kriging (cached) ───────────────────────────────────────────────
    if cache_path is None and temp_param is not None and y_param is not None:
        from TEXAS.utils.paths import CACHE_DIR
        _tag = f"{temp_param}_{y_param}_{residual_tag}"
        cache_path = str(
            CACHE_DIR / f"kriged_halo_{krige_res}deg_{int(max_dist_deg)}dmax_woa23_{_tag}.npz"
        )
        print(f"Auto cache path: {cache_path}")

    if cache_path is not None:
        halo_grids = load_or_build_halo_cache(
            cache_path, data, lons, lats,
            grid_lon=grid_lon_halo, grid_lat=grid_lat_halo,
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

    # ── True grids (vectorised, instant) ───────────────────────────────────
    true_grids = []
    for _, _, _, residuals, _, _ in data:
        res_vals = residuals.values if hasattr(residuals, "values") else np.array(residuals)
        true_grids.append(
            make_true_grid(lons, lats, res_vals, grid_lon_true, grid_lat_true)
        )
    print(f"True grids built ({len(true_grids)} panels)")

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

    # ── Colour scale ────────────────────────────────────────────────────────
    if vmin is not None and vmax is not None:
        boundaries = np.arange(vmin, vmax + 1e-9, boundary_step)
    else:
        boundaries = np.arange(-vlim, vlim + 1e-9, boundary_step)
    norm_res   = mcolors.BoundaryNorm(boundaries, ncolors=256)

    # ── ProPlot figure layout ───────────────────────────────────────────────
    proj_global   = plot.Proj('eck3', lon_0=-100)
    proj_regional = plot.Proj('eck3', lon_0=0)

    proj_dict = {}
    for row in range(nrows):
        base = row * 3 + 1
        proj_dict[base]     = proj_global
        proj_dict[base + 1] = proj_regional
        proj_dict[base + 2] = proj_regional

    fig, axs = plot.subplots(
        proj=proj_dict,
        width=fig_width, ncols=3, nrows=nrows, share=0,
        wratios=[2, 2, 0.75],
        wspace=[1, 1],
        hspace=hspace if hspace is not None else [1, 1, 4, 1, 1],
    )

    # ── Per-column gridlines ────────────────────────────────────────────────
    axs[:, 0].format(lonlines=30, latlines=30, fontsize=10)
    axs[:, 1].format(lonlines=10, latlines=10, fontsize=8)
    axs[:, 2].format(fontsize=8)
    for ax in axs[:, 2]:
        for geoaxis in [ax._lonaxis, ax._lataxis]:
            geoaxis.set_major_locator(mticker.NullLocator())
            geoaxis.set_minor_locator(mticker.NullLocator())
        for gl in getattr(ax, "_gridliners", []):
            gl.xlines = False
            gl.ylines = False

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

        if annotations:
            for lon, lat, num in annotations:
                _circled_number(ax_global, lon, lat, num,
                                fontsize=10, pad=0.1,
                                facecolor="white", edgecolor="k")

        # col 1: Mediterranean
        _fill_map(ax_med, z_halo, z_true, lons, lats,
                  extent=list(med_extent), scatter_s=14, scatter_lw=0.5, **fill_kw)
        if annotations:
            for j, (_, _, num) in enumerate(annotations[:1]):   # ① only
                _circled_number(ax_med, 0.9, 1.0, num,
                                fontsize=12, pad=0.1,
                                transform=ax_med.transAxes,
                                facecolor="white", edgecolor="k")

        # col 2: Red Sea
        _fill_map(ax_rs, z_halo, z_true, lons, lats,
                  extent=list(rs_extent), scatter_s=14, scatter_lw=0.5, **fill_kw)
        if annotations and len(annotations) >= 2:
            _circled_number(ax_rs, 0.9, 1.0, annotations[1][2],
                            fontsize=12, pad=0.1,
                            transform=ax_rs.transAxes,
                            facecolor="white", edgecolor="k")

        # Row label + method + metrics
        ax_global.text(
            -0.05, 0.68, f"row {row_labels[i]}",
            transform=ax_global.transAxes,
            fontsize=16, fontweight="bold", ha="right", va="bottom", c="gray7",
        )
        ax_global.text(
            -0.05, 0.65, method_label,
            transform=ax_global.transAxes,
            fontsize=9, fontweight="bold", ha="right", va="top", c="gray6",
        )
        if row_annotations is not None:
            ann_text = row_annotations[i]
        else:
            ann_text = f"$\\mathbf{{R^2}}$ {r2:.2f}\n$\\mathbf{{RMSE}}$ {rmse:{rmse_fmt}}{rmse_unit}"
        ax_global.text(
            -0.05, 0.3, ann_text,
            transform=ax_global.transAxes,
            fontsize=9, ha="right", va="center", c="gray6",
        )

    # ── Shared colorbar ─────────────────────────────────────────────────────────
    # Pull the resolved cmap from the first pcolormesh drawn — guarantees
    # the colorbar matches the maps exactly, no proplot dependency needed.
    pcm_ref = axs[0, 0].collections[0]
    sm = mplcm.ScalarMappable(cmap=pcm_ref.get_cmap(), norm=norm_res)
    sm.set_array([])
    cb = fig.colorbar(
        sm, loc="b", label=colorbar_label,
        extend="both", ticks=boundaries,
        length=0.5, width=0.2,
    )
    cb.minorticks_off()

    # ── Global axes formatting ──────────────────────────────────────────────
    axs.format(
        yticklabels=[], grid=False,
        labelcolor="gray7",
        xtickcolor="gray7",  xticklabelcolor="gray7",
        ytickcolor="gray7",  yticklabelcolor="gray7",
    )
    plot.rc["abc"] = False
    for ax in axs:
        ax.spines[:].set_linewidth(1.2)
        ax.spines[:].set_color("gray7")
        ax.spines[:].set_zorder(10)

    # ── Post-draw layout (must be after fig.canvas.draw()) ─────────────────
    fig.canvas.draw()

    # Equalise Red Sea panel height to Mediterranean
    for i in range(nrows):
        pos_med = axs[i, 1].get_position()
        pos_rs  = axs[i, 2].get_position()
        cy = pos_rs.y0 + pos_rs.height / 2
        axs[i, 2].set_position(
            [pos_rs.x0, cy - pos_med.height / 2, pos_rs.width, pos_med.height]
        )

    # Section headers
    if section_headers:
        for row_left, row_right, label in section_headers:
            _section_header(fig, axs, row_left, row_right,
                            y_axfrac=1.0, label=label)

    # ── Save ────────────────────────────────────────────────────────────────
    if save_dir and fname:
        for ext in ("png", "pdf"):
            out = os.path.join(save_dir, f"{fname}.{ext}")
            fig.savefig(out, dpi=dpi, facecolor="white", bbox_inches="tight")
        print(f"Saved → {os.path.join(save_dir, fname)}")

    return fig, axs
