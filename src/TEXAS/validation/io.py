"""Result persistence for the revision-1 analysis workflow.

Every analysis in :mod:`TEXAS.validation` writes its output to disk so results
are reproducible, reviewer-shareable, and never silently recomputed:

- xarray ``Dataset`` / ``DataArray`` -> compressed NetCDF (``.nc``)
- pandas ``DataFrame`` -> ``.csv``

Each saved file carries provenance attributes (the reviewer comment it answers,
the config that produced it, the TEXAS version, and a UTC timestamp) so a file
found on disk months later is self-describing.

Results live under ``<results_root>/<group>/<name>.{nc,csv}`` where
``results_root`` is, in priority order:

1. the ``TEXAS_REVISION_RESULTS_DIR`` environment variable, or
2. ``<repo>/data/revision1/`` in a git checkout, or
3. ``~/.texas/revision1/`` when pip-installed outside a repo.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path

import pandas as pd
import xarray as xr


def results_root() -> Path:
    """Resolve the root directory for revision-1 analysis outputs."""
    env = os.environ.get("TEXAS_REVISION_RESULTS_DIR")
    if env:
        return Path(env)
    from ..utils.paths import get_project_root

    return get_project_root() / "data" / "revision1"


def _texas_version() -> str:
    try:
        import TEXAS

        return getattr(TEXAS, "__version__", "unknown")
    except Exception:
        return "unknown"


def _provenance(reviewer: str | None, config: dict | None) -> dict:
    """Build the provenance attribute block attached to every saved result."""
    return {
        "texas_version": _texas_version(),
        "created_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "reviewer_comment": reviewer or "",
        # Stan/NetCDF attrs must be scalar/str — serialize the config dict.
        "config_json": json.dumps(config or {}, default=str, sort_keys=True),
    }


def save_result(
    obj: "xr.Dataset | xr.DataArray | pd.DataFrame",
    name: str,
    *,
    group: str,
    reviewer: str | None = None,
    config: dict | None = None,
    overwrite: bool = True,
) -> Path:
    """Persist an analysis result with provenance, returning its path.

    Args:
        obj: The result. A ``Dataset``/``DataArray`` is written as NetCDF; a
            ``DataFrame`` as CSV (with a sidecar ``<name>.meta.json`` holding
            provenance, since CSV has no attribute channel).
        name: Base filename (no extension), e.g. ``"calibration_metrics_ci"``.
        group: Subdirectory, e.g. ``"groupA"`` / ``"groupB"`` / ``"groupC"``.
        reviewer: Short tag for the reviewer comment this answers, e.g.
            ``"R3-Krapp:noise-terms"``.
        config: The config dict that produced the result (screening choice,
            ring definition, fold layout, ...). Stored verbatim as JSON.
        overwrite: If False and the target exists, raise ``FileExistsError``.

    Returns:
        Path to the written file.
    """
    root = results_root() / group
    root.mkdir(parents=True, exist_ok=True)
    prov = _provenance(reviewer, config)

    if isinstance(obj, (xr.Dataset, xr.DataArray)):
        ds = obj.to_dataset() if isinstance(obj, xr.DataArray) else obj
        dest = root / f"{name}.nc"
        if dest.exists() and not overwrite:
            raise FileExistsError(dest)
        ds = ds.copy()
        ds.attrs.update(prov)
        enc = {v: {"zlib": True, "complevel": 4} for v in ds.data_vars}
        ds.to_netcdf(dest, encoding=enc)
        return dest

    if isinstance(obj, pd.DataFrame):
        dest = root / f"{name}.csv"
        if dest.exists() and not overwrite:
            raise FileExistsError(dest)
        obj.to_csv(dest, index=True)
        (root / f"{name}.meta.json").write_text(json.dumps(prov, indent=2))
        return dest

    raise TypeError(
        f"save_result expects xr.Dataset/DataArray or pd.DataFrame, got {type(obj)!r}"
    )


def load_result(name: str, *, group: str) -> "xr.Dataset | pd.DataFrame":
    """Load a previously saved result (NetCDF preferred, else CSV)."""
    root = results_root() / group
    nc = root / f"{name}.nc"
    if nc.exists():
        return xr.open_dataset(nc)
    csv = root / f"{name}.csv"
    if csv.exists():
        return pd.read_csv(csv, index_col=0)
    raise FileNotFoundError(f"No result '{name}' under {root}")


def list_results(group: str | None = None) -> list[Path]:
    """List saved result files, optionally within one group."""
    root = results_root()
    if not root.exists():
        return []
    pattern = f"{group}/*" if group else "**/*"
    return sorted(
        p for p in root.glob(pattern) if p.suffix in (".nc", ".csv")
    )
