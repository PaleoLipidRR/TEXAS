"""Group A — reporting metrics extracted from existing forward posteriors.

No refitting: every quantity here is read from a saved forward-calibration
``.nc`` and reduced to a credible interval. Addresses:

- R3(Krapp): R2 / RMSE need credible intervals, not point estimates.
- R3(Krapp): the noise/error terms must be reported (sigma^2_culmeso top layer,
  epsilon bottom layer).
- R1/R2: MCMC diagnostics (R-hat, ESS, E-BFMI, divergences) reported explicitly.

The forward Stan models already emit per-draw ``R2_full``, ``bayesR2_full`` and
``RMSE_full`` as generated quantities, and the noise scales as parameters, so
these sit in the posterior as ``(chain, draw)`` data variables ready to
summarize.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

from .intervals import credible_interval

# In-sample calibration skill, per draw (Stan generated quantities).
CALIBRATION_METRICS = ["R2_full", "bayesR2_full", "RMSE_full"]

# Noise / error terms. Two families, per Krapp's ambiguous "sigma^2_culmeso":
#   observation  -> proxy-observation (measurement + scatter) noise
#   pooling      -> hierarchical spread of coretop curve params about culmeso mean
OBSERVATION_NOISE = [
    "sigma_proxyObs_crtp",   # bottom-layer residual  (review's epsilon)
    "sigma_proxyObs_cul",    # top-layer culture obs noise
    "sigma_proxyObs_meso",   # top-layer mesocosm obs noise
]
POOLING_NOISE = [
    "sigma_t0_culmeso",
    "sigma_k_culmeso",
    "sigma_b_culmeso",
    "sigma_v_culmeso",
]


def _summarize_scalar_vars(
    ds: xr.Dataset,
    names: list[str],
    coord_name: str,
    level: float,
    kinds: "dict[str, str] | None" = None,
) -> xr.Dataset:
    """Reduce each named scalar-per-draw variable to a credible interval.

    Variables absent from ``ds`` or that do not reduce to a scalar (e.g. a
    per-site vector parameter) are skipped; the skipped names are recorded in
    the ``skipped`` attr so nothing is silently dropped.
    """
    rows: dict[str, list] = {k: [] for k in ("mean", "lower", "median", "upper")}
    kept: list[str] = []
    kept_kinds: list[str] = []
    skipped: list[str] = []
    for n in names:
        if n not in ds.data_vars:
            continue
        ci = credible_interval(ds[n], level=level)
        if ci["mean"].ndim != 0:  # not scalar (e.g. per-site) -> report elsewhere
            skipped.append(n)
            continue
        for k in rows:
            rows[k].append(float(ci[k]))
        kept.append(n)
        if kinds is not None:
            kept_kinds.append(kinds.get(n, ""))

    if not kept:
        raise ValueError(
            f"none of {names} are scalar-per-draw variables in this posterior "
            f"(data_vars: {list(ds.data_vars)[:12]}...)"
        )

    out = xr.Dataset(
        {k: (coord_name, np.asarray(v)) for k, v in rows.items()},
        coords={coord_name: kept},
    )
    if kinds is not None:
        out = out.assign_coords({"kind": (coord_name, kept_kinds)})
    out.attrs["interval_level"] = level
    out.attrs["interval_kind"] = "credible"
    if skipped:
        out.attrs["skipped_nonscalar"] = ", ".join(skipped)
    return out


def summarize_calibration_metrics(ds: xr.Dataset, level: float = 0.95) -> xr.Dataset:
    """Credible intervals for in-sample R2 / bayesR2 / RMSE from a forward posterior.

    Returns a Dataset indexed by a ``metric`` coordinate with ``mean``,
    ``lower``, ``median``, ``upper``. Note these are **in-sample** (calibration)
    metrics; out-of-sample skill comes from the cross-validation harness.
    """
    out = _summarize_scalar_vars(ds, CALIBRATION_METRICS, "metric", level)
    out.attrs["sample"] = "in-sample (calibration)"
    if "proxy_name" in ds.attrs:
        out.attrs["proxy_name"] = ds.attrs["proxy_name"]
    return out


def summarize_noise_terms(ds: xr.Dataset, level: float = 0.95) -> xr.Dataset:
    """Credible intervals for the model noise/error terms of a forward posterior.

    Reports both interpretations of the reviewer's "sigma^2_culmeso": the
    proxy-observation noise scales and (when present) the hierarchical pooling
    spreads. The ``kind`` coordinate labels each parameter ``observation`` or
    ``pooling`` so the manuscript can cite whichever the reviewer intends.
    """
    kinds = {**{n: "observation" for n in OBSERVATION_NOISE},
             **{n: "pooling" for n in POOLING_NOISE}}
    return _summarize_scalar_vars(
        ds, OBSERVATION_NOISE + POOLING_NOISE, "parameter", level, kinds=kinds
    )


def diagnostics_table(datasets: list[xr.Dataset]) -> pd.DataFrame:
    """MCMC diagnostics (R-hat, ESS, E-BFMI, divergences) as a tidy table.

    Reads the ``stan_diag_*`` attrs attached at sampling time and persisted in
    each ``.nc``. Thin wrapper over :func:`TEXAS.diagnostics.create_summary_table`
    that also flags posteriors missing the diagnostic attrs (e.g. saved before
    the diagnostics-attachment code existed) rather than silently omitting them.
    """
    from ..diagnostics import create_summary_table

    table = create_summary_table(datasets)
    missing = [
        ds.attrs.get("filename", f"posterior[{i}]")
        for i, ds in enumerate(datasets)
        if not any(k.startswith("stan_diag_") for k in ds.attrs)
    ]
    if missing:
        table.attrs["missing_diagnostics"] = missing
    return table
