#!/usr/bin/env python
"""Move kriged-grid caches into TEXAS_kriged_grids_cache/ and drop the dead ones.

Until 2026-09-07 ``plot_residual_maps`` wrote its ``.npz`` grids straight into
the cache root, next to the two posterior directories. This moves the live
grids into their own folder and deletes four superseded sets:

* ``kriged_grids_1.0deg_*`` -- the same grid as ``1deg`` under the old
  unformatted resolution token (the f-string had no ``:g``).
* ``kriged_grids_2.5deg_*`` -- the 2.5 degree cells in SI_code02 are
  commented out.
* ``kriged_halo_*.npz`` -- the halo-only cache format, written by
  ``load_or_build_halo_cache``, which had no callers and has been removed.
* ``rebuttal_boundedT/`` and the bare ``data_list_extreme_example.pkl`` --
  strays. SI_code03 reads the *variant-suffixed* pickles from
  ``TEXAS_posterior_cache/``, never this root copy; it says so in its own
  comments. Files under ``TEXAS_posterior_cache/`` are never touched here.

Everything deleted is regenerable: pass ``recompute='auto'`` to
``plot_residual_maps`` and it re-kriges.

THIS IS PER-MACHINE. ``data/cache/**`` is gitignored, so it does not travel
with a clone -- run it on every box. See the "does not travel" table in
RESUME.md.

**Dry-run by default.** Nothing moves or deletes until you pass ``--apply``.
Moving is refused outright if a destination file already exists (never
silently overwritten). Deletion only happens after every moved file has been
re-opened at its destination and confirmed readable -- if a move or a
verification fails, the run stops there and nothing is deleted.

Usage
-----
    python scripts/migrate_kriged_cache.py                        # dry run
    python scripts/migrate_kriged_cache.py --apply                # move only
    python scripts/migrate_kriged_cache.py --apply --delete-superseded
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

LIVE_PREFIX = "kriged_grids_1deg_"
SUPERSEDED_PREFIXES = (
    "kriged_grids_1.0deg_",
    "kriged_grids_2.5deg_",
    "kriged_halo_",
)
STRAY_FILES = ("data_list_extreme_example.pkl",)
STRAY_DIRS = ("rebuttal_boundedT",)


def _mb(nbytes: int) -> str:
    return f"{nbytes / 1_000_000:.1f} MB"


def _verify_moved(dest: Path) -> None:
    """Raise if *dest* is not a readable .npz with at least one array."""
    import numpy as np
    with np.load(dest) as z:
        if not z.files:
            raise ValueError(f"{dest} opened but contains no arrays")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--apply", action="store_true",
                    help="actually move the live grids")
    ap.add_argument("--delete-superseded", action="store_true",
                    help="also delete the superseded grids, halo caches and strays "
                         "(only after the move is verified)")
    ap.add_argument("--cache", type=Path, default=None,
                    help="cache root override (default: TEXAS's own)")
    args = ap.parse_args()

    from TEXAS.utils import paths

    root = args.cache if args.cache else paths.CACHE_ROOT
    dest_dir = (args.cache / "TEXAS_kriged_grids_cache") if args.cache \
        else paths.KRIGED_CACHE_DIR

    if not root.is_dir():
        print(f"No cache root at {root} -- nothing to do.")
        return 0

    moves = [(f, dest_dir / f.name)
             for f in sorted(root.glob(f"{LIVE_PREFIX}*.npz")) if f.is_file()]

    doomed_files = [f
                    for prefix in SUPERSEDED_PREFIXES
                    for f in sorted(root.glob(f"{prefix}*.npz")) if f.is_file()]
    doomed_files += [root / n for n in STRAY_FILES if (root / n).is_file()]
    doomed_dirs = [root / n for n in STRAY_DIRS if (root / n).is_dir()]

    clashes = [(a, b) for a, b in moves if b.exists()]
    if clashes:
        print("REFUSING: destination already exists for")
        for a, b in clashes:
            print(f"   {a.name}  ->  {b}")
        return 1

    print(f"cache root : {root}")
    print(f"destination: {dest_dir}\n")

    move_bytes = sum(a.stat().st_size for a, _ in moves)
    print(f"MOVE  ({len(moves)} file(s), {_mb(move_bytes)}):")
    for a, _ in moves:
        print(f"   {a.name}")

    del_bytes = sum(f.stat().st_size for f in doomed_files)
    print(f"\nDELETE ({len(doomed_files)} file(s) + {len(doomed_dirs)} dir(s), "
          f"{_mb(del_bytes)}):")
    for f in doomed_files:
        print(f"   {f.name}")
    for d in doomed_dirs:
        print(f"   {d.name}/")

    if not args.apply:
        print("\nDry run -- nothing changed. Re-run with --apply to move, "
              "and add --delete-superseded to delete.")
        return 0

    # --- Move -----------------------------------------------------------
    dest_dir.mkdir(parents=True, exist_ok=True)
    moved: list[Path] = []
    for a, b in moves:
        shutil.move(str(a), str(b))
        moved.append(b)
        print(f"moved   {a.name}")

    # --- Verify every moved file before anything is deleted -------------
    # A move that "succeeded" but landed a truncated/unreadable file must
    # never be followed by deleting the superseded originals -- that would
    # leave the loader with nothing to serve.
    for b in moved:
        try:
            _verify_moved(b)
        except Exception as exc:
            print(f"\nFAILED to verify {b.name} at its new location: {exc}")
            print("Stopping before any deletion. Nothing else was touched.")
            return 1
    if moved:
        print(f"verified {len(moved)} moved file(s) readable at the new location")

    if not args.delete_superseded:
        print("\nMoved. Nothing deleted -- read the DELETE list above, then "
              "re-run with --apply --delete-superseded.")
        return 0

    # --- Delete -----------------------------------------------------------
    for f in doomed_files:
        f.unlink()
        print(f"deleted {f.name}")
    for d in doomed_dirs:
        shutil.rmtree(d)
        print(f"deleted {d.name}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
