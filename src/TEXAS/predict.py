# TEXAS/predict.py
"""
High-level prediction API for the TEXAS proxy system model.

Two functions mirror the two directions of the calibration workflow
described in the manuscript:

  predict_proxy_from_T  — forward:  T → proxy (Scaled RI, TEX86, …)  (pure Python, no Stan)
  predict_T_from_proxyObs — inverse:  proxy → T  (runs Stan)

Both return percentile summaries (p5 / p50 / p95 by default) and
optionally the full ensemble / posterior.

Example
-------
>>> from TEXAS.predict import predict_proxy_from_T, predict_T_from_proxyObs
>>>
>>> # Forward: what Scaled RI does the calibration predict at 20–30 °C?
>>> result = predict_proxy_from_T(
...     temperatures=np.linspace(20, 30, 50),
...     posterior="gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI_cren3",
... )
>>> result["p50"]   # median calibration curve
>>>
>>> # Inverse: reconstruct temperature from downcore Scaled RI
>>> result = predict_T_from_proxyObs(
...     proxyObs=my_ri_array,
...     prior_mu_t=15.0,
...     prior_sigma_t=10.0,
...     fwd_posterior="tx.GHPU.thm.sri03.p0",
...     temptype="thermoT",
... )
>>> result["p50"]   # median temperature reconstruction
"""

from __future__ import annotations

import warnings
from typing import Dict, List, Literal, Optional, Sequence, Union, Any
from pathlib import Path

import numpy as np
import xarray as xr

from .stan.io import load_posterior
from .ensemble.generator import generate_ensemble_auto
from .stan.invT import predict_temperature_from_proxyObs as _predict_temperature_from_proxyObs
from .data.builder import InvTConfig
from .constants import DEFAULT_FWD_POSTERIOR
from .data.ocean_lookup import lookup_no3_from_woa, get_ocean_prop_ds


def predict_proxy_from_T(
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
    fwd_cache_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, np.ndarray]:
    """
    Forward prediction: temperature → proxy percentiles (Scaled RI, TEX86, or any fitted proxy).

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
    fwd_cache_dir : Path or str, optional
        Directory to resolve *posterior* in when it is given as a name string.
        Defaults to the standard forward posterior cache.  Ignored when a
        loaded Dataset is passed.

    Returns
    -------
    dict with keys:
        ``"x_vals"``  — temperature array (°C)
        ``"pN"``      — one key per requested percentile, e.g. ``"p5"``, ``"p50"``, ``"p95"``
        ``"ensemble"``  — full array, shape (n_draws, len(temperatures)), if return_full=True
        ``"metadata"``  — run metadata dict, if return_full=True
    """
    if isinstance(posterior, str):
        posterior = load_posterior(posterior, cache_dir=fwd_cache_dir)

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


