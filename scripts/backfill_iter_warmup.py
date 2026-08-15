#!/usr/bin/env python
"""Backfill ``iter_warmup`` onto posteriors that were written before it was recorded.

``num_draws_sampling`` reaches the ``.nc`` via arviz, but the warm-up length never
did, and **it is not recoverable from the file**. Nothing in the draws, the
dimensions, or the diagnostics distinguishes 300 warm-up iterations from 1,000.

So this script does not recover the value — it *asserts* one, and it will only do
so where there is external evidence for the specific file. The evidence is the
manifests that ``scripts/run_manuscript_refits.py`` writes, which record
``iter_warmup`` alongside the exact output ``path`` of every run it completed.

**Why a blanket stamp would be wrong.** The cache holds posteriors from more than
one budget: ``run_manuscript_refits.py`` uses 400 warm-up iterations for forward
fits and 500 for inverse ones, while ``SI_code02_t0shift_TEXAS_analysis.ipynb``
uses 300, and anything sampled without an explicit argument got CmdStan's default
of 1,000. Stamping one number across the cache would record a fabrication as
provenance on the files that came from somewhere else. Files with no manifest row
are therefore left alone, permanently — an absent attr is honest, a wrong one is
not.

Every written attr is paired with ``iter_warmup_source`` naming the manifest it
came from, so a later reader can tell an asserted value from a measured one.

    python scripts/backfill_iter_warmup.py            # dry run: print the plan
    python scripts/backfill_iter_warmup.py --apply    # write, verifying each file
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import xarray as xr

REPO = Path(__file__).resolve().parents[1]
REFIT_DIR = REPO / "data/revision1/groupA/manuscript_refit"

# Manifests carrying BOTH iter_warmup and the output path. The coretop_maps_*
# manifests record a warm-up but no path, so their rows cannot be tied to a file
# and are deliberately excluded.
MANIFESTS = ("manifest.csv", "single_predictor_manifest.csv")


def collect_claims() -> dict[Path, tuple[int, int | None, str]]:
    """path -> (iter_warmup, iter_sampling, provenance). Later manifests lose."""
    claims: dict[Path, tuple[int, int | None, str]] = {}
    for name in MANIFESTS:
        f = REFIT_DIR / name
        if not f.exists():
            print(f"  ! missing manifest, skipped: {f}")
            continue
        df = pd.read_csv(f)
        if not {"iter_warmup", "path"} <= set(df.columns):
            print(f"  ! {name} lacks iter_warmup/path, skipped")
            continue
        for _, r in df.iterrows():
            if str(r.get("status", "ok")) != "ok":
                continue
            if pd.isna(r["path"]) or pd.isna(r["iter_warmup"]):
                continue
            samp = r.get("iter_sampling")
            claims.setdefault(
                Path(str(r["path"])),
                (int(r["iter_warmup"]),
                 None if pd.isna(samp) else int(samp),
                 name),
            )
    return claims


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="write the attrs (default is a dry run)")
    args = ap.parse_args()

    claims = collect_claims()
    print(f"{len(claims)} manifest rows with a usable path\n")

    todo, skipped = [], []
    for path, (warmup, sampling, src) in sorted(claims.items()):
        if not path.exists():
            skipped.append((path, "file not on disk")); continue
        try:
            with xr.open_dataset(path) as ds:
                attrs = dict(ds.attrs)
        except Exception as e:                                  # noqa: BLE001
            skipped.append((path, f"unreadable: {type(e).__name__}")); continue

        if "iter_warmup" in attrs:
            skipped.append((path, f"already stamped ({attrs['iter_warmup']})")); continue

        # Consistency guard: if the file's sampling length disagrees with the
        # manifest row, the row is not describing this file and its warm-up
        # cannot be trusted for it either.
        got = attrs.get("num_draws_sampling")
        if sampling is not None and got is not None and int(got) != sampling:
            skipped.append((path, f"sampling mismatch: file {got} vs manifest {sampling}"))
            continue

        todo.append((path, warmup, src))

    for path, warmup, src in todo:
        print(f"  stamp iter_warmup={warmup:<5} {path.name}   [{src}]")
    if skipped:
        print(f"\n  {len(skipped)} skipped:")
        for path, why in skipped[:20]:
            print(f"    - {path.name}: {why}")
        if len(skipped) > 20:
            print(f"    ... and {len(skipped) - 20} more")

    if not args.apply:
        print(f"\nDRY RUN — {len(todo)} file(s) would be modified. Re-run with --apply.")
        return 0
    if not todo:
        print("\nNothing to do.")
        return 0

    print(f"\nWriting {len(todo)} file(s)...")
    failed = 0
    for path, warmup, src in todo:
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            with xr.open_dataset(path) as ds:
                ds.load()                      # detach before overwriting the source
                ds.attrs["iter_warmup"] = int(warmup)
                ds.attrs["iter_warmup_source"] = (
                    f"asserted from {src}; not recoverable from the file itself"
                )
                # Reuse each variable's existing encoding so compression survives.
                enc = {v: {k: val for k, val in ds[v].encoding.items()
                           if k in ("zlib", "complevel", "dtype", "_FillValue", "chunksizes")}
                       for v in ds.data_vars}
                ds.to_netcdf(tmp, encoding=enc)
            with xr.open_dataset(tmp) as chk:
                assert int(chk.attrs["iter_warmup"]) == int(warmup)
                assert len(chk.data_vars) == len(xr.open_dataset(path).data_vars)
            os.replace(tmp, path)
            print(f"  ok  {path.name}")
        except Exception as e:                                  # noqa: BLE001
            failed += 1
            tmp.unlink(missing_ok=True)
            print(f"  FAILED {path.name}: {type(e).__name__}: {e}")

    print(f"\n{len(todo) - failed} written, {failed} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
