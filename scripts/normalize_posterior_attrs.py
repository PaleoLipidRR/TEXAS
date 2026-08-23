#!/usr/bin/env python
"""
Bring cached posteriors' attrs up to the current spelling, in place.

Three things drifted as the project renamed its parts:

  stan_model_name   still says `..._eiv_boundedT` for posteriors sampled before
                    the 2026-08-15 rename. It is the same Stan program under
                    its old file name, so the current spelling `..._eiv_t0shift`
                    is not a rewrite of history -- it is the model's name.

  model             arviz echoes CmdStan's own config key: the same string as
                    stan_model_name with "_model" appended. Verified identical
                    in every cached posterior. Two attrs for one fact means one
                    of them can go stale, which is exactly what happened, so
                    only stan_model_name is kept.

  case_id           a stored copy of a *derived* value, recomputed from attrs
                    anyway. Refreshed so it uses the current predictor token
                    (`N1p0`, not the old cutoff-x10 `N10`).

  generated_by      says `culRI-Bayesian`, the project's name years before it
                    was TEXAS. Set to `texas-psm`, which is what a reader would
                    install.

  version           the literal "1.0.0" in every cached posterior -- the default
                    argument of extract_and_update_metadata(), never set by a
                    caller and never read. Dropped. `texas_version` is the real
                    one; it is NOT backfilled here, because which package
                    version produced an older file is not recoverable, and
                    absent is the honest answer.

`filename` is deliberately NOT touched. It records what the file was called
when it was written, which is what lets a date-stamped legacy request still
resolve; it is history, not identity.

Attributes are edited through netCDF4 in append mode, so the draws are never
rewritten: an 80 MB posterior is updated in milliseconds and its data cannot be
altered by this script.

Usage
-----
    python scripts/normalize_posterior_attrs.py                 # dry run
    python scripts/normalize_posterior_attrs.py --apply
    python scripts/normalize_posterior_attrs.py --apply --dir <some/other/cache>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import netCDF4

LEGACY_MODEL_TOKEN = ("boundedT", "t0shift")


def _targets(explicit: str | None) -> list[Path]:
    if explicit:
        return [Path(explicit)]
    from TEXAS.utils.paths import BUNDLED_POSTERIOR_DIR, POSTERIOR_CACHE_DIR
    return [POSTERIOR_CACHE_DIR, BUNDLED_POSTERIOR_DIR]


def _planned_changes(path: Path) -> dict:
    """What this file needs, without opening it for writing."""
    changes: dict[str, object] = {}
    with netCDF4.Dataset(path) as nc:
        attrs = {k: nc.getncattr(k) for k in nc.ncattrs()}

    name = str(attrs.get("stan_model_name", ""))
    old, new = LEGACY_MODEL_TOKEN
    if old in name:
        changes["stan_model_name"] = name.replace(old, new)

    if str(attrs.get("generated_by", "")) == "culRI-Bayesian":
        changes["generated_by"] = "texas-psm"

    stale = [k for k in ("model",) if k in attrs]
    # Only the fossil default. A version someone actually set is left alone.
    if str(attrs.get("version", "")) == "1.0.0":
        stale.append("version")
    if stale:
        changes["__delete__"] = stale

    # case_id is a FORWARD calibration identity. Deriving one from an inverse
    # posterior's attrs "succeeds" -- case_from_attrs happily encodes the invT
    # model name into a compset -- and produces a calibration that never
    # existed (tx.GTDA...). An invT run is a member of its parent case, which
    # is recorded in `fwd_case` or nowhere; it never has a case of its own.
    is_inverse = str(attrs.get("stan_model_name", "")).startswith("invT")
    try:
        if is_inverse:
            raise RuntimeError("inverse posterior: no case id of its own")
        from TEXAS.utils.naming import case_from_attrs
        merged = dict(attrs)
        merged.update({k: v for k, v in changes.items() if k != "__delete__"})
        fresh = str(case_from_attrs(merged))
        if fresh and str(attrs.get("case_id", "")) != fresh:
            changes["case_id"] = fresh
    except Exception:
        pass

    return changes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    ap.add_argument("--dir", default=None, help="one directory to process")
    args = ap.parse_args()

    files: list[Path] = []
    for d in _targets(args.dir):
        if not d.is_dir():
            continue
        # `superseded/` is an archive of what earlier runs produced. An archive
        # that gets edited is no longer an archive, so it is left exactly as it
        # is -- nothing reads it, and its whole value is being untouched.
        files += [f for f in sorted(d.glob("*.nc")) + sorted(d.glob("*/*.nc"))
                  if f.parent.name != "superseded"]

    touched = 0
    for f in files:
        try:
            changes = _planned_changes(f)
        except Exception as exc:
            print(f"  skip {f.name}: {exc}")
            continue
        if not changes:
            continue
        touched += 1
        print(f"{f.name}")
        for key, value in changes.items():
            if key == "__delete__":
                print(f"    - drop  {', '.join(value)}")
            else:
                print(f"    - {key} -> {value}")
        if args.apply:
            with netCDF4.Dataset(f, "a") as nc:
                for key, value in changes.items():
                    if key == "__delete__":
                        for name in value:
                            nc.delncattr(name)
                    else:
                        nc.setncattr(key, value)

    verb = "updated" if args.apply else "would change"
    print(f"\n{touched} of {len(files)} posterior(s) {verb}."
          + ("" if args.apply else "  Re-run with --apply."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