def predict_T_from_proxyObs(
    proxyObs: Union[np.ndarray, List[float]],
    prior_mu_t: Union[np.ndarray, float],
    prior_sigma_t: float,
    fwd_posterior: Optional[Union[str, xr.Dataset]] = None,
    *,
    proxy_name: Optional[str] = None,
    temptype: Optional[str] = None,
    site_name: Optional[str] = None,
    predictors: Optional[Dict[str, np.ndarray]] = None,
    # ── Predictor shorthands (override anything in predictors dict) ───────
    no3: Optional[Union[float, np.ndarray]] = None,
    gdgt23ratio: Optional[Union[float, np.ndarray]] = None,
    # ── Modern-ocean NO₃ lookup from WOA23-derived dataset ───────────────
    site_lat: Optional[Union[float, np.ndarray]] = None,
    site_lon: Optional[Union[float, np.ndarray]] = None,
    no3_dataset: Optional[xr.Dataset] = None,
    no3_dataset_var: str = "no3_sf2tc_avg",
    # ─────────────────────────────────────────────────────────────────────
    config: Optional[InvTConfig] = None,
    chains: int = 4,
    iter_warmup: int = 500,
    iter_sampling: int = 1000,
    seed: int = 42,
    constraint_type: Literal[
        "unconstrained", "hard_constraint", "truncated_prior", "reparameterized", "soft"
    ] = "unconstrained",
    min_temp: Optional[float] = None,
    threads_per_chain: Optional[int] = None,
    save_results: bool = False,
    save_draws: bool = False,
    filename_tag: Optional[Union[str, Sequence[str]]] = None,
    cache_dir: Optional[Union[str, Path]] = None,
    fwd_cache_dir: Optional[Union[str, Path]] = None,
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
    proxyObs : array-like, shape (N,)
        Observed proxy values from downcore or coretop samples (e.g. scaledRI, TEX86).
    prior_mu_t : float or array-like, shape (N,)
        Prior mean temperature (°C).  Scalar applies the same prior to all
        N observations; array sets a site-specific prior per sample.
    prior_sigma_t : float
        Prior temperature uncertainty (°C).  Use a diffuse value (e.g. 10)
        when little prior information is available.
    fwd_posterior : str or xr.Dataset, optional
        The forward calibration posterior.  When omitted, the full multivariate
        T0-shift calibration for *temptype* is used --- ``tx.GHEB.sst.sri03.G23-N1p0``
        for SST, ``tx.GHEB.thm.sri03.G23-N1p0`` for thermoT --- which ships with
        the package, so no download is required.  Accepts either:

        - **str** — name of the saved posterior (without ``.nc`` extension)
          in the posterior cache directory.  The file is loaded automatically.
        - **xr.Dataset** — a pre-loaded posterior Dataset.  No file I/O or
          Zenodo download is attempted; pass this when the cache is unavailable
          (e.g. Google Colab with a Drive-mounted ``.nc``)::

              ds = xr.open_dataset("my_drive/posterior.nc")
              result = predict_T_from_proxyObs(..., fwd_posterior=ds)

    temptype : str, optional
        Temperature type: ``"SST"`` or ``"thermoT"``.  **Optional.**  It does
        not change the reconstruction, which follows the calibration supplied:
        when *fwd_posterior* is given, the target is read from that posterior's
        own attributes and *temptype* only labels the metadata and output
        filenames (a value conflicting with the calibration raises a warning).
        It matters in exactly one case --- when *fwd_posterior* is omitted, it
        chooses which default calibration is used, SST or thermoT.
    site_name : str, optional
        Label attached to result metadata and output filenames.
    predictors : dict, optional
        Non-thermal predictor arrays for the N observations, e.g.
        ``{"gdgt23ratio": array, "no3": array}``.  Must be provided when
        the forward posterior was fitted with the multivariate model.
        Overridden by *no3* / *gdgt23ratio* shorthands when both are given.
    no3 : float or array-like, optional
        Nitrate concentration (µmol/L) for the N observations.

        - **Array** (length N): per-observation values — use modern WOA23
          values extracted at each sample's location (``ocean_prop_ds``
          column ``"no3_sf2tc_avg"``).
        - **Scalar**: broadcast to all N observations.  Pass a value above
          ``no3_cutoff`` (e.g. ``no3=10.0`` when ``no3_cutoff=1.0``) to
          effectively disable the NO₃ correction — all observations fall
          outside the correction window.

        Overrides any ``"no3"`` key in *predictors*.  Ignored when
        *site_lat* / *site_lon* / *no3_dataset* are also provided (the
        lookup result takes priority).
    gdgt23ratio : float or array-like, optional
        GDGT-2/GDGT-3 ratio for the N observations.  Scalar or array,
        same broadcast rules as *no3*.  Overrides any ``"gdgt23ratio"``
        key in *predictors*.
    site_lat : float or array-like, optional
        Decimal latitude(s) of the study site(s).  Scalar for a single
        drill core; array of length N to assign a distinct location to
        each observation.  Requires *site_lon* and *no3_dataset*.
    site_lon : float or array-like, optional
        Decimal longitude(s) of the study site(s).  Same shape rules as
        *site_lat*.
    no3_dataset : xr.Dataset, optional
        WOA23-derived dataset with a ``(lat, lon)`` grid, typically the
        ``ocean_prop_ds`` generated in the preprocessing notebook
        (SI_code0).  Must contain *no3_dataset_var*.  When provided
        together with *site_lat* / *site_lon*, the NO₃ value at those
        coordinates is looked up via bilinear interpolation and used as
        the predictor.  The result is a scalar (one drill site) or array
        (per-obs sites), and is broadcast to all N observations when scalar.
        **Optional** when *site_lat* / *site_lon* are given: if omitted, the
        ~20 MB ``ocean_prop_ds`` field is downloaded from Zenodo and cached
        automatically (see :func:`TEXAS.data.ocean_lookup.get_ocean_prop_ds`
        / :func:`TEXAS.download_ocean_properties`) — pass it explicitly to
        avoid the download (e.g. a pre-loaded copy, or a Colab session with
        no persistent cache).
    no3_dataset_var : str
        Variable name to extract from *no3_dataset*.
        Default ``"no3_sf2tc_avg"``.
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

        - ``"unconstrained"`` (default): no lower bound; P5 can be unrealistically cold
          near the calibration curve's lower asymptote.
        - ``"hard_constraint"``: hard lower bound via ``<lower=min_temp>``; prevents
          sub-freezing samples but the Jacobian biases P50 warm for polar sites.
        - ``"truncated_prior"`` (recommended when ``min_temp`` is set): proper
          truncated Normal prior via inverse-CDF reparameterization — P50 is
          data-driven and P5 is bounded at ``min_temp`` without warm bias.
        - ``"reparameterized"``, ``"soft"``: experimental variants.
    min_temp : float, optional
        Lower temperature bound (°C). Required for ``"hard_constraint"`` and
        ``"truncated_prior"``. Typically −1.8 (seawater freezing point).
        When provided without an explicit ``constraint_type``, automatically
        selects ``"truncated_prior"``.
    threads_per_chain : int, optional
        Enable within-chain parallelism via Stan's ``reduce_sum``.
    save_results : bool
        If True, save the quantile posterior ``.nc`` and results ``.npz`` to the
        invT cache directory.
    save_draws : bool
        If True, also save the raw posterior draws (pre-quantile) as a separate
        ``{base}_draws.nc`` file in the invT cache directory.  The file contains
        ``t_est`` with dims ``(chain, draw, obs_idx)`` and is suitable for
        kernel-density plots or custom quantile calculation.  Default False.
    filename_tag : str or list of str, optional
        Extra tag(s) appended to the output filename.
    cache_dir : Path or str, optional
        Directory where ``.nc`` and ``.npz`` files are written when
        *save_results* or *save_draws* is True.  Defaults to the standard
        invT cache (``~/.texas/cache/TEXAS_invT_posterior_cache/`` for pip
        installs, or ``data/cache/TEXAS_invT_posterior_cache/`` in the repo).
    fwd_cache_dir : Path or str, optional
        Directory to resolve *fwd_posterior* in when it is given as a name
        string.  Defaults to the standard forward posterior cache.  This is a
        separate directory from *cache_dir*, which controls only where results
        are written.

    Returns
    -------
    dict with keys:
        ``"proxyObs"``   — input proxy array
        ``"proxy_name"`` — proxy type label (e.g. ``"scaledRI"``, ``"TEX86"``)
        ``"p5"``         — 5th percentile temperature (°C), shape (N,)
        ``"p50"``        — median temperature (°C), shape (N,)
        ``"p95"``        — 95th percentile temperature (°C), shape (N,)
        ``"metadata"``   — run metadata dict (model name, attrs, etc.)
    """
    # ── Default calibration ──────────────────────────────────────────────────
    # Omitting fwd_posterior selects the full multivariate T0-shift calibration
    # for the requested target, which ships inside the package. It is the
    # default because the nonthermal effects are in the coretop data whether or
    # not a user models them: a temperature-only calibration does not remove
    # them, it absorbs them into the thermal parameters.
    if fwd_posterior is None:
        _target = temptype if temptype in DEFAULT_FWD_POSTERIOR else "SST"
        fwd_posterior = DEFAULT_FWD_POSTERIOR[_target]
        print(
            f"📚 No fwd_posterior given — using the default {_target} calibration "
            f"'{fwd_posterior}' (full multivariate, G23 + NO3)."
        )

    # ── Normalise fwd_posterior: split str vs pre-loaded Dataset ─────────────
    if isinstance(fwd_posterior, xr.Dataset):
        _fwd_ds: Optional[xr.Dataset] = fwd_posterior
        _fwd_name: Optional[str] = None
    else:
        _fwd_ds = None
        _fwd_name = fwd_posterior  # str or None

    # ── Resolve NO₃ predictor ─────────────────────────────────────────────────
    # Priority: site_lat/lon lookup > no3= explicit > predictors["no3"] > zeros
    predictors = dict(predictors or {})

    if site_lat is not None or site_lon is not None:
        if site_lat is None or site_lon is None:
            raise ValueError(
                "site_lat and site_lon must both be provided for a WOA23 lookup."
            )
        if no3_dataset is None:
            try:
                no3_dataset = get_ocean_prop_ds()
            except Exception as e:
                raise ValueError(
                    "no3_dataset must be provided when using site_lat/site_lon, "
                    "and the automatic download of the WOA23-derived "
                    f"ocean_prop_ds from Zenodo failed ({e}). Pass no3_dataset "
                    "explicitly (e.g. from your preprocessing notebook), or "
                    "retry with TEXAS.download_ocean_properties()."
                ) from e
            print(
                "🌊 no3_dataset not provided — downloaded/cached the WOA23 "
                "ocean_prop_ds field from Zenodo."
            )
        no3 = lookup_no3_from_woa(
            lat=site_lat,
            lon=site_lon,
            woa_dataset=no3_dataset,
            variable=no3_dataset_var,
        )
        _lat_repr = f"{site_lat}" if np.isscalar(site_lat) else f"array[{np.asarray(site_lat).size}]"
        _lon_repr = f"{site_lon}" if np.isscalar(site_lon) else f"array[{np.asarray(site_lon).size}]"
        _no3_repr = f"{float(no3):.3g}" if np.asarray(no3).ndim == 0 else f"array[{np.asarray(no3).size}], mean={float(np.nanmean(no3)):.3g}"
        print(f"🌊 WOA23 NO₃ lookup: lat={_lat_repr}, lon={_lon_repr} → {_no3_repr} µmol/L")

    if no3 is not None:
        predictors["no3"] = no3
    if gdgt23ratio is not None:
        predictors["gdgt23ratio"] = gdgt23ratio

    # Warn if predictors are passed but the forward posterior doesn't use them
    _ds_for_check = _fwd_ds
    if _ds_for_check is None and _fwd_name:
        try:
            _ds_for_check = load_posterior(_fwd_name, cache_dir=fwd_cache_dir)
        except Exception:
            pass
    if _ds_for_check is not None:
        _attrs = _ds_for_check.attrs
        if predictors.get("gdgt23ratio") is not None and not _attrs.get("use_gdgt23ratio", False):
            warnings.warn(
                "gdgt23ratio was passed but the forward posterior has no GDGT-2/3 ratio "
                "parameters (use_gdgt23ratio=False) — the predictor will be silently ignored. "
                "To apply the GDGT-2/3 correction, use a multivariate posterior "
                "(e.g. gen_logi_fixed_hier_crtp_multiv_priorApprox_*).",
                UserWarning, stacklevel=2,
            )
        _fwd_temptype = _attrs.get("temptype")
        if temptype and _fwd_temptype and temptype != _fwd_temptype:
            warnings.warn(
                f"temptype={temptype!r} was passed, but this calibration was "
                f"fitted against {_fwd_temptype!r}. The reconstruction follows "
                f"the calibration, not the label, so the result is "
                f"{_fwd_temptype}; only the metadata and output filenames would "
                f"say otherwise. Drop temptype= to take it from the calibration.",
                UserWarning, stacklevel=2,
            )
        if predictors.get("gdgt23ratio") is None and _attrs.get("use_gdgt23ratio", False):
            warnings.warn(
                "This calibration uses the GDGT-2/3 ratio, but none was supplied — "
                "it will be treated as 0, which is not the same as switching the "
                "correction off: it asserts a ratio of zero and biases the "
                "reconstruction cold by roughly gamma_G23 x (true ratio) degC. "
                "Pass gdgt23ratio=, or use a temperature-only calibration "
                "(e.g. 'tx.GHPU.sst.sri03.p0').",
                UserWarning, stacklevel=2,
            )
        if predictors.get("no3") is not None and not _attrs.get("use_no3", False):
            warnings.warn(
                "no3 was passed but the forward posterior has no NO₃ parameters "
                "(use_no3=False) — the predictor will be silently ignored. "
                "To apply the NO₃ correction, use a multivariate posterior "
                "(e.g. gen_logi_fixed_hier_crtp_multiv_priorApprox_*).",
                UserWarning, stacklevel=2,
            )

    return _predict_temperature_from_proxyObs(
        proxyObs=proxyObs,
        prior_mu_t=prior_mu_t,
        prior_sigma_t=prior_sigma_t,
        fwd_posterior_name=_fwd_name,
        fwd_posterior=_fwd_ds,
        site_name=site_name,
        temptype=temptype,
        predictors=predictors,
        config=config,
        chains=chains,
        iter_warmup=iter_warmup,
        iter_sampling=iter_sampling,
        seed=seed,
        save_results=save_results,
        save_draws=save_draws,
        filename_tag=filename_tag,
        cache_dir=cache_dir,
        fwd_cache_dir=fwd_cache_dir,
        threads_per_chain=threads_per_chain,
        model_type="direct",
        constraint_type=constraint_type,
        min_temp=min_temp,
        proxy_name=proxy_name,
    )


def compute_scaledRI(
    gdgt0,
    gdgt1,
    gdgt2,
    gdgt3,
    cren,
    cren_prime,
    *,
    cren_weight: float = 3,
    cren_rings: int = None,
) -> np.ndarray:
    """
    Compute Scaled Ring Index from six isoGDGT abundances.

    Accepts raw LC/MS peak areas or fractional abundances — both give identical
    results because the formula divides by the total sum of all six GDGTs, so
    any common scale factor drops out.
    Default ``cren_weight=3`` produces **scaledRI_cren3** (RI₀₋₃), the canonical
    proxy used in TEXAS calibration posteriors.

    Parameters
    ----------
    gdgt0, gdgt1, gdgt2, gdgt3, cren, cren_prime : float or array-like
        isoGDGT abundances — GDGT-0, GDGT-1, GDGT-2, GDGT-3, crenarchaeol,
        crenarchaeol regioisomer (cren').  Raw LC/MS peak areas and fractional
        abundances give the same result (see above).
    cren_weight : float
        Weight carried by both crenarchaeol and its regioisomer, which also
        sets the normalisation (see Notes).
        ``3`` → scaledRI_cren3 / RI₀₋₃ (default, recommended).
        ``4`` → scaledRI / RI₀₋₄ (Zhang et al. 2016 convention).
    cren_rings : int, optional
        Deprecated alias for ``cren_weight``. Emits a ``DeprecationWarning``.

    Returns
    -------
    numpy.ndarray or float
        Scaled Ring Index, dimensionless, nominally in [0, 1].

    Notes
    -----
    The formula is::

        RI      = (1·GDGT1 + 2·GDGT2 + 3·GDGT3 + cren_weight·cren + cren_weight·cren')
                  / (GDGT0 + GDGT1 + GDGT2 + GDGT3 + cren + cren')
        scaledRI = RI / cren_weight

    The parameter does two jobs at once: it is the coefficient on cren and
    cren' in the numerator *and* the constant the whole index is divided by, so
    it fixes the scale on which every sample is expressed, not just the two
    crenarchaeol terms. That second job is what makes a value chosen here part
    of the proxy's definition rather than a detail — a posterior calibrated at
    3 cannot read an index built at 4.

    It was called ``cren_rings`` until 2026-08-21, which was misleading twice
    over:
    it named only the first job, and it implied a count of cyclic moieties.
    Neither 3 nor 4 is that count. They are calibration conventions, which is
    why both are offered and why neither is "correct".

    Examples
    --------
    >>> compute_scaledRI(0.45, 0.10, 0.08, 0.05, 0.30, 0.02)
    array(0.45666...)

    >>> import pandas as pd
    >>> df = pd.read_csv("my_gdgt_data.csv")
    >>> df["scaledRI_cren3"] = compute_scaledRI(
    ...     df["GDGT-0"], df["GDGT-1"], df["GDGT-2"], df["GDGT-3"],
    ...     df["cren"],   df["cren_prime"],
    ... )
    """
    if cren_rings is not None:
        import warnings
        warnings.warn(
            "compute_scaledRI(cren_rings=...) is deprecated; use "
            "'cren_weight' instead. The value is a weight and a normalisation "
            "constant, not a count of rings.",
            DeprecationWarning, stacklevel=2,
        )
        cren_weight = cren_rings

    g0 = np.asarray(gdgt0, dtype=float)
    g1 = np.asarray(gdgt1, dtype=float)
    g2 = np.asarray(gdgt2, dtype=float)
    g3 = np.asarray(gdgt3, dtype=float)
    cr = np.asarray(cren, dtype=float)
    cp = np.asarray(cren_prime, dtype=float)

    numerator = g1 + 2 * g2 + 3 * g3 + cren_weight * cr + cren_weight * cp
    denominator = (g0 + g1 + g2 + g3 + cr + cp) * cren_weight
    return numerator / denominator


