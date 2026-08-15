#!/usr/bin/env python
"""Fit the four bounded-T forward calibrations the manuscript refit left out.

The 2026-08-12 refit (``run_manuscript_refits.py``) fitted each arm with the
FULL predictor set only -- G23 + NO3. The additive-EIV arm, fitted earlier and
piecemeal, also has the two single-predictor cells:

    GHEA  sst/thm  G23   G23-N10   N10          <- all six present
    GHEB  sst/thm        G23-N10                <- only two

``SI_code02_t0shift_TEXAS_analysis.ipynb`` draws a five-layer prior-comparison
figure per temperature target (culmeso, univariate, +G23, +NO3, +G23+NO3), so
the two missing cells are two missing layers in each of those figures.

This script fills exactly those four:

    tx.GHEB.sst.sri03.G23    tx.GHEB.sst.sri03.N10
    tx.GHEB.thm.sri03.G23    tx.GHEB.thm.sri03.N10

Comparability is the whole point, so nothing here is re-derived:

* The **budget is the refit's** (400/1000, 4 chains, seed 42), imported rather
  than retyped, so these cannot drift from it.
* The **training rows are the refit's** -- ``coretop()`` dropna'd on all six
  multivariate columns, N=1513. That is deliberately the same row set the FULL
  fit uses, not the larger set a single predictor could support on its own: the
  figure compares parameters ACROSS predictor sets, so the rows have to be held
  fixed or the comparison confounds predictors with sample size. It also
  matches how the existing GHEA single-predictor fits were built (verified:
  N_crtp = 1513 in all three GHEA cells).
* ``culmeso`` and the univariate baseline are **loaded from the refit
  manifest**, never resampled, so the hyperpriors and R2_thermal feeding these
  fits are byte-identical to the ones behind the G23-N10 runs.

Results go to their own manifest, NOT the refit's. The refit manifest is what
``run_manuscript_refits.py audit`` reads to certify one-budget comparability,
and its forward keys are ``fwd|<variant>|<temptype>|<proxy>`` -- appending
these would collide with the full-predictor rows under the same key and make
the audit describe something that never happened.

    python scripts/fit_t0shift_single_predictors.py --dry-run
    python scripts/fit_t0shift_single_predictors.py
    python scripts/fit_t0shift_single_predictors.py --force      # refit existing
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_manuscript_refits as R  # noqa: E402  (path set above)

MANIFEST = R.RESULTS_DIR / "single_predictor_manifest.csv"

# predictor cell -> (use G23, use NO3). The full cell is the refit's job.
CELLS = [
    ("G23", True, False),
    ("N10", False, True),
]


def existing_case(temptype: str, g23: bool, no3: bool) -> str | None:
    """Case id if this calibration is already in the cache, else None."""
    from TEXAS.utils.naming import case_from_attrs, resolve_posterior_path
    from TEXAS.utils.paths import POSTERIOR_CACHE_DIR

    attrs = {
        "stan_model_name": R.VARIANTS["bnd"]["fwd"],
        "temptype": temptype,
        "proxy_name": R.PROXY,
        "use_gdgt23ratio": int(g23),
        "use_no3": int(no3),
    }
    if no3:
        attrs["no3_cutoff"] = float(R.NO3_CUTOFF)
    case = str(case_from_attrs(attrs))
    return case if resolve_posterior_path(case, POSTERIOR_CACHE_DIR) else None


def fit_one(temptype, cell, g23, no3, culmeso_post, univ_post, dry_run=False):
    from TEXAS.data import build_fwd_data
    from TEXAS.stan.io import save_posterior
    from TEXAS.stan.sampler import get_posterior

    col = R.TEMPTYPES[temptype]
    # Identical rows to the full-predictor fit -- see the module docstring.
    reg = R.coretop()[[col, R.PROXY, "gdgt23ratio", "gdgt23ratio_se",
                       "no3_sf2tc_avg", "thermoNO3_se"]].dropna()
    r2 = float(univ_post["R2_full"].mean())

    kw = dict(t_crtp=reg[col].values, proxy_crtp=reg[R.PROXY].values,
              R2_thermal=r2, culmeso_posterior=culmeso_post)
    if g23:
        kw.update(gdgt23ratio_crtp=reg["gdgt23ratio"].values,
                  sd_gdgt23ratio_crtp=reg["gdgt23ratio_se"].values)
    if no3:
        kw.update(no3_crtp=reg["no3_sf2tc_avg"].values,
                  sd_no3_crtp=reg["thermoNO3_se"].values,
                  no3_cutoff=R.NO3_CUTOFF)

    if dry_run:
        R.log(f"    would fit bnd {temptype} {cell}  (N={len(reg)}, "
              f"R2_thermal={r2:.5f})")
        return None

    data = build_fwd_data(**kw)
    t0 = time.time()
    post, _ = get_posterior(data=data, stan_file=R.VARIANTS["bnd"]["fwd"],
                            temptype=temptype, proxy_name=R.PROXY,
                            iter_warmup=R.FWD_WARMUP,
                            iter_sampling=R.FWD_SAMPLING,
                            chains=R.CHAINS, seed=R.SEED)
    path = save_posterior(post)
    wall = round(time.time() - t0, 1)
    R.log(f"    bnd {temptype} {cell}: {wall}s  "
          f"R-hat={post.attrs.get('stan_diag_max_rhat')}  -> {R.case_of(path)}")
    return dict(key=f"fwd|bnd|{temptype}|{cell}|{R.PROXY}", stage="forward",
                model=R.VARIANTS["bnd"]["fwd"], variant="bnd", cell=cell,
                temptype=temptype, iter_warmup=R.FWD_WARMUP,
                iter_sampling=R.FWD_SAMPLING, n_obs=len(reg), r2_thermal=r2,
                max_rhat=post.attrs.get("stan_diag_max_rhat"),
                divergences=post.attrs.get("stan_diag_n_divergent"),
                wall_sec=wall, path=str(path), status="ok")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true",
                    help="refit even if the case is already in the cache")
    ap.add_argument("--force-lock", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--temptypes", nargs="+", choices=list(R.TEMPTYPES),
                    default=list(R.TEMPTYPES))
    args = ap.parse_args(argv)

    t0 = time.time()
    R.log(f"bounded-T single-predictor fits at {R.FWD_WARMUP}/{R.FWD_SAMPLING}, "
          f"{R.CHAINS} chains, seed {R.SEED}")

    todo, skip = [], []
    for tt in args.temptypes:
        for cell, g23, no3 in CELLS:
            have = existing_case(tt, g23, no3)
            (skip if (have and not args.force) else todo).append((tt, cell, g23, no3, have))
    for tt, cell, _, _, have in skip:
        R.log(f"  skip  bnd {tt} {cell} — already in the cache ({have})")
    R.log(f"  {len(todo)} fit(s) to run, {len(skip)} skipped")
    if not todo:
        return 0

    with R.single_instance(force=args.force_lock):
        R.STOP.install()
        # From the refit manifest, not resampled -- see the module docstring.
        culmeso_post = R.fit_culmeso()
        rows = []
        for tt in args.temptypes:
            cells = [c for c in todo if c[0] == tt]
            if not cells:
                continue
            univ_post = R.fit_univ(tt, culmeso_post)
            for _, cell, g23, no3, _ in cells:
                if R.STOP.requested:
                    R.log("stopping before the next fit, as requested")
                    break
                row = fit_one(tt, cell, g23, no3, culmeso_post, univ_post,
                              dry_run=args.dry_run)
                if row:
                    rows.append(row)
                    # Write after every fit: a kill mid-run keeps what finished.
                    df = pd.concat(
                        [pd.read_csv(MANIFEST) if MANIFEST.exists() else pd.DataFrame(),
                         pd.DataFrame([row])], ignore_index=True)
                    df.to_csv(MANIFEST, index=False)
            if R.STOP.requested:
                break

    if rows:
        R.log("")
        R.log(f"wrote {len(rows)} posterior(s); manifest -> {MANIFEST}")
    R.log(f"done in {timedelta(seconds=int(time.time() - t0))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
