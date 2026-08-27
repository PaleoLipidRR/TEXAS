#!/usr/bin/env python
"""
Build the calibration posteriors that ship inside the wheel.

TEXAS bundles the full multivariate T0-shift calibration so that
``predict_T_from_proxyObs`` works on a bare ``pip install texas-psm`` with no
network access. The archived posteriors cannot ship as-is: the EIV model
carries one latent (error-free) value per coretop site for each of its two
predictors, which is ~1500 x 4000 x 2 doubles and takes each file to ~80 MB.

None of that is read by the inverse model, which needs only the curve
parameters, the two gamma coefficients and the noise scale. Dropping the
per-site latents takes a file from 81 MB to 0.37 MB with no loss of anything
the reconstruction path touches, which is what makes bundling possible at all.

The full files stay on Zenodo and remain the archival record; the bundled
subset is a convenience copy, and says so in its attrs.

Usage
-----
    python scripts/make_bundled_posteriors.py            # rebuild from the cache
    python scripts/make_bundled_posteriors.py --check    # verify, write nothing
"""

from __future__ import annotations

import argparse
import sys

import xarray as xr

from TEXAS.utils.paths import BUNDLED_POSTERIOR_DIR, POSTERIOR_CACHE_DIR
from TEXAS.stan.io import load_posterior

# The calibrations that travel with the package: the full multivariate
# (G23 + NO3) T0-shift model, for both calibration targets.
BUNDLED_CASES = [
    "tx.GHEB.sst.sri03.G23-N1p0",
    "tx.GHEB.thm.sri03.G23-N1p0",
]

# Latent variables of the EIV model. One value per coretop site per draw, used
# only while fitting; the inverse model never reads them.
_LATENT_PREFIX = "true_"

_NOTE = (
    "Bundled subset: the per-site EIV latent variables (true_*) were dropped "
    "to fit inside the wheel. Every parameter the forward and inverse models "
    "read is present and unmodified. The complete posterior, including the "
    "latents, is on Zenodo."
)


def _slim(ds: xr.Dataset) -> tuple[xr.Dataset, list[str]]:
    dropped = [v for v in ds.data_vars if v.startswith(_LATENT_PREFIX)]
    out = ds.drop_vars(dropped)
    out.attrs = dict(ds.attrs)
    out.attrs["bundled_subset"] = 1
    # Which package built the bundle. Not the same fact as `texas_version`,
    # which records what produced the draws -- posteriors sampled before that
    # attr existed simply do not carry it, and guessing one would be worse
    # than its absence.
    try:
        from TEXAS import __version__ as _v
        out.attrs["bundled_with"] = f"texas-psm {_v}"
    except Exception:
        pass
    out.attrs["bundled_dropped_vars"] = ", ".join(dropped) if dropped else "(none)"
    out.attrs["bundled_note"] = _NOTE
    return out, dropped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify the bundled files exist and load; write nothing")
    ap.add_argument("--cache", default=None,
                    help=f"source cache (default: {POSTERIOR_CACHE_DIR})")
    args = ap.parse_args()

    BUNDLED_POSTERIOR_DIR.mkdir(parents=True, exist_ok=True)

    if args.check:
        ok = True
        for case in BUNDLED_CASES:
            path = BUNDLED_POSTERIOR_DIR / f"{case}.fwd.nc"
            if not path.exists():
                print(f"MISSING  {path}")
                ok = False
                continue
            ds = xr.load_dataset(path)
            size = path.stat().st_size / 1e6
            print(f"ok  {case}  {size:.2f} MB  {len(ds.data_vars)} vars")
        return 0 if ok else 1

    for case in BUNDLED_CASES:
        full = load_posterior(case, cache_dir=args.cache)
        slim, dropped = _slim(full)
        dest = BUNDLED_POSTERIOR_DIR / f"{case}.fwd.nc"
        encoding = {v: {"zlib": True, "complevel": 5} for v in slim.data_vars}
        slim.to_netcdf(dest, encoding=encoding)
        print(
            f"{case}: dropped {len(dropped)} latent var(s) -> "
            f"{dest.stat().st_size / 1e6:.2f} MB  [{dest}]"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
