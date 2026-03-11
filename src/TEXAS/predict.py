# TEXAS/predict.py
"""
High-level prediction API for the TEXAS proxy system model.

Two functions mirror the two directions of the calibration workflow
described in the manuscript:

  predict_RI_from_T   — forward:  T → scaled RI  (pure Python, no Stan)
  predict_T_from_RI   — inverse:  scaled RI → T  (runs Stan)

Both return percentile summaries (p5 / p50 / p95 by default) and
optionally the full ensemble / posterior.

Example
-------
>>> from TEXAS.predict import predict_RI_from_T, predict_T_from_RI
>>>
>>> # Forward: what scaled RI does the calibration predict at 20–30 °C?
>>> result = predict_RI_from_T(
...     temperatures=np.linspace(20, 30, 50),
...     posterior="gen_logi_fixed_hier_crtp_multiv_thermoT",
... )
>>> result["p50"]   # median calibration curve
>>>
>>> # Inverse: reconstruct temperature from downcore scaled RI
>>> result = predict_T_from_RI(
...     scaledRI=my_ri_array,
...     prior_mu_t=15.0,
...     prior_sigma_t=10.0,
...     fwd_posterior_name="gen_logi_fixed_hier_crtp_multiv_thermoT",
...     temptype="thermoT",
... )
>>> result["p50"]   # median temperature reconstruction
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, Sequence, Union, Any
from pathlib import Path

import numpy as np
import xarray as xr

from .stan.io import load_posterior
from .ensemble.generator import generate_ensemble_auto
from .stan.invT import predict_temperature_from_RI as _predict_temperature_from_RI
from .data.builder import InvTConfig


def predict_RI_from_T(
    temperatures: Union[np.ndarray, List[float]],
    posterior: Union[xr.Dataset, str],
    *,
    n_draws: int = 500,
    percentiles: List[float] = [5, 50, 95],
    return_full: bool = False,
    seed: int = 42,
    gdgt23ratio: Optional[np.ndarray] = None,
    no3: Optional[np.ndarray] = None,
    no3_cutoff: Optional[float] = None,
    suffix: Optional[str] = None,
) -> Dict[str, np.ndarray]:
    """
    Forward prediction: temperature → scaled RI percentiles.

    Samples `n_draws` self-consistent parameter sets from the forward
    calibration posterior (all parameters drawn from the same posterior
    index, preserving correlations) and evaluates the calibration curve
    at each requested temperature.  Corresponds to the forward model
    described in Eq. 1 / Eq. 6–7 of the manuscript.

    Parameters
    ----------
    temperatures : array-like
        Temperatures (°C) at which to evaluate the calibration curve.
    posterior : xr.Dataset or str
        Forward calibration posterior — either a loaded xr.Dataset or
        a saved-file name string (looked up in the posterior cache).
    n_draws : int
        Number of posterior draws to sample.  Default 500.
    percentiles : list of float
        Percentiles to return, e.g. [5, 50, 95].
    return_full : bool
        If True, also return the full (n_draws × len(temperatures))
        ensemble array and run metadata under keys ``"ensemble"`` and
        ``"metadata"``.
    seed : int
        Random seed for reproducible draw sampling.
    gdgt23ratio : array-like, optional
        GDGT-2/GDGT-3 ratio values (one per temperature point).
        Required only when the posterior was fitted with the multivariate
        model (β_{G₂/₃} correction).
    no3 : array-like, optional
        Nitrate concentration values (one per temperature point).
        Required only when the posterior was fitted with NO₃ correction.
    no3_cutoff : float, optional
        Nitrate threshold (μmol/L) below which the NO₃ correction applies.
        Defaults to the value stored in the posterior attributes.
    suffix : str, optional
        Force a specific parameter suffix (e.g. ``"crtp"``).  Auto-detected
        by priority order when omitted.

    Returns
    -------
    dict with keys:
        ``"x_vals"``  — temperature array (°C)
        ``"pN"``      — one key per requested percentile, e.g. ``"p5"``, ``"p50"``, ``"p95"``
        ``"ensemble"``  — full array, shape (n_draws, len(temperatures)), if return_full=True
        ``"metadata"``  — run metadata dict, if return_full=True
    """
    if isinstance(posterior, str):
        posterior = load_posterior(posterior)

    return generate_ensemble_auto(
        post_ds=posterior,
        x_vals=np.asarray(temperatures, dtype=float),
        model_type="forward",
        gdgt23ratio=gdgt23ratio,
        no3=no3,
        no3_cutoff=no3_cutoff,
        return_full_ensemble=return_full,
        suffix=suffix,
        # passed through **kwargs to generate_ensemble:
        n_draws=n_draws,
        percentiles=percentiles,
        seed=seed,
    )


def predict_T_from_RI(
    scaledRI: Union[np.ndarray, List[float]],
    prior_mu_t: Union[np.ndarray, float],
    prior_sigma_t: float,
    fwd_posterior_name: Optional[str] = None,
    *,
    fwd_posterior: Optional[xr.Dataset] = None,
    temptype: Optional[str] = None,
    site_name: Optional[str] = None,
    predictors: Optional[Dict[str, np.ndarray]] = None,
    config: Optional[InvTConfig] = None,
    chains: int = 4,
    iter_warmup: int = 500,
    iter_sampling: int = 1000,
    seed: int = 42,
    constraint_type: Literal[
        "unconstrained", "hard_constraint", "reparameterized", "soft"
    ] = "unconstrained",
    min_temp: Optional[float] = None,
    threads_per_chain: Optional[int] = None,
    save_results: bool = False,
    filename_tag: Optional[Union[str, Sequence[str]]] = None,
) -> Dict[str, Any]:
    """
    Inverse reconstruction: scaled RI → temperature percentiles.

    Runs the TEXAS-Bay inverse Stan model to infer paleotemperature from
    observed scaled Ring Index values.  Marginalises over M draws from
    the forward calibration posterior to propagate calibration uncertainty
    into the temperature reconstruction.  Corresponds to Section 8
    (Applications to Paleothermometry) of the manuscript.

    Parameters
    ----------
    scaledRI : array-like, shape (N,)
        Observed scaled Ring Index values from downcore or coretop samples.
    prior_mu_t : float or array-like, shape (N,)
        Prior mean temperature (°C).  Scalar applies the same prior to all
        N observations; array sets a site-specific prior per sample.
    prior_sigma_t : float
        Prior temperature uncertainty (°C).  Use a diffuse value (e.g. 10)
        when little prior information is available.
    fwd_posterior_name : str, optional
        Name of the saved forward calibration posterior (without ``.nc``
        extension) stored in the posterior cache.  Not required when
        *fwd_posterior* is supplied directly.
    fwd_posterior : xr.Dataset, optional
        Pre-loaded forward posterior Dataset.  When provided, no file I/O or
        Zenodo download is attempted.  Useful in Google Colab or any context
        where the posterior cache is unavailable — load the ``.nc`` yourself
        (e.g. from Google Drive) and pass it here.
    temptype : str, optional
        Temperature type: ``"SST"`` or ``"thermoT"``.  Used for metadata
        and output file naming.
    site_name : str, optional
        Label attached to result metadata and output filenames.
    predictors : dict, optional
        Non-thermal predictor arrays for the N observations, e.g.
        ``{"gdgt23ratio": array, "no3": array}``.  Must be provided when
        the forward posterior was fitted with the multivariate model.
    config : InvTConfig, optional
        Controls number of forward-posterior draws (M), seed, etc.
        Defaults to ``InvTConfig()`` (M=100).
    chains : int
        Number of MCMC chains.  Default 4.
    iter_warmup : int
        Warmup iterations per chain.  Default 500.
    iter_sampling : int
        Sampling iterations per chain.  Default 1000.
    seed : int
        Random seed.  Default 42.
    constraint_type : str
        Temperature constraint applied in the Stan model:
        ``"unconstrained"`` (default), ``"hard_constraint"`` (requires
        ``min_temp``), ``"reparameterized"``, or ``"soft"``.
    min_temp : float, optional
        Lower temperature bound (°C) when ``constraint_type="hard_constraint"``.
        Typically −1.8 (seawater freezing point).
    threads_per_chain : int, optional
        Enable within-chain parallelism via Stan's ``reduce_sum``.
    save_results : bool
        If True, save the posterior ``.nc`` and results ``.npz`` to the
        invT cache directory.
    filename_tag : str or list of str, optional
        Extra tag(s) appended to the output filename.

    Returns
    -------
    dict with keys:
        ``"scaledRI"`` — input scaled RI array
        ``"p5"``       — 5th percentile temperature (°C), shape (N,)
        ``"p50"``      — median temperature (°C), shape (N,)
        ``"p95"``      — 95th percentile temperature (°C), shape (N,)
        ``"metadata"`` — run metadata dict (model name, attrs, etc.)
    """
    return _predict_temperature_from_RI(
        scaledRI=scaledRI,
        prior_mu_t=prior_mu_t,
        prior_sigma_t=prior_sigma_t,
        fwd_posterior_name=fwd_posterior_name,
        fwd_posterior=fwd_posterior,
        site_name=site_name,
        temptype=temptype,
        predictors=predictors,
        config=config,
        chains=chains,
        iter_warmup=iter_warmup,
        iter_sampling=iter_sampling,
        seed=seed,
        save_results=save_results,
        filename_tag=filename_tag,
        threads_per_chain=threads_per_chain,
        model_type="direct",
        constraint_type=constraint_type,
        min_temp=min_temp,
    )
