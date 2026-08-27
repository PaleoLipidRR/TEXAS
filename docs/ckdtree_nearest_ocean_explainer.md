# Finding the Nearest Ocean Pixel: How `cKDTree` Works

> **Context**: Used in `SI_code00_PreProcessing.ipynb` — the `get_nearest_valid_value()` function snaps each sediment core site to the nearest valid (non-land) pixel in a gridded dataset.

---

## The Problem

Gridded datasets (e.g., World Ocean Atlas temperature, WOA nitrate) store data on a regular lat/lon grid. Pixels over land are `NaN`. A sediment core site near a coastline may fall exactly on a land pixel — so we can't just do a direct lookup. We need to find the nearest *ocean* pixel instead.

```
  Grid (each cell = 1° × 1°):

  ~~~  ~~~  ~~~  ~~~  ~~~  ~~~
  ~~~  ~~~  ~~~  ~~~  ~~~  ~~~
  ~~~  ~~~  NaN  NaN  NaN  ~~~     NaN = land
  ~~~  ~~~  NaN  NaN  NaN  ~~~
  ~~~  ~~~  ~~~  ~~~  ~~~  ~~~

  Core site ✦ falls here:
                 ↓
  ~~~  ~~~  ~~~  NaN  NaN  ~~~
                  ✦ ← oops, this is land!
```

We want to automatically jump to the nearest `~~~` (ocean) cell.

---

## Step 1 — Flatten and Drop Land

The 2D grid is **stacked** into a 1D list of points, then all `NaN` (land) entries are dropped.

```
Before stacking (2D grid):

  col→   0     1     2     3     4
row 0: [~~~] [~~~] [~~~] [~~~] [~~~]
row 1: [~~~] [~~~] [NaN] [NaN] [NaN]
row 2: [~~~] [~~~] [NaN] [NaN] [NaN]

After .stack():
  [(0,0,~~~), (0,1,~~~), (0,2,~~~), (0,3,~~~), (0,4,~~~),
   (1,0,~~~), (1,1,~~~), (1,2,NaN), (1,3,NaN), (1,4,NaN),
   (2,0,~~~), (2,1,~~~), (2,2,NaN), (2,3,NaN), (2,4,NaN)]

After .dropna():
  [(0,0,~~~), (0,1,~~~), (0,2,~~~), (0,3,~~~), (0,4,~~~),
   (1,0,~~~), (1,1,~~~),
   (2,0,~~~), (2,1,~~~)]
                ↑
         land pixels gone — only ocean remains
```

We now have a 1D array of `(lat, lon, value)` for ocean points only.

---

## Step 2 — Build the cKDTree

### Why not just check every point?

With a global 1° grid, there are ~180 × 360 = **64,800 grid cells**, most of them ocean. If you have 500 core sites and check each against every ocean point:

```
500 sites × ~40,000 ocean points = 20,000,000 comparisons  😬
```

A **KD-Tree** organizes points spatially so you only check a tiny fraction.

---

### What the tree looks like

A KD-Tree recursively splits points along alternating axes (latitude, then longitude, then latitude, ...). Each split divides the remaining points roughly in half.

```
                    ┌─────────────────────────────┐
                    │       ALL OCEAN POINTS       │
                    │  (lat/lon pairs, no NaNs)    │
                    └──────────────┬──────────────┘
                                   │
                          Split on LATITUDE
                          ─────────────────
                    ┌──────────────┴──────────────┐
                    │                             │
              lat < 20°N                     lat ≥ 20°N
           (tropical ocean)              (mid/high latitude)
                    │                             │
           Split on LONGITUDE             Split on LONGITUDE
           ──────────────────             ──────────────────
          ┌──────┴──────┐               ┌──────┴──────┐
        lon<0°        lon≥0°          lon<0°        lon≥0°
       (Atlantic)   (Indo-Pac)      (N. Atl.)    (N. Pac.)
          │             │               │             │
         ...           ...             ...           ...
          │
    [small bucket
     of ~10-20 pts]  ← only these get compared at query time
```

Each level halves the search space. With 40,000 ocean points, it takes only ~log₂(40,000) ≈ **15 comparisons** to reach the right bucket.

---

### Speed comparison

| Method | Comparisons (500 sites, 40k ocean pts) |
|---|---|
| Brute force | 20,000,000 |
| cKDTree | ~500 × 15 = **7,500** |

