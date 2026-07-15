#!/usr/bin/env python
"""Batch driver - Group C spatially-blocked cross-validation of TEXAS forward skill.

Reviewers R2/R3 asked for out-of-sample, spatially-independent skill to support
"outperforms all existing calibrations". This script refits the forward model on
each spatial fold's training coretop sites and scores its held-out sites, giving
out-of-sample R2/RMSE credible intervals (see :mod:`TEXAS.validation.crossval`).

It is an **hours-scale** job (one forward refit per fold), so
:func:`TEXAS.validation.run_spatial_crossval` checkpoints each fold to
``data/revision1/groupC/`` and skips folds already on disk - safe to re-run /
resume after an interruption.

Data (LFS-gated -> fetch from Zenodo, LFS is over budget):

    python -c "import TEXAS; TEXAS.download_training_data(); TEXAS.download_posteriors()"

Then, e.g. (fast univariate CV, 5 spatial-block folds):

    python scripts/revision1/run_crossval.py \
        --csv data/spreadsheets/ds_gridded_screened_global_compilation_finalized.csv \
        --culmeso-posterior gen_logi_fixed_culmeso_cultureT_scaledRI_cren3 \
        --temptype SST --scheme block --n-folds 5

Heavier multivariate EIV CV (matches the headline model; needs R2_thermal):

    python scripts/revision1/run_crossval.py --csv ... \
        --stan-file gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv \
        --predictors both --r2-thermal 0.72 --scheme ocean_basin

Column names default to the SI_code2 compilation schema but are all overridable
(``--*-col``) so the driver works on differently-named tables without edits.
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd


def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", required=True, help="Training compilation CSV (culture+mesocosm+coretop rows).")
    p.add_argument("--culmeso-posterior", required=True,
                   help="Name of the saved stage-1 culmeso posterior (hyperprior source).")
    p.add_argument("--stan-file", default="gen_logi_fixed_hier_crtp_univ_priorApprox",
                   help="Forward Stan model to refit per fold. Default: univariate priorApprox.")
    p.add_argument("--temptype", choices=["SST", "thermoT"], default="SST")
    p.add_argument("--proxy-name", default="scaledRI_cren3")

    # Fold layout
    p.add_argument("--scheme", choices=["block", "ocean_basin"], default="block")
    p.add_argument("--n-folds", type=int, default=5, help="Number of block folds (--scheme block).")
    p.add_argument("--block-deg", type=float, default=20.0, help="Block edge length in degrees (--scheme block).")
    p.add_argument("--min-test", type=int, default=5, help="Drop folds with fewer held-out sites than this.")
    p.add_argument("--seed", type=int, default=42)

    # Predictors (EIV multivariate model)
    p.add_argument("--predictors", choices=["none", "gdgt23ratio", "no3", "both"], default="none")
    p.add_argument("--r2-thermal", type=float, default=None,
                   help="Thermal-only R^2 for the EIV sigma-prior scale (required for *_eiv models).")
    p.add_argument("--no3-cutoff", type=float, default=1.0)
    p.add_argument("--n-draws", type=int, default=500, help="Posterior draws for held-out prediction.")

    # Column-name overrides (default to the SI_code2 schema)
    p.add_argument("--datatype-col", default="datatype")
    p.add_argument("--coretop-value", default="coretop")
    p.add_argument("--sst-col", default="SST")
    p.add_argument("--thermo-col", default="t_sf2tc_avg")
    p.add_argument("--lat-col", default="match_lat_04deg")
    p.add_argument("--lon-col", default="match_lon_04deg")
    p.add_argument("--gdgt23ratio-col", default="gdgt23ratio")
    p.add_argument("--gdgt23ratio-se-col", default="gdgt23ratio_se")
    p.add_argument("--no3-col", default="no3_sf2tc_avg")
    p.add_argument("--no3-se-col", default="thermoNO3_se")

    p.add_argument("--no-save-posteriors", action="store_true",
                   help="Do not persist each fold's refit posterior (saves disk).")
    return p.parse_args(argv)


def _require_columns(df: pd.DataFrame, cols: list[str], where: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise SystemExit(
            f"[run_crossval] {where}: missing columns {missing}. "
            f"Available: {list(df.columns)[:20]}... - set the matching --*-col flag."
        )


def main(argv=None) -> int:
    args = _parse_args(argv)

    # Import here so --help works without the (heavy) TEXAS/Stan import chain.
    from TEXAS.stan.io import load_posterior
    from TEXAS.validation import (
        CrossvalArrays,
        assign_block_folds,
        assign_ocean_basin_folds,
        make_folds,
        run_spatial_crossval,
    )

    use_g23 = args.predictors in ("gdgt23ratio", "both")
    use_no3 = args.predictors in ("no3", "both")
    is_eiv = "eiv" in args.stan_file
    if is_eiv and args.r2_thermal is None:
        raise SystemExit("[run_crossval] --r2-thermal is required for *_eiv models "
                         "(compute it from a thermal-only coretop posterior: R2_full.mean()).")

    df = pd.read_csv(args.csv)
    _require_columns(df, [args.datatype_col], "training CSV")
    coretop = df[df[args.datatype_col] == args.coretop_value].copy()
    if coretop.empty:
        raise SystemExit(f"[run_crossval] no rows with {args.datatype_col}=={args.coretop_value!r}.")

    temp_col = args.sst_col if args.temptype == "SST" else args.thermo_col
    needed = [temp_col, args.proxy_name, args.lat_col, args.lon_col]
    if use_g23:
        needed += [args.gdgt23ratio_col, args.gdgt23ratio_se_col]
    if use_no3:
        needed += [args.no3_col, args.no3_se_col]
    _require_columns(coretop, needed, "coretop subset")
    coretop = coretop.dropna(subset=needed).reset_index(drop=True)

    lons = coretop[args.lon_col].to_numpy(float)
    lats = coretop[args.lat_col].to_numpy(float)

    if args.scheme == "block":
        fold_ids = assign_block_folds(lons, lats, block_deg=args.block_deg,
                                      n_folds=args.n_folds, seed=args.seed)
        labels = None
    else:
        fold_ids, labels = assign_ocean_basin_folds(lons, lats)
    folds = make_folds(fold_ids, labels, min_test=args.min_test)

    print(f"[run_crossval] {len(coretop)} coretop sites | scheme={args.scheme} | "
          f"{len(folds)} scored folds | model={args.stan_file} | temptype={args.temptype}")
    for f in folds:
        print(f"    fold {f.fold_id:>2} {f.label:<22} train={f.n_train:>4}  test={f.n_test:>4}")

    arrays = CrossvalArrays(
        t=coretop[temp_col].to_numpy(float),
        proxy=coretop[args.proxy_name].to_numpy(float),
        lons=lons, lats=lats,
        gdgt23ratio=coretop[args.gdgt23ratio_col].to_numpy(float) if use_g23 else None,
        no3=coretop[args.no3_col].to_numpy(float) if use_no3 else None,
        sd_gdgt23ratio=coretop[args.gdgt23ratio_se_col].to_numpy(float) if use_g23 else None,
        sd_no3=coretop[args.no3_se_col].to_numpy(float) if use_no3 else None,
        extra_builder_kwargs=({"no3_cutoff": args.no3_cutoff} if use_no3 else {}),
    )

    culmeso_post = load_posterior(args.culmeso_posterior)

    table = run_spatial_crossval(
        arrays, folds,
        stan_file=args.stan_file,
        temptype=args.temptype,
        proxy_name=args.proxy_name,
        culmeso_posterior=culmeso_post,
        R2_thermal=args.r2_thermal,
        n_draws=args.n_draws,
        seed=args.seed,
        save_posteriors=not args.no_save_posteriors,
    )

    print("\n[run_crossval] held-out skill (out-of-sample, spatially-blocked):")
    with pd.option_context("display.max_columns", None, "display.width", 140):
        print(table.to_string())
    print("\n[run_crossval] results saved under data/revision1/groupC/ "
          "(crossval_summary + per-fold checkpoints).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
