#!/usr/bin/env python
"""invT reconstructions over the gridded global coretop set, per model arm.

These are what the residual and 1-sigma uncertainty maps are drawn from
(fig9 / fig10 and their SI companions). The additive-EIV versions exist as
``global_coretop_*_direct.nc`` in the invT cache **on the machine they were run
on** -- ``data/cache/`` is gitignored, so this box has none of them. This script
produces them from scratch, for either arm (--arm bnd | eiv).

Scope: 2 predictor sets x 2 temperature targets = 4 configurations, each over
the 1513 coretop sites that have every multivariate column.

    bnd   G23 / G23-N10   tx.GHEB.{sst,thm}.sri03.*
    eiv   G23 / G23-N10   tx.GHEA.{sst,thm}.sri03.*

The thermal-only (univariate) layer is deliberately NOT re-run: it has no
predictors, so it is identical in both arms -- bounded-T only changes where the
predictors enter. There is also no invT univariate bounded-T model, by design.

Budget matches the manuscript refit's inverse settings (500/1000, M=300,
4 chains, seed 42), imported rather than retyped, so these are comparable with
every reconstruction already in the cache.

Prior: constant mu=20 degC, sigma=10 degC at every site. Constant on purpose --
a per-site prior informed by modern SST would make the residual map partly a
map of the prior. It is also what makes the coverage numbers in RESUME.md
conservative, and it keeps this comparable with the additive run.

Batched at 250 sites so a kill loses at most one batch; each batch is recorded
in a manifest and skipped on restart. Batches concatenate along t_est_dim_0,
which is what the notebook loader expects.

    python scripts/run_coretop_maps.py --dry-run
    python scripts/run_coretop_maps.py --arm bnd
    python scripts/run_coretop_maps.py --arm eiv --temptypes SST
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_manuscript_refits as R  # noqa: E402

# The bnd filename is kept exactly as first written so the run already on disk
# stays resumable across this rename.
MANIFEST_BY_ARM = {
    "bnd": "coretop_maps_boundedT_manifest.csv",
    "eiv": "coretop_maps_eiv_manifest.csv",
    "univ": "coretop_maps_univ_manifest.csv",
}
BATCH = 250
PRIOR_MU_T, PRIOR_SIGMA_T = 20.0, 10.0

# predictor set -> (use G23, use NO3)
CONFIGS = [
    ("G23", True, False),
    ("G23-N10", True, True),
]


def coretop_frame() -> pd.DataFrame:
    """The same 1513 rows every multivariate fit is trained on."""
    cols = ["SST", "t_sf2tc_avg", R.PROXY, "gdgt23ratio", "gdgt23ratio_se",
            "no3_sf2tc_avg", "thermoNO3_se", "Latitude", "Longitude",
            "match_lat_04deg", "match_lon_04deg"]
    df = R.coretop()
    have = [c for c in cols if c in df.columns]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        R.log(f"  note: coretop frame lacks {missing} (kept: {len(have)} cols)")
    # dropna on the modelling columns only -- lat/lon may be named differently
    model_cols = [c for c in ("SST", "t_sf2tc_avg", R.PROXY, "gdgt23ratio",
                              "gdgt23ratio_se", "no3_sf2tc_avg",
                              "thermoNO3_se") if c in df.columns]
    return df[have].dropna(subset=model_cols).reset_index(drop=True)


def fwd_case(arm: str, temptype: str, g23: bool, no3: bool) -> str:
    from TEXAS.utils.naming import case_from_attrs
    attrs = {
        "stan_model_name": (R.UNIV_STEM if arm == "univ"
                            else R.VARIANTS[arm]["fwd"]),
        "temptype": temptype,
        "proxy_name": R.PROXY,
        "use_gdgt23ratio": int(g23),
        "use_no3": int(no3),
    }
    if no3:
        attrs["no3_cutoff"] = float(R.NO3_CUTOFF)
    return str(case_from_attrs(attrs))


def manifest_path(arm: str) -> Path:
    return R.RESULTS_DIR / MANIFEST_BY_ARM[arm]


def read_manifest(arm: str) -> pd.DataFrame:
    p = manifest_path(arm)
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


def record(arm: str, row: dict) -> None:
    R.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.concat([read_manifest(arm), pd.DataFrame([row])], ignore_index=True)
    df.to_csv(manifest_path(arm), index=False)


def done_keys(arm: str) -> set:
    df = read_manifest(arm)
    if df.empty or "key" not in df:
        return set()
    return set(df[df.get("status", "ok") == "ok"]["key"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", choices=("bnd", "eiv", "univ"), default="bnd",
                    help="bnd = bounded-T, eiv = additive parent, "
                         "univ = thermal-only baseline (run ONCE; it has no "
                         "predictors, so it is shared by both arms)")
    ap.add_argument("--temptypes", nargs="+", choices=list(R.TEMPTYPES),
                    default=list(R.TEMPTYPES))
    ap.add_argument("--batch", type=int, default=BATCH)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force-lock", action="store_true")
    args = ap.parse_args(argv)

    from TEXAS.predict import predict_T_from_proxyObs
    from TEXAS.utils.naming import resolve_posterior_path
    from TEXAS.utils.paths import POSTERIOR_CACHE_DIR

    df = coretop_frame()
    n = len(df)
    starts = list(range(0, n, args.batch))
    t_start = time.time()

    # The .nc files index results by position along t_est_dim_0, so the row
    # order IS the join key. Write it out once, with coordinates and the
    # measured temperatures, or the maps depend on reproducing this frame
    # exactly by memory.
    # arm-independent: the same 1513 rows in the same order for both arms
    sites_csv = R.RESULTS_DIR / "coretop_maps_sites.csv"
    if not args.dry_run:
        R.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out = df.copy()
        out.insert(0, "row", np.arange(len(out)))
        out.insert(1, "batch", (out["row"] // args.batch) + 1)
        out.to_csv(sites_csv, index=False)
        R.log(f"site table -> {sites_csv}")

    R.log(f"coretop {args.arm} maps: {n} sites, batches of {args.batch} "
          f"({len(starts)} per configuration)")
    R.log(f"budget {R.INV_WARMUP}/{R.INV_SAMPLING}, M={R.INV_M}, "
          f"{R.CHAINS} chains, seed {R.SEED}; prior N({PRIOR_MU_T}, {PRIOR_SIGMA_T})")

    todo = []
    # The thermal-only baseline is a single predictor-free configuration per
    # target. It is shared by both arms -- bounded-T only changes where the
    # predictors enter, and there are none here -- so it is run once under its
    # own manifest rather than duplicated per arm. fig9/fig10 need it as the
    # "univ" layer, which is why it cannot simply be skipped.
    configs = [("p0", False, False)] if args.arm == "univ" else CONFIGS
    for tt in args.temptypes:
        for cell, g23, no3 in configs:
            case = fwd_case(args.arm, tt, g23, no3)
            if resolve_posterior_path(case, POSTERIOR_CACHE_DIR) is None:
                R.log(f"  SKIP {tt} {cell}: forward posterior {case} not in cache")
                continue
            todo.append((tt, cell, g23, no3, case))
    R.log(f"{len(todo)} configuration(s) x {len(starts)} batches = "
          f"{len(todo) * len(starts)} Stan runs")
    for tt, cell, _, _, case in todo:
        R.log(f"    {tt:8s} {cell:8s} <- {case}")
    if args.dry_run or not todo:
        return 0

    have = done_keys(args.arm)
    with R.single_instance(force=args.force_lock):
        R.STOP.install()
        for tt, cell, g23, no3, case in todo:
            col = R.TEMPTYPES[tt]
            tag = R._TEMPTYPE_TAG[tt] if hasattr(R, "_TEMPTYPE_TAG") else (
                "sst" if tt == "SST" else "thermoT")
            for bi, s0 in enumerate(starts, start=1):
                key = f"{tt}|{cell}|b{bi:02d}"
                if key in have:
                    R.log(f"  skip {key} (already done)")
                    continue
                if R.STOP.requested:
                    R.log("stopping between batches, as requested")
                    return 0
                sub = df.iloc[s0:s0 + args.batch]
                preds = ({"gdgt23ratio": sub["gdgt23ratio"].values}
                         if g23 else None)
                if no3:
                    preds["no3"] = sub["no3_sf2tc_avg"].values
                t0 = time.time()
                predict_T_from_proxyObs(
                    proxyObs=sub[R.PROXY].values,
                    prior_mu_t=PRIOR_MU_T, prior_sigma_t=PRIOR_SIGMA_T,
                    fwd_posterior=case,
                    predictors=preds,
                    site_name=f"global_coretop_b{bi:02d}",
                    proxy_name=R.PROXY,
                    temptype=tag,
                    save_results=True,
                    filename_tag="",
                )
                wall = round(time.time() - t0, 1)
                R.log(f"  {key}: {len(sub)} sites in {wall}s")
                record(args.arm, dict(key=key, arm=args.arm, temptype=tt, cell=cell, batch=bi,
                            fwd_case=case, n_sites=len(sub),
                            iter_warmup=R.INV_WARMUP, M=R.INV_M,
                            prior_mu_t=PRIOR_MU_T, prior_sigma_t=PRIOR_SIGMA_T,
                            wall_sec=wall, status="ok"))

    R.log("")
    R.log(f"done in {timedelta(seconds=int(time.time() - t_start))}; "
          f"manifest -> {manifest_path(args.arm)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
