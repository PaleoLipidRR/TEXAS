#!/usr/bin/env python
"""
Backfill R2_thermal onto the two bundled EIV forward posteriors.

The previous commit made new EIV fits stamp `R2_thermal` into a posterior's
attrs (`constants.DIRECT_KEYS`, via `extract_and_update_metadata`). That does
nothing for the two posteriors already bundled inside the wheel
(`src/TEXAS/bundled_posteriors/*.fwd.nc`) -- they were sampled before that
change existed, and they are where most users actually meet this project.

The values are not a guess: they are recorded in a tracked file,
`data/revision1/groupA/manuscript_refit/manifest.csv`, in the `bnd` (T0-shift,
the `GHEB` compset the bundled files carry) rows:

    bnd, SST,      1513, 0.74558372475
    bnd, thermoT,  1513, 0.7571108695000001

This script reads those two values out of the manifest itself -- it does not
hardcode them -- so a stale docstring here can never drift from the source of
truth.

Same method as `scripts/normalize_posterior_attrs.py`: edit through netCDF4 in
append mode, so the draws are never rewritten. Dry-run by default; refuses to
touch a file that already carries `R2_thermal` (backfill is a one-time op, not
an overwrite tool).

Usage
-----
    python scripts/backfill_r2_thermal.py            # dry run
    python scripts/backfill_r2_thermal.py --apply
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import netCDF4

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "data/revision1/groupA/manuscript_refit/manifest.csv"
BUNDLED_DIR = REPO_ROOT / "src/TEXAS/bundled_posteriors"

# (bundled filename, manifest temptype) -- both are the `bnd` variant, the
# T0-shift / GHEB compset the bundled files are.
TARGETS = [
    ("tx.GHEB.sst.sri03.G23-N1p0.fwd.nc", "SST"),
    ("tx.GHEB.thm.sri03.G23-N1p0.fwd.nc", "thermoT"),
]


def _r2_from_manifest(temptype: str) -> float:
    with open(MANIFEST, newline="") as fh:
        rows = [r for r in csv.DictReader(fh)
                if r["variant"] == "bnd" and r["temptype"] == temptype
                and r.get("r2_thermal")]
    if not rows:
        raise ValueError(f"no bnd/{temptype} row with r2_thermal in {MANIFEST}")
    values = {row["r2_thermal"] for row in rows}
    if len(values) > 1:
        raise ValueError(f"bnd/{temptype} rows disagree on r2_thermal: {values}")
    return float(values.pop())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write the attribute (default: dry run)")
    args = ap.parse_args()

    touched = 0
    for fname, temptype in TARGETS:
        path = BUNDLED_DIR / fname
        if not path.is_file():
            print(f"  skip {fname}: not found")
            continue

        r2 = _r2_from_manifest(temptype)

        with netCDF4.Dataset(path) as nc:
            existing = "R2_thermal" in nc.ncattrs()

        if existing:
            print(f"  skip {fname}: R2_thermal already present, refusing to overwrite")
            continue

        touched += 1
        print(f"{fname}")
        print(f"    - R2_thermal -> {r2!r}")
        if args.apply:
            with netCDF4.Dataset(path, "a") as nc:
                nc.setncattr("R2_thermal", float(r2))

    verb = "updated" if args.apply else "would change"
    print(f"\n{touched} of {len(TARGETS)} file(s) {verb}."
          + ("" if args.apply else "  Re-run with --apply."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
