#!/usr/bin/env python
"""MCMC diagnostics for every calibration the manuscript uses.

Reviewer #2: "Model implementation: Please report MCMC diagnostics more
explicitly, including Rhat, effective sample sizes, and any relevant Stan
diagnostics."

Everything below is already stamped onto each posterior by
``diagnostics.summarize_sampler_diagnostics`` at sampling time. This reads the
cached .nc files and tabulates it; nothing is refitted and nothing is recomputed,
so the table cannot drift from what was actually sampled.

Gates applied, and why these:

    R-hat        <= 1.01   the standard Vehtari et al. (2021) threshold
    ESS bulk     >= 400    100 per chain at 4 chains, the usual working minimum
    divergences  == 0      any divergence invalidates the geometry locally
    treedepth    == 0 hits saturating treedepth means the sampler ran out of
                           steps, not that it converged

    python scripts/build_diagnostics_table.py
    python scripts/build_diagnostics_table.py --csv out.csv --all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

MANUSCRIPT_CASES = [
    ("culture + mesocosm (top layer)", "tx.GCDU.cul.sri03.p0"),
    ("coretop thermal-only, SST", "tx.GHPU.sst.sri03.p0"),
    ("coretop thermal-only, thermoT", "tx.GHPU.thm.sri03.p0"),
    ("coretop additive EIV, SST", "tx.GHEA.sst.sri03.G23-N10"),
    ("coretop additive EIV, thermoT", "tx.GHEA.thm.sri03.G23-N10"),
    ("coretop bounded-T, SST", "tx.GHEB.sst.sri03.G23-N10"),
    ("coretop bounded-T, thermoT", "tx.GHEB.thm.sri03.G23-N10"),
]

RHAT_GATE, ESS_GATE = 1.01, 400.0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", type=Path, default=None)
    ap.add_argument("--all", action="store_true",
                    help="every forward posterior in the cache, not just the "
                         "manuscript's seven")
    args = ap.parse_args(argv)

    from TEXAS.stan.io import load_posterior
    from TEXAS.utils.paths import POSTERIOR_CACHE_DIR

    if args.all:
        cases = sorted({p.name.split(".fwd")[0]
                        for p in Path(POSTERIOR_CACHE_DIR).glob("tx.*.fwd.nc")})
        cases = [(c, c) for c in cases]
    else:
        cases = MANUSCRIPT_CASES

    rows = []
    for label, case in cases:
        try:
            d = load_posterior(case)
        except Exception as e:
            print(f"  skip {case}: {type(e).__name__}", file=sys.stderr)
            continue
        a = d.attrs
        rhat = a.get("stan_diag_max_rhat")
        ess = a.get("stan_diag_min_ess_bulk")
        div = a.get("stan_diag_n_divergent")
        td = a.get("stan_diag_n_max_treedepth")
        rows.append(dict(
            fit=label, case=case,
            # chains is not an attr; it is the posterior's own dimension, which
            # is the honest source anyway -- it cannot disagree with the draws.
            chains=int(d.sizes.get("chain", 0)) or None,
            sampling=a.get("num_draws_sampling", int(d.sizes.get("draw", 0))),
            total_draws=int(d.sizes.get("chain", 0)) * int(d.sizes.get("draw", 0)),
            max_rhat=rhat, worst_param=a.get("stan_diag_worst_rhat_param", ""),
            min_ess_bulk=ess, divergences=div, max_treedepth_hits=td,
            min_ebfmi=a.get("stan_diag_min_ebfmi"),
            passes=(rhat is not None and rhat <= RHAT_GATE
                    and ess is not None and ess >= ESS_GATE
                    and (div in (0, None)) and (td in (0, None))),
            reported_status=a.get("stan_diag_overall_status", ""),
        ))

    df = pd.DataFrame(rows)
    if args.csv:
        df.to_csv(args.csv, index=False)
        print(f"wrote {args.csv}  ({len(df)} rows)", file=sys.stderr)

    print("| fit | chains x draws | max R-hat | min ESS(bulk) | divergences | "
          "treedepth hits | passes all gates |")
    print("|---|---|---:|---:|---:|---:|---|")
    for _, r in df.iterrows():
        rh = "—" if pd.isna(r.max_rhat) else f"{r.max_rhat:.5f}"
        es = "—" if pd.isna(r.min_ess_bulk) else f"{r.min_ess_bulk:.0f}"
        print(f"| {r.fit} | {r.chains} x {r.sampling} | {rh} | {es} "
              f"| {r.divergences} | {r.max_treedepth_hits} "
              f"| {'yes' if r.passes else 'NO'} |")

    bad = df[~df.passes]
    if len(bad):
        print(f"\n{len(bad)} fit(s) miss a gate:")
        for _, r in bad.iterrows():
            print(f"  {r.case}: R-hat {r.max_rhat}, ESS {r.min_ess_bulk}, "
                  f"div {r.divergences}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
