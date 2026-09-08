#!/usr/bin/env python
"""Move kriged-grid caches into TEXAS_kriged_grids_cache/ and drop the dead ones.

Until 2026-09-07 ``plot_residual_maps`` wrote its ``.npz`` grids straight into
the cache root, next to the two posterior directories. This moves the live
grids into their own folder and deletes three superseded sets:

* ``kriged_grids_1.0deg_*`` -- normally the same grid as ``1deg`` under the
  old unformatted resolution token (the f-string had no ``:g``), so it is
  deleted as a duplicate *only when a ``1deg`` counterpart actually exists*
  (in the cache root or already in the destination). A machine whose grids
  were written through the default ``krige_res=1.0`` rather than an explicit
  ``1`` has no such counterpart -- there deleting it would destroy the only
  copy, so instead it is **renamed into the new folder under the canonical
  ``1deg`` name**, and the plan says so.
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
# ``1.0deg`` files are handled separately below (deleted only if a ``1deg``
# counterpart exists; otherwise renamed in as the only copy) -- not a flat
# "always superseded" prefix.
ORPHAN_PREFIX = "kriged_grids_1.0deg_"
SUPERSEDED_PREFIXES = (
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


def build_plan(root: Path, dest_dir: Path) -> dict:
    """Classify every ``.npz``/stray under *root* into what the migration does.

    Returns a dict with:
      - ``moves``          : [(src, dest)] -- live ``1deg`` grids to relocate
      - ``orphan_renames``  : [(src, dest)] -- ``1.0deg`` grids with no ``1deg``
        counterpart anywhere (root or destination); the only copy of that
        grid, so they are renamed into *dest_dir* under the canonical
        ``1deg`` name instead of being deleted.
      - ``doomed_files``   : [Path] -- files to delete (superseded duplicates
        + strays), including any ``1.0deg`` file that DOES have a ``1deg``
        counterpart.
      - ``doomed_dirs``    : [Path] -- stray directories to delete.

    Pure classification -- nothing on disk is touched.
    """
    moves = [(f, dest_dir / f.name)
             for f in sorted(root.glob(f"{LIVE_PREFIX}*.npz")) if f.is_file()]

    # 1.0deg files: delete only when a 1deg counterpart genuinely exists
    # (about to be moved from root, or already sitting in dest_dir); a
    # machine whose grids were written through the default krige_res=1.0
    # rather than an explicit 1 has no such counterpart, so that file is the
    # *only* copy of the grid and must be preserved, not deleted.
    orphan_renames: list[tuple[Path, Path]] = []
    doomed_1p0_files: list[Path] = []
    for f in sorted(root.glob(f"{ORPHAN_PREFIX}*.npz")):
        if not f.is_file():
            continue
        sibling_name = LIVE_PREFIX + f.name[len(ORPHAN_PREFIX):]
        has_counterpart = (root / sibling_name).exists() or (dest_dir / sibling_name).exists()
        if has_counterpart:
            doomed_1p0_files.append(f)
        else:
            orphan_renames.append((f, dest_dir / sibling_name))

    doomed_files = doomed_1p0_files + [
        f
        for prefix in SUPERSEDED_PREFIXES
        for f in sorted(root.glob(f"{prefix}*.npz")) if f.is_file()
    ]
    doomed_files += [root / n for n in STRAY_FILES if (root / n).is_file()]
    doomed_dirs = [root / n for n in STRAY_DIRS if (root / n).is_dir()]

    return {
        "moves": moves,
        "orphan_renames": orphan_renames,
        "doomed_files": doomed_files,
        "doomed_dirs": doomed_dirs,
    }


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

    plan = build_plan(root, dest_dir)
    moves = plan["moves"]
    orphan_renames = plan["orphan_renames"]
    doomed_files = plan["doomed_files"]
    doomed_dirs = plan["doomed_dirs"]

    clashes = [(a, b) for a, b in moves + orphan_renames if b.exists()]
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

    if orphan_renames:
        rename_bytes = sum(a.stat().st_size for a, _ in orphan_renames)
        print(f"\nRENAME -- no 1deg counterpart, this is the only copy "
              f"({len(orphan_renames)} file(s), {_mb(rename_bytes)}):")
        for a, b in orphan_renames:
            print(f"   {a.name}  ->  {b.name}")

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
    for a, b in moves + orphan_renames:
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
