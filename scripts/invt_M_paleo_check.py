#!/usr/bin/env python
"""Does M matter where the paper's claims actually live?

Part 3's M ladder runs on modern core-tops, whose Scaled RI tops out at 0.870.
The records the manuscript reconstructs do not stay inside that range:

    ODP 1259            RI3 0.885-0.955   entirely ABOVE the modern maximum
    South Dover Bridge  RI3 0.679-0.924   partly above
    ODP 959             RI3 0.539-0.970   spans past it
    Co1010              RI3 0.122-0.518   below the modern minimum

Above the upper asymptote the generalized logistic flattens, the likelihood goes
nearly flat in T, and the posterior turns prior-dominated and heavy-tailed. That
is the regime where a coarse mixture over M calibration draws could plausibly
bite, and it is a regime the core-top set cannot reach by construction. So the
core-top ladder alone does not settle the question for paleo use.

Writes  data/revision1/groupA/param_sensitivity/invt_M_paleo.csv
    python scripts/invt_M_paleo_check.py
"""
from __future__ import annotations
import sys, time
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_param_sensitivity as R

M_VALUES = [25, 100, 300, 500]
ITER_WARMUP, ITER_SAMPLING, CHAINS, SEED = 500, 1000, 4, 42
PRIOR_SIGMA_T = 10.0
NO3_OFF = 10.0        # above the 1.0 cutoff: the NO3 correction is switched off,
                      # which is the paleo default (nitrate is not observable)

#: prior mean per record, matching SI03's showcases. The value is irrelevant to
#: an M comparison so long as it is held fixed across M -- what matters is that
#: it is a climatological guess, not the answer.
RECORDS = {
    "ODP1259":            40.0,   # upper-asymptote stress case
    "Co1010":              5.0,   # lower-asymptote stress case
    "South Dover Bridge": 35.0,   # PETM body
    "ODP959":             35.0,   # PETM body
}
PALEO_CSV = "data/spreadsheets/published_data/PhanTEX_v001_modified_050126.csv"
OUT = R.REPO / "data" / "revision1" / "groupA" / "param_sensitivity" / "invt_M_paleo.csv"


def main() -> int:
    from TEXAS.stan.invT import predict_temperature_from_proxyObs
    from TEXAS.data.builder import InvTConfig
    from TEXAS.stan.io import load_posterior

    fwd = R._invt_fwd_name()
    attrs = load_posterior(fwd).attrs
    R.log(f"forward calibration: {fwd}")

    df = pd.read_csv(R.REPO / PALEO_CSV, low_memory=False)
    col = R.PROXIES[R.PRODUCTION_PROXY]["column"]
    rows = []
    for rec, mu in RECORDS.items():
        sub = df[df.SiteName == rec].dropna(subset=[col, "gdgt23ratio"]).reset_index(drop=True)
        R.log(f"{rec}: n={len(sub)}  RI3 {sub[col].min():.3f}-{sub[col].max():.3f}")
        preds = {}
        if int(attrs.get("use_gdgt23ratio", 0)):
            preds["gdgt23ratio"] = sub["gdgt23ratio"].to_numpy(float)
        if int(attrs.get("use_no3", 0)):
            preds["no3"] = np.full(len(sub), NO3_OFF)
        for M in M_VALUES:
            t0 = time.time()
            res = predict_temperature_from_proxyObs(
                proxyObs=sub[col].to_numpy(float),
                prior_mu_t=np.full(len(sub), mu), prior_sigma_t=PRIOR_SIGMA_T,
                fwd_posterior_name=fwd, site_name=f"Mcheck_{rec.replace(' ','')}_M{M}",
                temptype=R.TEMPTYPE, proxy_name=col, predictors=preds or None,
                config=InvTConfig(n_draws=M), chains=CHAINS,
                iter_warmup=ITER_WARMUP, iter_sampling=ITER_SAMPLING, seed=SEED,
                constraint_type=R.INVT_CONSTRAINT,
                save_results=False,          # a tuning run is not a reconstruction
            )
            p16, p50, p84 = (np.asarray(res[k], float) for k in ("p16", "p50", "p84"))
            for i in range(len(sub)):
                rows.append(dict(record=rec, M=M, sample=i, proxy=float(sub[col][i]),
                                 p16=p16[i], p50=p50[i], p84=p84[i]))
            R.log(f"    M={M:4d}  {time.time()-t0:5.0f}s  "
                  f"median T {np.median(p50):6.2f}  mean 68% width "
                  f"{np.mean(p84-p16):5.2f} degC")
    pd.DataFrame(rows).to_csv(OUT, index=False)
    R.log(f"wrote {OUT}  ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