The tree is built once and then queried 500 times cheaply.

> The `c` in `cKDTree` means it is compiled in **C** via SciPy — much faster than a pure-Python implementation.

---

## Step 3 — Query: Snap Each Core Site to Nearest Ocean Pixel

For each core site, the tree navigates to the right branch and finds the closest ocean point.

```
Map view — finding nearest ocean for site ✦:

  🌊  🌊  🌊  🌊  🌊  🌊
  🌊  🌊  🌊  🌊  🌊  🌊
  🌊  🌊  🏔️  🏔️  🏔️  🌊
  🌊  🌊  🏔️  🏔️  🏔️  🌊
  🌊  🌊  🌊  🌊  🌊  🌊

             ✦  ← core site (on land pixel 🏔️)

  cKDTree search:
    Navigate tree → reach bucket containing nearby points
    Measure distance to each point in bucket:

        🌊 ←── 2.1°    🌊 ←── 2.8°
        🌊 ←── 1.4° ✓  🏔️  (NaN, already removed)
        🌊 ←── 1.9°    🏔️  (NaN, already removed)
                 ✦

  Winner: 🌊 at distance 1.4° → return its value
```

The `distances` array returned by `.query()` can optionally be used to flag sites that are suspiciously far from any ocean (e.g., > 5°), which might indicate a data entry error in the core coordinates.

---

## Putting It All Together

```
get_nearest_valid_value(ds, target_lats, target_lons)
         │
         ▼
  1. Stack 2D grid → 1D list
  2. Drop NaN (land) → ocean-only points
  3. Extract (lat, lon) coordinates of ocean points
         │
         ▼
  4. cKDTree(ocean_coords)
     ┌─────────────────────┐
     │  Build spatial index │  ← one-time cost
     └─────────────────────┘
         │
         ▼
  5. tree.query(target_coords)
     ┌────────────────────────────────┐
     │ For each core site:            │
     │   Navigate tree → find nearest │  ← fast, repeated
     │   Return index + distance      │
     └────────────────────────────────┘
         │
         ▼
  6. ocean_points.isel(grid_point=indices)
     → return the actual data values
       (temperature, NO₃, etc.)
         │
         ▼
     numpy array, shape (N_sites,)
```

---

## Code Reference

```python
from scipy.spatial import cKDTree
import numpy as np

def get_nearest_valid_value(ds, target_lats, target_lons,
                            lat_dim='lat', lon_dim='lon'):

    # Steps 1–2: flatten the 2D grid into a 1D list and drop land (NaN) pixels.
    # .stack() converts the (lat, lon) grid into a single "grid_point" dimension.
    # .dropna() removes every point where the value is NaN (i.e., land),
    # leaving only valid ocean pixels.
    ocean_points = ds.stack(grid_point=(lat_dim, lon_dim)).dropna('grid_point')

    # Step 3: extract the (lat, lon) coordinates of the surviving ocean pixels.
    # ocean_coords is a 2-column array — one row per ocean pixel:
    #   [[lat_0, lon_0],
    #    [lat_1, lon_1],
    #    ...]
    ocean_coords = np.column_stack((ocean_points[lat_dim].values,
                                    ocean_points[lon_dim].values))

    # Step 4: build the KD-Tree from the ocean coordinates.
    #
    # A KD-Tree ("K-Dimensional Tree") is a spatial index that organises
    # points by recursively splitting them along alternating axes:
    #
    #   Level 0 — split on LATITUDE  (north vs south)
    #   Level 1 — split on LONGITUDE (east vs west)
    #   Level 2 — split on LATITUDE  again …
    #   …until each leaf holds only a handful of points.
    #
    # Diagram (schematic — not to scale):
    #
    #              ALL ~40 000 OCEAN POINTS
    #                        │
    #              ┌─── lat < 0°? ───┐
    #           S. Hem.           N. Hem.
    #              │                 │
    #       ┌─lon < 0°─┐      ┌─lon < 0°─┐
    #      SW          SE    NW          NE
    #       │           │     │           │
    #      ...         ...   ...    [~600 pts]
    #                               │
    #                        ┌─ lat < 45°? ─┐
    #                     [~300]          [~300]
    #                        │
    #                      … keep splitting …
    #                        │
    #                   [leaf: ~15 pts]   ← only these are compared
    #
    # Building the tree is a one-time O(N log N) cost.
    # Each subsequent query is only O(log N) — ~15 comparisons instead of 40 000.
    #
    # The 'c' prefix means this is SciPy's C-compiled implementation,
    # far faster than a pure-Python KD-Tree.
    tree = cKDTree(ocean_coords)

    # Step 5: query — for every core site, find the index of the nearest ocean pixel.
    # target_coords has the same 2-column format as ocean_coords:
    #   [[site_lat_0, site_lon_0],
    #    [site_lat_1, site_lon_1], ...]
    # .query() traverses the tree for each row and returns:
    #   distances — great-circle-ish distance to the nearest ocean pixel
    #               (useful for flagging sites unreasonably far from ocean, e.g. > 5°)
    #   indices   — position in ocean_points of the nearest pixel
    target_coords = np.column_stack((target_lats, target_lons))
    distances, indices = tree.query(target_coords)

    # Step 6: use the indices to pull the actual data values
    # (temperature, NO₃, etc.) from ocean_points and return as a plain numpy array.
    return ocean_points.isel(grid_point=indices).values
```

