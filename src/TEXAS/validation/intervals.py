"""Credible-interval helpers for reviewer-facing reporting.

Reviewer #3 (Krapp) asked for (a) "credible interval" rather than "confidence
interval" terminology, and (b) 95% intervals in addition to the 68% bands used
in several manuscript figures. These helpers centralize both so every table and
figure in the revision uses consistent, correctly-labeled intervals.
"""
from __future__ import annotations

import xarray as xr

# Central credible-interval probability masses. 0.68 kept for backwards
# comparison with the current figures; 0.95 is the reviewer-requested default.
LEVELS = {0.68: (0.16, 0.84), 0.90: (0.05, 0.95), 0.95: (0.025, 0.975)}

SAMPLE_DIMS = ("chain", "draw")


def credible_interval(
    da: xr.DataArray,
    level: float = 0.95,
    dim: "tuple[str, ...] | str" = SAMPLE_DIMS,
) -> xr.Dataset:
    """Posterior median + central credible interval of a draw-indexed variable.

    Args:
        da: A posterior variable with sample dimensions (default ``chain``,
            ``draw``). Missing sample dims are ignored, so a
            single-``draw``-dim array also works.
        level: Central probability mass (must be a key of :data:`LEVELS`).
        dim: Sample dimension(s) to reduce over.

    Returns:
        Dataset with ``median``, ``lower``, ``upper`` and scalar ``mean``, plus
        ``interval_level`` / ``interval_kind='credible'`` attrs.
    """
    if level not in LEVELS:
        raise ValueError(f"level must be one of {sorted(LEVELS)}, got {level}")
    lo_q, hi_q = LEVELS[level]
    dims = tuple(d for d in ([dim] if isinstance(dim, str) else dim) if d in da.dims)
    if not dims:
        raise ValueError(f"none of {dim} are dimensions of {da.name!r} ({da.dims})")

    q = da.quantile([lo_q, 0.5, hi_q], dim=dims)
    out = xr.Dataset(
        {
            "mean": da.mean(dim=dims),
            "lower": q.sel(quantile=lo_q, drop=True),
            "median": q.sel(quantile=0.5, drop=True),
            "upper": q.sel(quantile=hi_q, drop=True),
        }
    )
    out.attrs["interval_level"] = level
    out.attrs["interval_kind"] = "credible"
    out.attrs["interval_lower_q"] = lo_q
    out.attrs["interval_upper_q"] = hi_q
    return out


def format_ci(summary: xr.Dataset, unit: str = "", sig: int = 3) -> str:
    """Render a scalar credible-interval Dataset as ``median [lower, upper]``."""
    level = summary.attrs.get("interval_level", 0.95)

    def _f(x) -> str:
        return f"{float(x):.{sig}g}{unit}"

    return (
        f"{_f(summary['median'])} "
        f"[{_f(summary['lower'])}, {_f(summary['upper'])}] "
        f"({int(level * 100)}% credible)"
    )
