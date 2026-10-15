#!/usr/bin/env python3
"""Inverse skill of TEXAS and BAYSPAR on the gridded core-tops under three prior means.

    python scripts/paper/score_prior_variants.py

Reads the TEXAS core-top inverse batches written by run_coretop_maps.py (--prior measured,
latband, const15; the T0-shift multivariate SST and the thermal-only SST configurations) and
BAYSPAR's predictions from bayspar_prior_variants.py, and scores each against the measured SST:
bias, RMSE, MAE, R2 and 68% coverage, over all sites and by latitude band (tropics |lat| < 23.5,
mid-latitudes 23.5-60, polar > 60). Every model gets the same prior in each variant, so the
change from "measured" to "latband" / "const15" shows how much of each model's skill came from a
prior centred on the answer.

Writes <manuscript_refit>/prior_variant_skill.csv (and prints it).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_coretop_maps as M  # noqa: E402
import run_manuscript_refits as R  # noqa: E402

TEXAS_MODELS = {"TEXAS T0-shift (T + G23 + NO3)": ("bnd", True, True),
                "TEXAS thermal-only": ("univ", False, False)}
BANDS = [("all", 0, 91), ("tropics (<23.5)", 0, 23.5), ("mid-lat (23.5-60)", 23.5, 60),
         ("polar (>60)", 60, 91)]


def load_texas(case: str, prior: str, n_batches: int) -> pd.DataFrame | None:
    from TEXAS.utils.paths import INVT_CACHE_DIR
    stem = "global_coretop" if prior == "measured" else f"global_coretop_{prior}"
    files = [INVT_CACHE_DIR / f"{case}.inv.{stem}_b{b:02d}.ud.nc" for b in range(1, n_batches + 1)]
    if not all(f.exists() for f in files):
        missing = [f.name for f in files if not f.exists()]
        R.log(f"  missing {len(missing)} batch(es) for {case} / {prior}, e.g. {missing[0]}")
        return None
    return pd.concat([xr.open_dataset(f)["t_est"].to_pandas().T for f in files], ignore_index=True)


def score(p50, p16, p84, y):
    e = p50 - y
    ok = np.isfinite(e)
    if not ok.any():
        return {}
    return dict(bias=e[ok].mean(), rmse=float(np.sqrt((e[ok] ** 2).mean())), mae=float(np.abs(e[ok]).mean()),
                r2=float(1 - np.sum(e[ok] ** 2) / np.sum((y[ok] - y[ok].mean()) ** 2)),
                cov68=float(np.mean((y[ok] >= p16[ok]) & (y[ok] <= p84[ok]))), n=int(ok.sum()))


def main() -> int:
    bs = pd.read_csv(R.RESULTS_DIR / "bayspar_prior_variants.csv")
    y, lat = bs["SST"].to_numpy(float), np.abs(bs["Latitude"].to_numpy(float))
    n_batches = int(np.ceil(len(bs) / M.BATCH))
    rows = []
    for prior in M.PRIOR_MEANS:
        preds = {}
        for label, (arm, g23, no3) in TEXAS_MODELS.items():
            q = load_texas(M.fwd_case(arm, "SST", g23, no3), prior, n_batches)
            if q is not None:
                assert len(q) == len(bs), f"{label}/{prior}: {len(q)} rows vs {len(bs)} sites"
                preds[label] = (q[0.50].to_numpy(), q[0.16].to_numpy(), q[0.84].to_numpy())
        preds["BAYSPAR (SST)"] = tuple(bs[f"bsr_{prior}_{p}"].to_numpy(float) for p in ("p50", "p16", "p84"))
        for label, (p50, p16, p84) in preds.items():
            for band, lo, hi in BANDS:
                m = (lat >= lo) & (lat < hi)
                rows.append(dict(prior=prior, model=label, band=band,
                                 **score(p50[m], p16[m], p84[m], y[m])))
    out = pd.DataFrame(rows)
    path = R.RESULTS_DIR / "prior_variant_skill.csv"
    out.to_csv(path, index=False)
    with pd.option_context("display.width", 200, "display.max_rows", 200):
        print(out.round(3).to_string(index=False))
    R.log(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
