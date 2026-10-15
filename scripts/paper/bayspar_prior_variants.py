#!/usr/bin/env python3
"""BAYSPAR SST predictions for the gridded core-tops under the three prior means of
run_coretop_maps.py --prior, so TEXAS and BAYSPAR are scored with identical priors.

    python scripts/paper/bayspar_prior_variants.py

Rows are the core-top map sites, in the same order (run_coretop_maps.coretop_frame()), so a
row lines up with position t_est_dim_0 of the TEXAS inverse batches. For each prior, BAYSPAR
standard (spatial) mode at the 0.4-degree cell centre, prior_std 10, temptype 'sst', as the
published comparison (archive SI_code2, predT_bayspar_p16_p50_p84.csv) did; only the prior mean
changes:

    measured   the site's measured SST (the published setting)
    latband    30 cos^2(lat) - 1
    const15    15 degC

Writes <manuscript_refit>/bayspar_prior_variants.csv: row, cell, Latitude, SST, TEX86, and
p16/p50/p84 per prior.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_coretop_maps as M  # noqa: E402
import run_manuscript_refits as R  # noqa: E402

PRIOR_STD = 10.0


def sites() -> pd.DataFrame:
    """coretop_frame()'s rows and order, with TEX86 (which that frame does not carry)."""
    df = R.coretop()
    model_cols = [c for c in ("SST", "t_sf2tc_avg", R.PROXY, "gdgt23ratio", "gdgt23ratio_se",
                              "no3_sf2tc_avg", "thermoNO3_se") if c in df.columns]
    out = df[df[model_cols].notna().all(axis=1)].reset_index(drop=True)
    ref = M.coretop_frame()
    assert len(out) == len(ref) and np.allclose(out["SST"], ref["SST"]), "site order differs from the maps"
    return out


def percentiles(pred, q=(16, 50, 84)):
    """numpy-2-safe Prediction.percentile() (baysparpy 0.0.3 passes interpolation=)."""
    axes = tuple(range(1, pred.ensemble.ndim))
    return np.ravel(np.percentile(pred.ensemble, q=q, axis=axes, method="nearest"))


def main() -> int:
    import bayspar as bsr

    df = sites()
    out = pd.DataFrame({"row": np.arange(len(df)), "match_lat_04deg": df["match_lat_04deg"],
                        "match_lon_04deg": df["match_lon_04deg"], "Latitude": df["Latitude"],
                        "SST": df["SST"], "TEX86": df["TEX86"]})
    for prior in M.PRIOR_MEANS:
        mu = (df["SST"].to_numpy(float) if prior == "measured"
              else np.asarray(M.PRIOR_MEANS[prior](df["Latitude"].to_numpy(float)), float))
        q = np.full((len(df), 3), np.nan)
        fails = []
        for i, r in df.iterrows():
            if not np.isfinite(r["TEX86"]):
                continue
            try:
                res = bsr.predict_seatemp(np.atleast_1d(r["TEX86"]), lat=r["match_lat_04deg"],
                                          lon=r["match_lon_04deg"], prior_mean=float(mu[i]),
                                          prior_std=PRIOR_STD, temptype="sst")
                q[i] = percentiles(res)
            except Exception as e:  # counted, never swallowed
                fails.append(type(e).__name__)
        for j, p in enumerate(("p16", "p50", "p84")):
            out[f"bsr_{prior}_{p}"] = q[:, j]
        R.log(f"BAYSPAR prior={prior}: {int(np.isfinite(q[:, 1]).sum())} of {len(df)} predicted"
              + (f"; {len(fails)} failed {Counter(fails).most_common()}" if fails else ""))
    path = R.RESULTS_DIR / "bayspar_prior_variants.csv"
    out.to_csv(path, index=False)
    R.log(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
