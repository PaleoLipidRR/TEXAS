#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate the browser walkthrough -> docs/_static/gdgt-to-temperature.html.

The page builds one reconstruction step by step, live in the reader's browser,
from the published calibration's own draws. The prose, styling and JavaScript
live in ``gdgt_to_temperature_template.html``; this script fills its data slot.

    python docs/_scripts/build_gdgt_to_temperature.py                # from the snapshot's TEXAS runs
    python docs/_scripts/build_gdgt_to_temperature.py --refresh-runs # re-run the examples (needs CmdStan)

**What is committed.** ``docs/_static/gdgt-to-temperature.html`` and
``docs/_static/gdgt-to-temperature.data.json``. The calibration draws, the Stan
source and the sampler defaults are re-read from the installed package at every
build, so they cannot drift. The ``stan`` percentiles of each example are real
``predict_T_from_proxyObs`` output and need CmdStan, so they come from the
snapshot unless ``--refresh-runs`` is passed. If TEXAS or its bundled posterior
cannot be read, the script leaves the committed page alone and exits 0, so a
docs deploy cannot blank it.
"""
from __future__ import annotations

import argparse
import inspect
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "gdgt_to_temperature_template.html"
OUT = HERE.parent / "_static" / "gdgt-to-temperature.html"
SNAPSHOT = HERE.parent / "_static" / "gdgt-to-temperature.data.json"

POSTERIOR = "tx.GHEB.sst.sri03.G23-N1p0"
STAN_FILE = "invT_gen_logi_fixed_multiv_marginal_unconstrained_t0shift.stan"
# Evaluation axis: wide enough that no posterior reachable from the page's inputs
# meets an edge, because the shipped model puts no bound on temperature.
T_AXIS = [-100.0, 120.0, 4401]
# Manuscript Fig. 7d: +/-0.03 Scaled RI becomes more than +/-5 degC outside these.
THR_LO, THR_HI = 7.1, 40.9
QUANTILES = ("p5", "p16", "p50", "p84", "p95")

# One sample from each of the manuscript's case-study sites: the sample nearest
# the site's median Scaled RI (Co1010: nearest 0.44, because the manuscript's
# argument concerns its samples below 0.45). Priors are the manuscript's. NO3 is
# the site's modern CMEMS value where the case study uses it, and 10 umol/L (the
# documented way to switch the correction off) for ODP 1259 and Co1010.
EXAMPLES = [
    dict(role="steep part", record="IODP U1482", age_label="477 ka", source="NW Australian margin, Section 8.2",
         ri=0.6628, g23=5.985, no3=2.727, prior_mu=20.0, prior_sigma=10.0, tex86=0.670159),
    dict(role="low nitrate", record="DSDP 591", age_label="83 ka", source="Tasman Sea, Section 8.1",
         ri=0.6267, g23=6.795, no3=0.576, prior_mu=20.0, prior_sigma=10.0, tex86=0.569400),
    dict(role="cold end", record="Co1010", age_label="10.7 ka", source="Prydz Bay, Section 8.4",
         ri=0.4363, g23=0.980, no3=10.0, prior_mu=5.0, prior_sigma=10.0, tex86=0.410000),
    dict(role="warm end", record="ODP 1259", age_label="91.9 Ma", source="Demerara Rise, Section 8.4",
         ri=0.9368, g23=1.804, no3=10.0, prior_mu=40.0, prior_sigma=10.0, tex86=0.935151),
]


def _rounded(values, n=5):
    return [round(float(v), n) for v in values]


def run_examples() -> dict:
    """Run the real package on the examples, at its defaults. Needs CmdStan."""
    import numpy as np
    from TEXAS import predict_T_from_proxyObs

    out = predict_T_from_proxyObs(
        proxyObs=[e["ri"] for e in EXAMPLES],
        prior_mu_t=np.array([e["prior_mu"] for e in EXAMPLES]),
        prior_sigma_t=10.0,
        fwd_posterior=POSTERIOR,
        gdgt23ratio=np.array([e["g23"] for e in EXAMPLES]),
        no3=np.array([e["no3"] for e in EXAMPLES]),
        tex86=np.array([e["tex86"] for e in EXAMPLES]),
    )
    flags = out["flags"]
    return {
        e["record"]: dict(
            stan=_rounded([out[q][i] for q in QUANTILES], 3),
            outside_domain=bool(flags["outside_domain"].iloc[i]),
            flags={c: bool(flags[c].iloc[i]) for c in (
                "proxy_below_floor", "proxy_above_ceiling", "proxy_extrapolated",
                "predictor_extrapolated", "no3_correction_inactive", "prior_dominated")},
            width_ratio=round(float(flags["posterior_prior_width_ratio"].iloc[i]), 4),
        )
        for i, e in enumerate(EXAMPLES)
    }


def assemble(runs: dict) -> dict:
    """Everything the page needs, read from the installed package."""
    import numpy as np
    import TEXAS
    import xarray as xr
    from TEXAS.data.builder import build_invT_inputData
    from TEXAS.quality import DEFAULT_PRIOR_DOMINATED_RATIO

    # The bundled file directly, not load_posterior(): a machine's cache can hold
    # a different fit under the same case id, and this page must not depend on it.
    package = Path(TEXAS.__file__).parent
    ds = xr.load_dataset(package / "bundled_posteriors" / f"{POSTERIOR}.fwd.nc")
    # The exact M draws a default reconstruction marginalizes over.
    data, _ = build_invT_inputData(
        [0.6], 20.0, 10.0, fwd_posterior=ds,
        predictors={"gdgt23ratio": np.array([1.0]), "no3": np.array([10.0])},
    )
    ens = dict(t0=data["t0"], k=data["k"], b=data["b"], v=data["v"], gG=data["gamma_G23"],
               gN=data["gamma_NO3"], sig=data["sigma_proxyObs"])
    a = ds.attrs
    sig = inspect.signature(TEXAS.predict_T_from_proxyObs).parameters
    stan_src = (package / "stan_models" / STAN_FILE).read_text(encoding="utf-8")
    examples = [{k: v for k, v in e.items() if k != "tex86"} | {
        "stan": runs[e["record"]]["stan"], "outside_domain": runs[e["record"]]["outside_domain"],
    } for e in EXAMPLES]
    return dict(
        meta=dict(posterior=POSTERIOR, M=int(data["M"]), cutoff=float(a["no3_cutoff"]), T=T_AXIS,
                  thr_lo=THR_LO, thr_hi=THR_HI,
                  prior_dominated_ratio=DEFAULT_PRIOR_DOMINATED_RATIO,
                  ranges=dict(proxy=[float(a["proxyObs_crtp_min"]), float(a["proxyObs_crtp_max"])],
                              g23=[float(a["gdgt23ratio_crtp_min"]), float(a["gdgt23ratio_crtp_max"])],
                              no3=[float(a["no3_crtp_min"]), float(a["no3_crtp_max"])])),
        ens={k: _rounded(v) for k, v in ens.items()},
        plugin=dict(med={k: round(float(np.median(v)), 4) for k, v in ens.items() if k != "sig"}),
        examples=examples,
        runs=runs,
        stan=dict(file=STAN_FILE, src=stan_src, chains=int(sig["chains"].default),
                  warmup=int(sig["iter_warmup"].default), sampling=int(sig["iter_sampling"].default),
                  seed=int(sig["seed"].default), adapt_delta=0.8, max_treedepth=10),  # CmdStan's defaults, which TEXAS keeps
    )


def render(payload: dict) -> str:
    """Fill the template's data slot."""
    text = json.dumps(payload, separators=(",", ":"), allow_nan=False, ensure_ascii=False)
    if "</script" in text:
        raise SystemExit("ABORT: the data contains '</script', which would end the data block early")
    return TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", text)


def main() -> int:
    """Rebuild the page and its snapshot, or keep the committed pair if TEXAS is unreadable."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh-runs", action="store_true", help="re-run the examples through TEXAS (needs CmdStan)")
    args = ap.parse_args()

    try:
        if args.refresh_runs:
            runs = run_examples()
        else:
            runs = json.loads(SNAPSHOT.read_text(encoding="utf-8"))["runs"]
        payload = assemble(runs)
    except (ImportError, OSError, KeyError, ValueError) as exc:
        if args.refresh_runs:
            raise
        print(f"build_gdgt_to_temperature: keeping the committed page ({type(exc).__name__}: {exc})")
        return 0
    OUT.write_text(render(payload), encoding="utf-8")
    SNAPSHOT.write_text(json.dumps(payload, indent=0, allow_nan=False, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.name} ({OUT.stat().st_size // 1024} KB), M = {payload['meta']['M']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