---

## Longitude Convention Sensitivity

> **TL;DR** — the tree uses plain Euclidean distance, so both the dataset and your target coordinates **must use the same longitude convention**, and neither should straddle the ±180°/0°–360° boundary.

### Two failure modes

**1. Convention mismatch** — dataset on 0–360, core sites on -180–180 (or vice versa):

```
Dataset lon  = 350°   (eastern Atlantic, 0–360 convention)
Core site lon = -10°  (same location,   -180–180 convention)

Tree sees: |350 − (−10)| = 360°  ← thinks they're on opposite sides of Earth
Truth:                        0°
```

**2. Antimeridian wraparound** — points near ±180° are far apart in Euclidean space even when geographically adjacent:

```
  -180/180 convention:
    Point A: lon =  179°  ]
    Point B: lon = -179°  ]  2° apart in reality

    Tree distance: |179 − (−179)| = 358°  ← treated as near-antipodal
```
This is a real issue for Pacific sediment cores near the date line.

### Diagnosis

Check before calling the function:

```python
print(ds[lon_dim].values.min(), ds[lon_dim].values.max())
# 0–360 dataset:   0.5 ... 359.5
# -180/180 dataset: -179.5 ... 179.5

print(target_lons.min(), target_lons.max())
# must match the dataset convention
```

### Fix: normalise to the same convention

Pick one convention and convert both sides before building the tree.

```python
# Helper: force any longitude array into -180 to +180
def to_180(lon):
    return ((np.asarray(lon) + 180) % 360) - 180

# Use on the dataset coordinate
ds[lon_dim] = to_180(ds[lon_dim].values)

# Use on target coordinates
target_lons_fixed = to_180(target_lons)

result = get_nearest_valid_value(ds, target_lats, target_lons_fixed)
```

Or convert to 0–360 instead — either is fine, just be consistent.

### Robust alternative: 3-D Cartesian tree

Converting lat/lon to 3-D (x, y, z) on the unit sphere eliminates both problems — Euclidean distance in 3-D space is a monotone function of great-circle distance and has no seam:

```python
def latlon_to_xyz(lat, lon):
    lat_r = np.radians(lat)
    lon_r = np.radians(lon)
    x = np.cos(lat_r) * np.cos(lon_r)
    y = np.cos(lat_r) * np.sin(lon_r)
    z = np.sin(lat_r)
    return np.column_stack((x, y, z))

# Build tree in 3-D
ocean_xyz   = latlon_to_xyz(ocean_points[lat_dim].values,
                             ocean_points[lon_dim].values)
target_xyz  = latlon_to_xyz(target_lats, target_lons)

tree = cKDTree(ocean_xyz)
distances, indices = tree.query(target_xyz)
# distances are now chord lengths (0–2), not degrees
```

This version is insensitive to longitude convention and works correctly across the date line and poles.

---

## See Also

- [`scipy.spatial.cKDTree` documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.cKDTree.html)
- [`xarray.DataArray.stack`](https://docs.xarray.dev/en/stable/generated/xarray.DataArray.stack.html)
- Notebook: `notebooks/manuscripts/SI_code00_PreProcessing.ipynb`
