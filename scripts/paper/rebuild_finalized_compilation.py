#!/usr/bin/env python3
"""Rebuild the finalized gridded calibration set from the raw compilation.

    python scripts/paper/rebuild_finalized_compilation.py --check    # old screen reproduces the file
    python scripts/paper/rebuild_finalized_compilation.py            # dry run: what the fix changes
    python scripts/paper/rebuild_finalized_compilation.py --apply    # rewrite the finalized CSV

Reproduces SI_code00_PreProcessing sections 3.3.3 and 3.3 (cells 90, 97, 99) without
running the notebook: the 90% chi-square Mahalanobis ellipse is fitted to the core-tops with
no low-abundance GDGT and GDGT-2/3 <= 5, applied to every sample with the manual warm-end
exception; the kept core-tops are reduced to one median per 0.4-degree cell, and the kept
culture and mesocosm samples are appended ungridded.

Why: the finalized file was screened with the ``TEXRI`` feature set, TEX86 and ``scaledRI``
(RI with crenarchaeol counted as 4 rings, / 4), while the manuscript, the calibration fits and
``MahalanobisOutlierDetector.from_calibration()`` all use Scaled RI, ``scaledRI_cren3``
(crenarchaeol counted as 3 rings, / 3). ``--check`` rebuilds with the old features and fails
unless it matches the committed file, so the rebuild is known to be faithful before the
features change.

After ``--apply``, rerun ``scripts/paper/add_retained_flag.py --apply`` (it stamps the
screening flags this script does not write).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
SPREADSHEETS = REPO / "data" / "spreadsheets"
RAW_CSV = SPREADSHEETS / "combined_coretop_culture_mesocosm_rev20260210.csv"
OUT_CSV = SPREADSHEETS / "ds_gridded_screened_global_compilation_finalized.csv"
FLAG_COLS = ["mahalDist_TEXRI_cren3", "mahal_outlier_090", "warm_end_retained"]   # add_retained_flag.py

OLD_FEATURES = ["TEX86", "scaledRI"]          # the notebook's "TEXRI" set, which built the file
NEW_FEATURES = ["TEX86", "scaledRI_cren3"]    # "TEXRI_cren3": what the manuscript describes

# SI_code00 cell 99, verbatim
NONNUMERIC = ['regionName', 'reference_name', 'datatype', 'Strains',
              'organism_commonName', 'organism_broadClass', 'organism_broadClass2',
              'organism_broadClass3', 'organism_broadClass4', 'publicationYear']
NUMERIC = ['Latitude', 'Longitude', 'modernWaterDepth',
           'TEX86', 'BIT', 'methaneIndex',
           'weighted_tex', 'weighted_tex_cren2', 'weighted_tex_cren3', 'weighted_tex_cren5',
           'ringIndex', 'ringIndex_cren2', 'ringIndex_cren3',
           'ringIndex_cren5', 'ringIndex_noCrens', 'ringIndex_noCren',
           'scaledRI', 'scaledRI_cren2', 'scaledRI_cren3', 'scaledRI_cren5',
           'scaledRI_noCren', 'scaledRI_noCren_cren2', 'scaledRI_noCren_cren3', 'scaledRI_noCren_cren5',
           'scaledRI_noCrens',
           'gdgt23ratio', 'gdgt23ratio_se', 'ZeroOverZeroCren',
           'SST', 't_sf2tc_avg',
           'no3_sf2tc_avg', 'no3_sf2tc_woa23', 'thermoNO3_se',
           'OPTiMAL_Dnearest', 'OPTiMAL_SST']
CELL = ['match_lat_04deg', 'match_lon_04deg']


def build(features: list[str]) -> tuple[pd.DataFrame, dict]:
    from TEXAS.data import MahalanobisOutlierDetector

    raw = pd.read_csv(RAW_CSV, low_memory=False)
    low = raw["lowAbundanceFlag"].astype(bool)
    # cell 90: fit on the low-G2/3, low-abundance-free core-tops, apply to everything
    det = MahalanobisOutlierDetector(features, confidence=0.9)
    det.fit(raw[~low & (raw["datatype"] == "coretop") & (raw["gdgt23ratio"] <= 5)])
    out = det.detect_outliers_manual(raw)
    # cell 97 (the comparison with False drops NaN distances, as in the notebook)
    keep = (out == False) & ~low  # noqa: E712
    crtp = raw[(raw["datatype"] == "coretop") & keep]
    culmeso = raw[(raw["datatype"] != "coretop") & keep]
    # cell 99
    first = pd.pivot_table(crtp, index=CELL, values=NONNUMERIC, aggfunc='first', sort=False).reset_index()
    med = pd.pivot_table(crtp, values=NUMERIC, index=CELL, aggfunc='median').reset_index()
    grid = pd.merge(first, med, how='right')
    df = pd.concat([grid, culmeso[grid.columns]], axis=0)
    # cell 110: the ocean basin of each core-top cell
    import regionmask
    import xarray as xr
    basins = regionmask.defined_regions.natural_earth_v5_0_0.ocean_basins_50
    is_ct = df['datatype'] == 'coretop'
    lon = df.loc[is_ct, 'Longitude'].values
    lon = np.where(lon > 180, lon - 360, lon)
    ids = basins.mask(xr.DataArray(lon, dims='points'),
                      xr.DataArray(df.loc[is_ct, 'Latitude'].values, dims='points')).values
    ids = pd.Series(ids.astype(int), index=df.loc[is_ct].index)
    df.loc[is_ct, 'ocean_region_id'] = ids.values
    df.loc[is_ct, 'ocean_region'] = ids.map(dict(zip(basins.numbers, basins.names)))
    df.loc[is_ct, 'ocean_region_abbrev'] = ids.map(dict(zip(basins.numbers, basins.abbrevs)))
    # a later plotting cell sets NO3 = 10 (above the 1 umol/L cutoff: term off) on culture and
    # mesocosm rows without NO3, through a plot_data that is the same object as this frame, so the
    # saved file carries it
    df['no3_sf2tc_avg'] = [10 if n != 'coretop' and np.isnan(x) else x
                           for n, x in zip(df['datatype'], df['no3_sf2tc_avg'])]
    info = dict(features=features, threshold=float(det.threshold), n_fit=int(det.n_reference)
                if getattr(det, "n_reference", None) else None,
                counts=df["datatype"].value_counts().to_dict())
    return df, info


def key(df: pd.DataFrame) -> pd.Series:
    """Identity of a row: its cell for core-tops, its values for culture and mesocosm."""
    # formatted by hand: under pandas' string dtype, astype(str) keeps NaN as NaN
    return pd.Series([f"{d}|{la:.4f}|{lo:.4f}|{t:.3f}|{x:.5f}" for d, la, lo, t, x in zip(
        df["datatype"], df["match_lat_04deg"], df["match_lon_04deg"], df["SST"], df["TEX86"])])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="rebuild with the old features; fail unless "
                    "it reproduces the committed file")
    ap.add_argument("--apply", action="store_true", help="write the rebuilt file (Scaled RI screen)")
    args = ap.parse_args(argv)

    committed = pd.read_csv(OUT_CSV, low_memory=False)
    base = committed.drop(columns=[c for c in FLAG_COLS if c in committed.columns])

    if args.check:
        df, info = build(OLD_FEATURES)
        same_cols = list(df.columns) == list(base.columns)
        a = df.reset_index(drop=True)
        b = base.reset_index(drop=True)
        same_shape = a.shape == b.shape
        num = [c for c in a.columns if pd.api.types.is_numeric_dtype(a[c])]
        same_vals = same_shape and np.allclose(a[num].to_numpy(float), b[num].to_numpy(float),
                                               equal_nan=True, rtol=0, atol=1e-9)
        oth = [c for c in a.columns if c not in num]
        same_text = same_shape and a[oth].astype(str).equals(b[oth].astype(str))
        print(f"old features {OLD_FEATURES}: {info['counts']}")
        print(f"  columns {same_cols}, shape {same_shape}, numbers {same_vals}, text {same_text}")
        if not (same_cols and same_vals and same_text):
            print("FAIL: the rebuild does not reproduce the committed file")
            return 1
        print("OK: the rebuild reproduces the committed file row for row")
        return 0

    df, info = build(NEW_FEATURES)
    old_k, new_k = set(key(base)), set(key(df))
    print(f"new features {NEW_FEATURES}: {info['counts']} (was {base['datatype'].value_counts().to_dict()})")
    for dt in ("coretop", "culture", "mesocosm"):
        o = {k for k in old_k if k.startswith(dt + "|")}
        n = {k for k in new_k if k.startswith(dt + "|")}
        print(f"  {dt:9s} kept {len(n & o)}, added {len(n - o)}, dropped {len(o - n)}")
    if args.apply:
        df.to_csv(OUT_CSV, index=False)
        print(f"wrote {OUT_CSV} ({len(df)} rows); now run scripts/paper/add_retained_flag.py --apply")
    else:
        print("dry run; --apply writes the file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
