#!/usr/bin/env python
"""Parameter table with credible intervals, noise terms included.

Written for Reviewer #3, who could not find the estimates of the noise terms --
sigma_culmeso (Eq 11, the top layer) and epsilon (Eq 14, the bottom layer) --
and pointed out that R2 and RMSE, being functions of probabilistic parameters,
need credible intervals rather than point values.

Both were reporting gaps, not modelling gaps: every quantity below is already a
full posterior distribution in the cached .nc files. Nothing is refitted here;
this reads what is on disk and quotes it properly.

Two things it is careful about:

* **Credible, not confidence.** These are posterior quantiles. The column
  headers say so.
* **R2_full and bayesR2_full are different quantities** and differ by ~0.06.
  Both are emitted, labelled, so the manuscript can quote one and name it
  rather than leaving a reader to guess which definition produced the number.

    python scripts/build_parameter_table.py                # markdown to stdout
    python scripts/build_parameter_table.py --csv out.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

# label -> (case id, what it is)
CASES = [
    ("culture + mesocosm (top layer, Eq 11)", "tx.GCDU.cul.sri03.p0"),
    ("coretop, thermal only (SST)", "tx.GHPU.sst.sri03.p0"),
    ("coretop, additive EIV (SST)", "tx.GHEA.sst.sri03.G23-N10"),
    ("coretop, bounded-T (SST)", "tx.GHEB.sst.sri03.G23-N10"),
    ("coretop, thermal only (thermoT)", "tx.GHPU.thm.sri03.p0"),
    ("coretop, additive EIV (thermoT)", "tx.GHEA.thm.sri03.G23-N10"),
    ("coretop, bounded-T (thermoT)", "tx.GHEB.thm.sri03.G23-N10"),
]

# Ordered so the noise terms sit with the parameters, not in a diagnostics
# afterthought -- the reviewer's point was precisely that they are model
# parameters.
PARAM_ORDER = ["t0", "k", "b", "v",
               "beta_G23", "beta_NO3", "gamma_G23", "gamma_NO3",
               "sigma_proxyObs"]
DIAGNOSTICS = ["R2_full", "bayesR2_full", "RMSE_full"]


def _rank(name: str) -> int:
    for i, p in enumerate(PARAM_ORDER):
        if name.startswith(p + "_") or name == p:
            return i
    return len(PARAM_ORDER)


def summarise(v) -> dict:
    a = np.asarray(v).ravel()
    q = np.percentile(a, [2.5, 16, 50, 84, 97.5])
    return dict(median=q[2], q16=q[1], q84=q[3], q025=q[0], q975=q[4],
                mean=a.mean(), sd=a.std(ddof=1))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", type=Path, default=None)
    ap.add_argument("--decimals", type=int, default=4)
    args = ap.parse_args(argv)

    from TEXAS.stan.io import load_posterior

    rows = []
    for label, case in CASES:
        try:
            d = load_posterior(case)
        except Exception as e:
            print(f"  skip {case}: {type(e).__name__}", file=sys.stderr)
            continue
        names = [v for v in d.data_vars if _rank(v) < len(PARAM_ORDER)]
        for n in sorted(names, key=lambda x: (_rank(x), x)):
            s = summarise(d[n])
            rows.append(dict(fit=label, case=case, quantity=n,
                             kind="noise" if n.startswith("sigma_") else "parameter",
                             **s))
        for n in DIAGNOSTICS:
            if n in d:
                rows.append(dict(fit=label, case=case, quantity=n,
                                 kind="diagnostic", **summarise(d[n])))

    df = pd.DataFrame(rows)
    if args.csv:
        df.to_csv(args.csv, index=False)
        print(f"wrote {args.csv}  ({len(df)} rows)", file=sys.stderr)

    dp = args.decimals
    print("| fit | quantity | kind | median | 68% CrI | 95% CrI |")
    print("|---|---|---|---:|---|---|")
    for _, r in df.iterrows():
        print(f"| {r.fit} | `{r.quantity}` | {r['kind']} | {r['median']:.{dp}f} "
              f"| {r.q16:.{dp}f}–{r.q84:.{dp}f} | {r.q025:.{dp}f}–{r.q975:.{dp}f} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
