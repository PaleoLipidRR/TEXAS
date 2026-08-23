#!/usr/bin/env python
"""
Rename cached files onto the current nitrate token: `N10` -> `N1p0`.

The 2026-08-23 rename changed what TEXAS *writes*; it renamed nothing already
on disk, because every read path accepts both spellings. That leaves a cache
where the same calibration appears under two spellings depending on when it was
sampled, which is confusing to read even though it resolves. This closes that.

Covers both caches and every extension (an invT run writes `.nc` and `.npz`
siblings that must move together), and skips `superseded/`, which is an archive.

Safety
------
* dry-run by default; `--apply` to move
* refuses the whole run if any destination already exists
* `os.replace` within one directory, so a rename is atomic and cheap
* reversible: `--revert` maps N1p0 back to N10

Nothing depends on this having been run. `load_posterior` resolves either
spelling, in either direction, so a half-renamed cache still works.

Usage
-----
    python scripts/rename_cache_files.py                    # dry run, both caches
    python scripts/rename_cache_files.py --apply
    python scripts/rename_cache_files.py --apply --dir <one/cache>
    python scripts/rename_cache_files.py --apply --revert
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from TEXAS.utils.naming import swap_no3_token


def _dirs(explicit: str | None) -> list[Path]:
    if explicit:
        return [Path(explicit)]
    from TEXAS.utils.paths import INVT_CACHE_DIR, POSTERIOR_CACHE_DIR
    return [POSTERIOR_CACHE_DIR, INVT_CACHE_DIR]


_LEGACY = re.compile(r"(?<=[.\-])N\d{2}(?=[.\-]|$)")
_CURRENT = re.compile(r"(?<=[.\-])N\d+p\d+(?=[.\-]|$)")


def _wanted(name: str, revert: bool) -> str | None:
    """The new name, if this file should move.

    Direction is read from the spelling the file already carries, not from the
    swap's output -- site names in an invT leaf can contain letters that make
    inspecting the swapped string unreliable.
    """
    carries_legacy = bool(_LEGACY.search(name))
    carries_current = bool(_CURRENT.search(name))
    if not (carries_legacy or carries_current):
        return None
    if carries_legacy == revert:      # already in the spelling we want
        return None
    return swap_no3_token(name)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--revert", action="store_true", help="N1p0 -> N10")
    ap.add_argument("--dir", default=None)
    args = ap.parse_args()

    moves: list[tuple[Path, Path]] = []
    for d in _dirs(args.dir):
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            if not f.is_file():
                continue
            new = _wanted(f.name, args.revert)
            if new:
                moves.append((f, f.with_name(new)))

    clashes = [(a, b) for a, b in moves if b.exists()]
    if clashes:
        print("REFUSING: destination already exists for")
        for a, b in clashes:
            print(f"   {a.name}  ->  {b.name}")
        return 1

    for a, b in moves:
        print(f"{a.parent.name}/  {a.name}\n            -> {b.name}")
        if args.apply:
            os.replace(a, b)

    verb = "renamed" if args.apply else "would rename"
    print(f"\n{len(moves)} file(s) {verb}."
          + ("" if args.apply else "  Re-run with --apply."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
