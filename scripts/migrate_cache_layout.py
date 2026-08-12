#!/usr/bin/env python
"""
Migrate forward posteriors in the cache onto the current case layout.

    <case>/<case>.fwd.nc

Handles both sources: legacy flat files (``gen_logi_fixed_..._cren3.nc``) and
case directories written before 2026-08-11, when the leaf was a bare ``fwd.nc``
and the tokens were ``ri3`` / ``none`` instead of ``sri03`` / ``p0``.

**Dry-run by default.** Nothing moves until you pass ``--apply``. It copies
rather than moves, verifies each copy opens and carries the expected case, and
only then removes the source (with ``--prune``).

Inverse posteriors are deliberately NOT migrated. An invT model name records
the curve and constraint but not the training set or estimator, so the parent
case is not recoverable for any file lacking a ``fwd_case`` attr, and guessing
one would record a guess as provenance. See Phase 5D in RESUME.md.

    python scripts/migrate_cache_layout.py                 # show the plan
    python scripts/migrate_cache_layout.py --apply         # copy into place
    python scripts/migrate_cache_layout.py --apply --prune # and remove sources
"""
from __future__ import annotations

import argparse
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import xarray as xr

from TEXAS.utils.naming import case_from_attrs, fwd_leaf_candidates, fwd_relpath
from TEXAS.utils.paths import POSTERIOR_CACHE_DIR


def discover(cache: Path) -> list[Path]:
    """Every forward posterior in *cache*, under either layout."""
    found = sorted(cache.glob("*.nc"))
    for d in sorted(p for p in cache.iterdir() if p.is_dir()):
        for leaf in fwd_leaf_candidates(d.name):
            if (d / leaf).exists():
                found.append(d / leaf)
                break
    return found


def plan(cache: Path) -> tuple[list[tuple[Path, Path]], dict[str, list[Path]]]:
    """Return (moves, collisions). A move whose source is already correct is skipped."""
    moves: list[tuple[Path, Path]] = []
    by_dest: dict[str, list[Path]] = defaultdict(list)

    for src in discover(cache):
        try:
            with xr.open_dataset(src) as ds:
                attrs = dict(ds.attrs)
        except Exception as exc:
            print(f"  !! unreadable, skipped: {src.name} ({exc})")
            continue
        try:
            case = case_from_attrs(attrs)
        except Exception as exc:
            print(f"  !! no case id, skipped: {src.name} ({exc})")
            continue

        dest = cache / fwd_relpath(case)
        by_dest[str(case)].append(src)
        if src.resolve() != dest.resolve():
            moves.append((src, dest))

    collisions = {c: v for c, v in by_dest.items() if len(v) > 1}
    return moves, collisions


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", type=Path, default=POSTERIOR_CACHE_DIR)
    ap.add_argument("--apply", action="store_true", help="actually copy files")
    ap.add_argument("--prune", action="store_true",
                    help="with --apply, remove each source after its copy verifies")
    args = ap.parse_args()

    cache = args.cache
    if not cache.is_dir():
        print(f"No such cache directory: {cache}")
        return 2

    print(f"Cache: {cache}\n")
    moves, collisions = plan(cache)

    if collisions:
        print("REFUSING TO MIGRATE -- these case ids are claimed by more than one file.\n"
              "Migrating would overwrite one posterior with another. This is Phase 5C in\n"
              "RESUME.md: case_from_attrs() cannot recover filename_suffix, so refits\n"
              "collapse onto run .001. Fix that first, or give the refits distinct runs.\n")
        for case, srcs in sorted(collisions.items()):
            print(f"  {case}")
            for s in srcs:
                print(f"      {s.relative_to(cache)}")
        return 1

    if not moves:
        print("Nothing to do -- every forward posterior is already on the case layout.")
        return 0

    print(f"{len(moves)} file(s) to migrate:\n")
    for src, dest in moves:
        print(f"  {src.relative_to(cache)}\n    -> {dest.relative_to(cache)}")

    if not args.apply:
        print("\nDry run. Re-run with --apply to copy these into place.")
        return 0

    print()
    for src, dest in moves:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        try:
            with xr.open_dataset(dest) as ds:
                assert str(case_from_attrs(dict(ds.attrs))) == dest.parent.name
        except Exception as exc:
            dest.unlink(missing_ok=True)
            print(f"  FAILED to verify {dest.name}, copy removed: {exc}")
            return 1
        print(f"  ok  {dest.relative_to(cache)}")
        if args.prune:
            src.unlink()
            if src.parent != cache and not any(src.parent.iterdir()):
                src.parent.rmdir()
            print(f"      pruned {src.relative_to(cache)}")

    print(f"\nMigrated {len(moves)} file(s).")
    if not args.prune:
        print("Sources kept. Re-run with --prune once you have checked the results.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
