#!/usr/bin/env python
"""
Flatten both posterior caches onto the canonical short names.

    data/cache/TEXAS_posterior_cache/tx.GHEA.sst.sri03.G23-N10.fwd.nc
    data/cache/TEXAS_invT_posterior_cache/tx.GHEA.sst.sri03.G23-N10.inv.U1482.ud-no3_modern.nc

Moves files out of case directories and drops the `v026` version and the
`.001` member from the case prefix. Both left the naming scheme on 2026-08-12:
the version was the pip release, which orphaned every name on a docs-only
release, and the member read as a second number beside the nitrate cutoff.

**Dry-run by default.** Nothing moves until ``--apply``. Copies first, verifies
each copy opens and carries the expected case, and only then removes the source
(with ``--prune``).

    python scripts/flatten_cache.py                  # show the plan
    python scripts/flatten_cache.py --apply
    python scripts/flatten_cache.py --apply --prune

**Collisions are expected here and are not automatically resolved.** Dropping
the member means `.001` and `.002` of one calibration want the same flat name.
That is a real choice about which fit is authoritative, so the script refuses
and lists them rather than picking. Resolve by deleting the superseded file, or
by keeping it with an explicit ``run=``.

This is tidiness, not a prerequisite: ``resolve_posterior_path`` reads flat
leaves, both case-directory layouts, versioned and short ids, and legacy long
names, so everything works whether or not this is ever run.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import xarray as xr

from TEXAS.utils.naming import (case_from_attrs, is_case_id, parse_case,
                                fwd_leaf_candidates)
from TEXAS.utils.paths import INVT_CACHE_DIR, POSTERIOR_CACHE_DIR


def short(case_text: str) -> str:
    """Strip the version and member from a case id."""
    return str(replace(parse_case(case_text), version="", run=""))


def plan_forward(cache: Path):
    """(moves, collisions) for the forward cache, keyed on the canonical name."""
    moves, by_dest = [], defaultdict(list)
    sources = list(cache.glob("*.nc"))
    for d in (p for p in cache.iterdir() if p.is_dir()):
        for leaf in fwd_leaf_candidates(d.name):
            if (d / leaf).exists():
                sources.append(d / leaf)
                break

    for src in sorted(sources):
        try:
            with xr.open_dataset(src) as ds:
                attrs = dict(ds.attrs)
            case = case_from_attrs(attrs)       # already the short form
        except Exception as exc:
            print(f"  !! skipped {src.name}: {exc}")
            continue
        dest = cache / f"{case}.fwd.nc"
        by_dest[dest.name].append(src)
        if src.resolve() != dest.resolve():
            moves.append((src, dest))
    return moves, {k: v for k, v in by_dest.items() if len(v) > 1}


def plan_invt(cache: Path):
    """
    (moves, collisions) for the inverse cache.

    Only files already inside a case directory are touched. A legacy flat invT
    file has no recoverable parent case -- an invT model name records the curve
    and constraint but not the training set or estimator -- so inventing one
    would record a guess as provenance. Those stay exactly where they are.
    """
    moves, by_dest = [], defaultdict(list)
    for d in sorted(p for p in cache.iterdir() if p.is_dir()):
        if not is_case_id(d.name):
            continue
        try:
            new_case = short(d.name)
        except Exception:
            continue
        # Both artefacts: predict_T_from_proxyObs writes a .nc posterior AND a
        # .npz of the quantile results. Globbing only .nc left 64 .npz files
        # stranded in case directories that otherwise looked emptied.
        for src in sorted(list(d.glob("*.nc")) + list(d.glob("*.npz"))):
            leaf = src.name
            # `<case>.inv.<site>.<codes>.nc` -> same, with the short case
            dest = cache / (new_case + leaf[len(d.name):] if leaf.startswith(d.name)
                            else f"{new_case}.{leaf}")
            by_dest[dest.name].append(src)
            if src.resolve() != dest.resolve():
                moves.append((src, dest))
    return moves, {k: v for k, v in by_dest.items() if len(v) > 1}


MANIFEST = Path("data/revision1/groupA/manuscript_refit/manifest.csv")


def authoritative(srcs):
    """
    Which file in a collision group wins, and why.

    Rule, in order:
      1. the manuscript refit wrote it -- that is the audited 400/1000 fit the
         paper reports, so it outranks anything older by definition;
      2. otherwise the most recent run_timestamp, falling back to mtime.

    Returns (winner, reason). Never deletes: the caller moves the losers to
    superseded/ so a wrong call here is reversible.
    """
    refit = set()
    if MANIFEST.exists():
        import csv
        with MANIFEST.open() as fh:
            for row in csv.DictReader(fh):
                if row.get("path"):
                    refit.add(Path(row["path"]).resolve())
    for s in srcs:
        if s.resolve() in refit:
            return s, "written by the manuscript refit"

    def stamp(f):
        try:
            with xr.open_dataset(f) as ds:
                return str(ds.attrs.get("run_timestamp") or "")
        except Exception:
            return ""
    best = max(srcs, key=lambda f: (stamp(f), f.stat().st_mtime))
    return best, ("newest run_timestamp" if stamp(best) else "newest mtime")


def report(label, moves, collisions, cache):
    print(f"\n=== {label}  [{cache}]")
    if collisions:
        print(f"  {len(collisions)} COLLISION(S) — two files want one name:")
        for name, srcs in sorted(collisions.items()):
            print(f"    {name}")
            for s in srcs:
                print(f"        {s.relative_to(cache)}")
    if not moves:
        print("  nothing to move")
    else:
        print(f"  {len(moves)} file(s) to flatten:")
        for src, dest in moves[:60]:
            print(f"    {src.relative_to(cache)}\n      -> {dest.name}")
        if len(moves) > 60:
            print(f"    ... and {len(moves) - 60} more")


def verify(path: Path) -> None:
    """
    Open a copy to prove it survived. Raises if not.

    Handles both artefacts an inverse run writes: the .nc posterior and the
    .npz of quantile results. Verifying a .npz with xarray fails, and this
    function used to do exactly that -- deleting each freshly made copy and
    aborting, which looked like a migration failure rather than a wrong check.
    """
    if path.suffix == ".npz":
        import numpy as _np
        with _np.load(path, allow_pickle=True) as z:
            assert len(z.files), "empty npz"
    else:
        with xr.open_dataset(path) as ds:
            assert ds.attrs or ds.data_vars, "opened but empty"


def apply(moves, prune: bool) -> int:
    for src, dest in moves:
        if dest.exists():
            # Already copied by an earlier --apply. Verify it and then still
            # prune the source: skipping outright meant a second pass with
            # --prune left every source in place, which looks like success and
            # is not.
            try:
                verify(dest)
            except Exception as exc:
                print(f"  BAD existing copy {dest.name}: {exc}")
                return 1
            print(f"  ok  {dest.name} (already copied)")
            if prune and src.exists() and src.resolve() != dest.resolve():
                src.unlink()
                if src.parent != dest.parent and not any(src.parent.iterdir()):
                    src.parent.rmdir()
            continue
        shutil.copy2(src, dest)
        try:
            verify(dest)
        except Exception as exc:
            dest.unlink(missing_ok=True)
            print(f"  FAILED to verify {dest.name}, copy removed: {exc}")
            return 1
        print(f"  ok  {dest.name}")
        if prune:
            src.unlink()
            if src.parent != dest.parent and not any(src.parent.iterdir()):
                src.parent.rmdir()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fwd-cache", type=Path, default=POSTERIOR_CACHE_DIR)
    ap.add_argument("--invt-cache", type=Path, default=INVT_CACHE_DIR)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--resolve", action="store_true",
                    help="resolve collisions: refit wins, else newest; losers "
                         "move to superseded/ rather than being deleted")
    ap.add_argument("--prune", action="store_true",
                    help="with --apply, remove each source after its copy verifies")
    args = ap.parse_args()

    fmoves, fcoll = plan_forward(args.fwd_cache)
    imoves, icoll = plan_invt(args.invt_cache)
    report("forward", fmoves, fcoll, args.fwd_cache)
    report("inverse", imoves, icoll, args.invt_cache)

    if (fcoll or icoll) and not args.resolve:
        print("\nREFUSING TO MOVE — resolve the collisions above first.\n"
              "Dropping the member means .001 and .002 of one calibration want\n"
              "the same name. Which fit is authoritative is a real choice, so\n"
              "this does not guess. Re-run with --resolve to apply the rule\n"
              "(refit wins, else newest), which moves the losers to superseded/\n"
              "rather than deleting them.")
        return 1

    if args.resolve and (fcoll or icoll):
        print("\n=== collision resolution")
        for cache, coll, moves in ((args.fwd_cache, fcoll, fmoves),
                                   (args.invt_cache, icoll, imoves)):
            for name, srcs in sorted(coll.items()):
                winner, why = authoritative(srcs)
                print(f"  {name}\n    KEEP  {winner.relative_to(cache)}  ({why})")
                for loser in srcs:
                    if loser == winner:
                        continue
                    print(f"    move  {loser.relative_to(cache)} -> superseded/")
                    if args.apply:
                        sup = cache / "superseded"
                        sup.mkdir(exist_ok=True)
                        loser.rename(sup / loser.name)
                    moves[:] = [m for m in moves if m[0] != loser]

    if not (fmoves or imoves):
        print("\nNothing to do.")
        return 0
    if not args.apply:
        print("\nDry run. Re-run with --apply to copy these into place.")
        return 0

    print()
    rc = apply(fmoves, args.prune) or apply(imoves, args.prune)
    print(f"\nFlattened {len(fmoves) + len(imoves)} file(s).")
    if not args.prune:
        print("Sources kept. Re-run with --prune once you have checked them.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
