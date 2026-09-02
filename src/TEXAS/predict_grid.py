# TEXAS/predict_grid.py
"""
DRAFT / UNREVIEWED -- see the warning banner at the top of README.md on this
branch (claude/gridT-gui-exploratory). Do not merge to main without explicit
co-author sign-off.

Fast inverse reconstruction via grid quadrature -- no Stan/CmdStan required.

This promotes the "gridT" reference implementation characterized in
TEXAS-revision/gridT_inversion_characterization.md (and embedded as a live
demo in docs/_static/why-plugin-p50-differs.html) into a real function.

It numerically integrates, on a temperature grid, the exact density the Stan
marginal invT model draws HMC samples from:

    p(T | y) ~ prior(T) * (1/M) * sum_m N(y | mu_m(T), sigma_m)

i.e. Bayesian quadrature against the same target -- not a different
estimator, just a different way of computing the same posterior. See the
characterization doc for the derivation and the "why this is method A, not
B or C" argument.

Validation status
------------------
The core quadrature math (this module's ``_grid_quantiles``) has been
checked against the embedded 80-draw reference posterior from
docs/_static/why-plugin-p50-differs.html and reproduces its published
p50 table to < 0.01 degC in the untruncated (cold/mid) range, and its
adaptive-upper-bound shift at saturated proxy values (RI >= 0.85) falls
within the doc's own documented truncation-error budget (<= 0.58 degC).

What has NOT been validated: the ``predict_T_grid()`` wrapper's use of
``build_invT_inputData()`` -- the M-draw sampling, predictor/EIV wiring,
and hyperparameter extraction -- has not been exercised end-to-end against
a real cached forward posterior (no CmdStan / cached .nc file was available
where this was written). Run it against a real posterior and compare
against ``predict_T_from_proxyObs()`` before trusting it for real
reconstructions.

Known limitations (carried over from the characterization doc):
- T0-shift mean function only. If pointed at an older additive-beta
  forward posterior (mu = lin + (1-b)/pow(...), lin = b + beta*predictor)
  rather than the current canonical t0shift one (T0_eff = T0 +
  gamma*predictor), this will silently reconstruct only the thermal term.
- Upper-tail credible intervals (p84/p95) are only as good as the grid's
  upper bound; ``grid_truncated`` flags rows where that may matter, but a
  flagged row's tail should not be trusted without checking against
  ``predict_T_from_proxyObs``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union
from pathlib import Path

import numpy as np
import xarray as xr

from .data.builder import build_invT_inputData, InvTConfig


def _grid_quantiles(
    y: float,
    mu_prior: float,
    sigma_prior: float,
    t0: np.ndarray,
    k: np.ndarray,
    b: np.ndarray,
    v: np.ndarray,
    sigma: np.ndarray,
    *,
    t0_shift: Optional[np.ndarray] = None,
    min_temp: float = -1.8,
    n_grid: int = 6000,
    percentiles: Sequence[float] = (5, 16, 50, 84, 95),
) -> Dict[str, float]:
    """
    Core grid-quadrature reconstruction for ONE observation.

    t0_shift, if given, is added to t0 per-draw before evaluating the curve
    (gamma_G23*gd + gamma_NO3*logno3, already gated/combined by the caller) --
    this is where the T0-shift multivariate correction plugs in.

    Adaptive upper bound: max(60, mu_prior + 5*sigma_prior), instead of a
    fixed cap, to avoid the warm-tail truncation the characterization doc
    flags for a hardcoded 45 degC grid.
    """
    from scipy.integrate import cumulative_trapezoid

    t0_eff = t0 if t0_shift is None else t0 + t0_shift
    T_hi = max(60.0, mu_prior + 5 * sigma_prior)
    T = np.linspace(min_temp, T_hi, n_grid)

    mu = b[None, :] + (1 - b[None, :]) / np.power(
        1 + np.exp(-k[None, :] * (T[:, None] - t0_eff[None, :])), 1.0 / v[None, :]
    )
    # Monte Carlo marginal likelihood: average over M forward-posterior draws.
    like = np.mean(np.exp(-0.5 * ((y - mu) / sigma[None, :]) ** 2) / sigma[None, :], axis=1)
    prior = np.exp(-0.5 * ((T - mu_prior) / sigma_prior) ** 2)
    post = like * prior

    cdf = cumulative_trapezoid(post, T, initial=0.0)
    total = cdf[-1]
    out = {f"p{p}": float(np.interp(p / 100.0 * total, cdf, T)) for p in percentiles}
    # Rule of thumb from the characterization doc: non-negligible density
    # still sitting at the grid's right edge means the tail may be cut off.
    out["grid_truncated"] = bool(post[-1] > 1e-3 * post.max())
    return out


def predict_T_grid(
    proxyObs: Union[np.ndarray, List[float]],
    prior_mu_t: Union[np.ndarray, float],
    prior_sigma_t: float,
    fwd_posterior: Union[str, xr.Dataset],
    *,
    predictors: Optional[Dict[str, np.ndarray]] = None,
    no3: Optional[Union[float, np.ndarray]] = None,
    gdgt23ratio: Optional[Union[float, np.ndarray]] = None,
    min_temp: float = -1.8,
    n_grid: int = 6000,
    percentiles: Sequence[float] = (5, 16, 50, 84, 95),
    config: Optional[InvTConfig] = None,
    fwd_cache_dir: Optional[Union[str, Path]] = None,
    return_full: bool = False,
) -> Dict[str, Any]:
    """
    DRAFT. Fast inverse reconstruction: proxy -> temperature percentiles,
    via grid quadrature instead of Stan/HMC sampling. See the module
    docstring for validation status and known limitations before using this
    for anything beyond a quick sanity check.

    Same target posterior as ``TEXAS.predict.predict_T_from_proxyObs``, and
    reuses ``build_invT_inputData`` directly for the M-draw sampling and
    predictor/EIV wiring, swapping HMC sampling for numerical integration on
    a temperature grid. No CmdStan required.

    Unlike ``predict_T_from_proxyObs``, this does NOT yet accept
    ``proxy_name``/``temptype`` (``build_invT_inputData`` has no such
    parameters -- that function reads the calibration target from the
    forward posterior's own attrs) or the WOA23 lat/lon NO3 lookup; only the
    plain ``no3=``/``gdgt23ratio=`` shorthands and ``predictors=`` dict are
    wired through here.

    Parameters
    ----------
    fwd_posterior : str or xr.Dataset
        Forward calibration posterior -- a cache-lookup name (str) or a
        pre-loaded Dataset. Required (unlike predict_T_from_proxyObs, this
        draft has no bundled-default fallback).

    Returns
    -------
    dict with keys ``"p{percentile}"`` per requested percentile,
    ``"flags"`` (dict with ``"grid_truncated"``, one bool per observation),
    and ``"metadata"``.
    """
    predictors = dict(predictors or {})
    if gdgt23ratio is not None:
        predictors["gdgt23ratio"] = gdgt23ratio
    if no3 is not None:
        predictors["no3"] = no3

    build_kwargs: Dict[str, Any] = dict(
        proxyObs=proxyObs, prior_mu_t=prior_mu_t, prior_sigma_t=prior_sigma_t,
        predictors=predictors, config=config, fwd_cache_dir=fwd_cache_dir,
    )
    if isinstance(fwd_posterior, str):
        build_kwargs["fwd_posterior_name"] = fwd_posterior
    else:
        build_kwargs["fwd_posterior"] = fwd_posterior

    data, meta = build_invT_inputData(**build_kwargs)

    y = np.asarray(data["proxyObs"], dtype=float)
    mu_t = np.broadcast_to(np.asarray(data["prior_mu_t"], dtype=float), y.shape)
    sigma_t = float(data["prior_sigma_t"])
    N = y.shape[0]

    t0, k, b, v, sigma = (
        np.asarray(data[key], dtype=float) for key in ("t0", "k", "b", "v", "sigma_proxyObs")
    )
    use_gd = bool(data.get("use_gdgt23ratio", 0))
    use_no3 = bool(data.get("use_no3", 0))
    gamma_gd = np.asarray(data.get("gamma_G23", np.zeros_like(t0)), dtype=float)
    gamma_no3 = np.asarray(data.get("gamma_NO3", np.zeros_like(t0)), dtype=float)
    gd_obs = np.asarray(data.get("gdgt23ratio", np.zeros(N)), dtype=float)
    no3_obs = np.asarray(data.get("no3", np.zeros(N)), dtype=float)
    no3_cutoff = float(data.get("no3_cutoff", 0.0))

    out = {f"p{p}": np.empty(N) for p in percentiles}
    truncated = np.zeros(N, dtype=bool)

    for i in range(N):
        # T0-shift: predictors move the curve's location, not its response --
        # matches invT_..._t0shift.stan's mean function exactly (see the
        # module docstring for the additive-beta alternative this does NOT
        # currently support).
        shift = np.zeros_like(t0)
        if use_gd:
            shift = shift + gamma_gd * gd_obs[i]
        if use_no3 and 0.0 < no3_obs[i] < no3_cutoff:
            shift = shift + gamma_no3 * np.log10(no3_obs[i] + 1e-9)

        row = _grid_quantiles(
            y[i], mu_t[i], sigma_t, t0, k, b, v, sigma,
            t0_shift=shift, min_temp=min_temp, n_grid=n_grid, percentiles=percentiles,
        )
        for p in percentiles:
            out[f"p{p}"][i] = row[f"p{p}"]
        truncated[i] = row["grid_truncated"]

    out["flags"] = {"grid_truncated": truncated}
    out["metadata"] = {**meta, "method": "grid_quadrature", "n_grid": n_grid, "min_temp": min_temp}
    if return_full:
        out["t0"], out["k"], out["b"], out["v"], out["sigma_proxyObs"] = t0, k, b, v, sigma
    return out
