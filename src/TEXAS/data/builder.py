# TEXAS/data/builder.py
"""
Data builder for inverse temperature (invT) models.

This module bridges the FORWARD and INVERSE calibration models:
  1. Loads posterior samples from a completed forward calibration
  2. Randomly samples M parameter sets from that posterior
  3. Packages them as FIXED DATA for the inverse Stan model

The inverse model then marginalizes over these M samples to predict
temperature from observed Ring Index values.
"""

from typing import Dict, Optional, List, Union, Tuple, Any
from dataclasses import dataclass

import numpy as np
import xarray as xr

from TEXAS.constants import OPTIONAL_PREDICTORS, PREDICTOR_BETA_NAMES
from TEXAS.data.filter import ensure_numpy
from TEXAS.stan.io import load_posterior

@dataclass
class InvTConfig:
    """Configuration for the inverse-T Stan data builder."""
    mode: str = "ensemble"        # Only 'ensemble' is supported (historical artifact)
    n_draws: Optional[int] = None # Number of forward posterior samples (M).
                                  # None → auto: min(available_draws, 300).
                                  # Larger M → better marginal likelihood approximation
                                  # (error ∝ 1/√M) but proportionally slower inference.
                                  # Recommended: 100 (quick), 300 (default), 500 (publication).
    seed: int = 42                # For reproducible sampling of M draws
    no3_cutoff: Optional[float] = 0.0
    suffix: Optional[str] = None   # Force a specific fwd parameter suffix (e.g., 'crtp')

# ═══════════════════════════════════════════════════════════════════════════════
# PARAMETER NAMING CONVENTIONS
# ═══════════════════════════════════════════════════════════════════════════════
# Core forward parameters always required from the forward posterior
_FORWARD_PARAMS = ["t0", "k", "b"]  # Generalized logistic core parameters

# Extra params for generalized logistic models (optional, depending on model)
_EXTRA_PARAMS = ["v"]  # Shape parameter (Q is fixed to 1 in all active models)


def build_invT_inputData(
    proxyObs: Union[np.ndarray, List[float]] = None,
    prior_mu_t: Union[np.ndarray, float] = None,
    prior_sigma_t: float = None,
    *,
    scaledRI: Union[np.ndarray, List[float]] = None,  # deprecated alias
    fwd_posterior_name: Optional[str] = None,
    predictors: Optional[Dict[str, np.ndarray]] = None,
    config: Optional[InvTConfig] = None,
    fwd_posterior: Optional[xr.Dataset] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Build the `data` dictionary for Stan's inverse model and sampler configuration.

    WORKFLOW:
    ─────────
    1. Load forward calibration posterior from .nc file (or accept a pre-loaded Dataset)
    2. Randomly sample M parameter sets from that posterior
    3. Extract calibration curve parameters (t0, k, b, v, sigma)
    4. Package optional environmental predictors (GDGT-2/3, NO3) if used
    5. Return data dict (for Stan) + sampler_kwargs (for CmdStanPy)

    Args:
        proxyObs: Observed proxy values to predict temperature from (length N).
            Any proxy is accepted: scaledRI, TEX86, ringIndex, etc.
        prior_mu_t: Prior mean temperature (scalar or array of length N)
        prior_sigma_t: Prior temperature uncertainty (e.g., 10°C)
        fwd_posterior_name: Name of saved forward calibration (without .nc extension).
            Not required when fwd_posterior is supplied directly.
        predictors: Optional environmental covariates {'gdgt23ratio': array, 'no3': array}
        config: Configuration object controlling M, seed, etc.
        fwd_posterior: Pre-loaded forward posterior xr.Dataset. When provided,
            fwd_posterior_name is ignored and no file I/O is performed. Useful
            when running from Google Colab or any pip-install context where the
            posterior cache is not available.

    Returns:
        data: Dictionary for Stan's data block
        sampler_kwargs: Dictionary for CmdStanPy sampling configuration
    """
    # Backward-compat: accept deprecated scaledRI kwarg
    if scaledRI is not None and proxyObs is None:
        import warnings
        warnings.warn(
            "The 'scaledRI' parameter is deprecated; use 'proxyObs' instead.",
            DeprecationWarning, stacklevel=2,
        )
        proxyObs = scaledRI
    if proxyObs is None:
        raise TypeError("build_invT_inputData() missing required argument: 'proxyObs'")

    if fwd_posterior is None and fwd_posterior_name is None:
        raise ValueError(
            "Provide either fwd_posterior_name (cache lookup) "
            "or fwd_posterior (pre-loaded xr.Dataset)."
        )

    config = config or InvTConfig()
    np.random.seed(config.seed)  # Ensure reproducible M-sample selection
    predictors = predictors or {}

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 1: LOAD FORWARD CALIBRATION POSTERIOR
    # ═══════════════════════════════════════════════════════════════════════════
    # Accept a pre-loaded Dataset (fwd_posterior) or load from the cache by name.
    # Expected structure: xr.Dataset with dims (chain, draw) and data_vars like:
    #   - t0_crtp, k_crtp, b_crtp, v_crtp, sigma_proxyObs_crtp
    #   - beta_G23_crtp, beta_NO3_crtp (if multivariate)
    # ───────────────────────────────────────────────────────────────────────────
    if fwd_posterior is not None:
        post: xr.Dataset = fwd_posterior
    else:
        post: xr.Dataset = load_posterior(fwd_posterior_name)
    vars_ = list(post.data_vars)

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 2: FLATTEN MCMC DIMENSIONS (chain, draw) → (sample)
    # ═══════════════════════════════════════════════════════════════════════════
    # Stan posteriors have shape (chain, draw, ...). We flatten to a single
    # dimension 'sample' so we can randomly select M draws across all chains.
    # ───────────────────────────────────────────────────────────────────────────
    if "chain" in post.dims:
        # Standard case: (chain, draw) → (sample)
        post = post.stack(sample=("chain", "draw")).reset_index("sample")
        draw_dim_name = "sample"
    else:
        # Edge case: already flattened or single-chain posterior
        if "sample" in post.dims:
            draw_dim_name = "sample"
        elif "draw" in post.dims:
            draw_dim_name = "draw"
        else:
            raise ValueError("Could not find a 'draw' or 'sample' dimension in the posterior file.")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 3: PREPARE OBSERVATION DATA
    # ═══════════════════════════════════════════════════════════════════════════
    y = np.asarray(proxyObs, dtype=float)  # Observed proxy values
    N = y.size  # Number of observations (e.g., coretop samples or PETM section)

    # Prior on temperature: Can be scalar (same prior for all N) or array (site-specific)
    mu_t = (np.full(N, float(prior_mu_t))
            if np.isscalar(prior_mu_t)
            else np.asarray(prior_mu_t, dtype=float))
    if mu_t.shape[0] != N:
        raise ValueError(f"prior_mu_t length ({mu_t.shape[0]}) must match proxyObs length ({N})")

    if config.mode != "ensemble":
        raise NotImplementedError(f"Only 'ensemble' mode is supported, not '{config.mode}'")

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 4: IDENTIFY PARAMETER SUFFIX
    # ═══════════════════════════════════════════════════════════════════════════
    # Forward models may produce parameters like:
    #   - t0_crtp, k_crtp (coretop-only calibration)
    #   - t0_culmesocore, k_culmesocore (culture+mesocosm+coretop)
    # We prioritize higher-data combinations (crtp > culmesocore > culmes > ...)
    # ───────────────────────────────────────────────────────────────────────────
    PRIORITY_SUFFIXES = ["crtp", "culmesocore", "culmes", "meso", "cul"]
    used_suffix = config.suffix
    if not used_suffix:
        # Auto-detect the highest-priority suffix present in the posterior
        for sfx in PRIORITY_SUFFIXES:
            if all(f"{p}_{sfx}" in vars_ for p in _FORWARD_PARAMS):
                used_suffix = sfx
                break
        if not used_suffix:
            raise ValueError("Could not find a valid parameter suffix in the forward posterior.")
    else:
        # User specified a suffix - verify it exists
        missing = [v for v in [f"{p}_{used_suffix}" for p in _FORWARD_PARAMS] if v not in vars_]
        if missing:
            raise ValueError(f"User suffix '{used_suffix}' is missing required parameters: {missing}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 5: RANDOMLY SAMPLE M PARAMETER SETS FROM THE FORWARD POSTERIOR
    # ═══════════════════════════════════════════════════════════════════════════
    # This is the KEY STEP for Bayesian uncertainty propagation!
    # 
    # Instead of using a single "best-fit" calibration, we randomly draw M
    # plausible calibration curves from the forward posterior. Each draw m
    # represents one self-consistent set of parameters {t0, k, b, v, sigma}.
    # 
    # The inverse model averages predictions across all M draws, naturally
    # accounting for calibration uncertainty.
    # ───────────────────────────────────────────────────────────────────────────
    total_available = post.dims[draw_dim_name]

    if config.n_draws is None:
        # Auto-select M: use up to 25% of available draws, bounded [100, 500].
        # 300 is the ceiling for typical runs (4 chains × 1000 = 4000 draws →
        # M=300 gives ~5.8% Monte Carlo error; sufficient for publication quality).
        M = min(500, max(100, total_available // 4))
        print(
            f"⚙️  Auto M={M} ({total_available} posterior draws available; "
            f"approx. error ≈ {100/M**0.5:.1f}%). "
            f"Override with InvTConfig(n_draws=...)."
        )
    else:
        M = config.n_draws
        if M > total_available:
            print(
                f"⚠️  n_draws={M} exceeds available draws ({total_available}); "
                f"sampling with replacement (draws will repeat)."
            )

    draw_indices = np.random.choice(total_available, M, replace=True)
    P = post.isel({draw_dim_name: draw_indices})  # Subset to M samples
    # Now P has shape (sample=M, ...) instead of (sample=total_available, ...)

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 6: INITIALIZE DATA DICTIONARY FOR STAN
    # ═══════════════════════════════════════════════════════════════════════════
    data: Dict[str, Any] = {
        "N": N,                     # Number of observations
        "proxyObs": y,              # Observed proxy values
        "prior_mu_t": mu_t,         # Prior temperature mean
        "prior_sigma_t": float(prior_sigma_t),  # Prior temperature uncertainty
        "M": M,                     # Number of forward posterior samples
    }

    used_posts: List[str] = []  # Track which parameters were extracted
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 7: EXTRACT CORE CALIBRATION PARAMETERS
    # ═══════════════════════════════════════════════════════════════════════════
    # Extract the M samples of each core parameter:
    #   t0[m] = inflection temperature for draw m
    #   k[m]  = growth rate for draw m
    #   b[m]  = lower asymptote for draw m
    # These will be passed to Stan as FIXED data (not sampled again).
    # ───────────────────────────────────────────────────────────────────────────
    for p in _FORWARD_PARAMS:
        key = f"{p}_{used_suffix}"  # e.g., "t0_crtp"
        data[p] = np.asarray(P[key].values, dtype=float)  # Shape: (M,)
        used_posts.append(key)

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 8: EXTRACT EXTRA PARAMETERS (v) IF PRESENT
    # ═══════════════════════════════════════════════════════════════════════════
    # Generalized logistic models include v (shape) parameter. Q is fixed to 1
    # in all active models and is no longer sampled or passed to invT Stan models.
    # Standard logistic models also fix v=1 and don't include it in the posterior.
    # ───────────────────────────────────────────────────────────────────────────
    for p in _EXTRA_PARAMS:
        key = f"{p}_{used_suffix}"
        if key in P:
            data[p] = np.asarray(P[key].values, dtype=float)  # Shape: (M,)
            used_posts.append(key)

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 9: EXTRACT RESIDUAL ERROR PARAMETER
    # ═══════════════════════════════════════════════════════════════════════════
    # sigma_proxyObs[m] = measurement/model error for calibration sample m
    # If not available in posterior, use a default value.
    # ───────────────────────────────────────────────────────────────────────────
    sigma_key = f"sigma_proxyObs_{used_suffix}"
    if sigma_key not in P:
        sigma_key = f"sigma_scaledRI_{used_suffix}"  # backward compat with old posteriors
    if sigma_key in P:
        data["sigma_proxyObs"] = np.asarray(P[sigma_key].values, dtype=float)  # Shape: (M,)
        used_posts.append(sigma_key)
    else:
        # Fallback to constant error if not estimated in forward model
        data["sigma_proxyObs"] = np.full(M, 0.1, dtype=float)

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 10: PROCESS OPTIONAL ENVIRONMENTAL PREDICTORS
    # ═══════════════════════════════════════════════════════════════════════════
    # If the forward model included environmental covariates (GDGT-2/3, NO3),
    # we need to:
    #   1. Extract their coefficients (beta0) from the forward posterior
    #   2. Pass the observed predictor values for our N observations
    #   3. Set use_* flags so Stan knows to apply nonthermal corrections
    # ───────────────────────────────────────────────────────────────────────────
    predictor_usage = {}
    for pred in OPTIONAL_PREDICTORS:  # ['gdgt23ratio', 'no3']
        # Check if this predictor was used in the forward calibration
        use_flag = bool(post.attrs.get(f"use_{pred}", False))
        predictor_usage[pred] = use_flag
        
        # Get observed predictor values for our N observations (or zeros if not provided)
        arr = ensure_numpy(predictors.get(pred, np.zeros(N, dtype=float)))
        if arr.shape[0] != N:
            raise ValueError(f"Predictor '{pred}' length ({arr.shape[0]}) must equal N ({N})")
        
        # Add to Stan data
        data[pred] = arr  # Observed predictor values: shape (N,)
        data[f"use_{pred}"] = 1 if use_flag else 0  # Flag for Stan conditional logic
        
        # Stan always expects beta_G23 and beta_NO3 as vector[M], even when the
        # predictor is disabled (use_* = 0). Provide zeros when not used so the
        # data block dimensions match regardless of which predictors are active.
        beta_name = PREDICTOR_BETA_NAMES[pred]          # e.g., "beta_G23"
        if use_flag:
            # Extract the coefficient from forward posterior
            beta_key = f"{beta_name}_{used_suffix}"          # e.g., "beta_G23_crtp"
            if beta_key not in P:
                raise ValueError(f"Expected '{beta_key}' in forward posterior but not found.")
            data[beta_name] = np.asarray(P[beta_key].values, dtype=float)  # Shape: (M,)
            used_posts.append(beta_key)
        else:
            # Predictor unused → pass zeros so Stan's vector[M] declaration is satisfied
            data[beta_name] = np.zeros(M, dtype=float)  # Shape: (M,)

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 11: HANDLE NITRATE CUTOFF (Special case for NO3 predictor)
    # ═══════════════════════════════════════════════════════════════════════════
    # NO3 uses a threshold model: correction only applies when NO3 > cutoff.
    # Priority: (1) forward posterior attrs, (2) InvTConfig, (3) default 0.0
    # ───────────────────────────────────────────────────────────────────────────
    if data.get("use_no3"):
        if np.allclose(data["no3"], 0):
            # All NO3 values are zero → no correction needed
            data["no3_cutoff"] = 0.0
        else:
            # 1. Try to get cutoff from forward posterior attributes
            cutoff_from_attrs = post.attrs.get("no3_cutoff")
            
            if cutoff_from_attrs is not None:
                final_cutoff = float(cutoff_from_attrs)
                print(f"💡 Using no3_cutoff from forward posterior attributes: {final_cutoff}")
            # 2. Fallback to InvTConfig if not in attributes
            elif config.no3_cutoff is not None:
                final_cutoff = config.no3_cutoff
                print(f"💡 Using no3_cutoff from InvTConfig: {final_cutoff}")
            # 3. Default to 0.0 if neither source available
            else:
                final_cutoff = 0.0
                print(f"⚠️ no3_cutoff not specified. Using default value: {final_cutoff}")
            
            data["no3_cutoff"] = final_cutoff
    else:
        # NO3 not used → cutoff irrelevant
        data["no3_cutoff"] = 0.0

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 12: PACKAGE SAMPLER CONFIGURATION AND METADATA
    # ═══════════════════════════════════════════════════════════════════════════
    # Return both the Stan data and configuration for CmdStanPy.
    # Metadata helps with provenance tracking and debugging.
    # ───────────────────────────────────────────────────────────────────────────
    fwd_model_name = post.attrs.get("stan_model_name", "")
    sampler_kwargs: Dict[str, Any] = {
        "chains": 4,           # Number of MCMC chains
        "iter_warmup": 500,    # Warmup iterations per chain
        "iter_sampling": 1000, # Sampling iterations per chain
        "seed": int(config.seed),
        "_metadata": {
            "posteriors_used": used_posts,  # Which parameters were extracted
            "calibration_model_name": fwd_model_name,
            "used_suffix": used_suffix,  # e.g., "crtp"
            "predictor_usage": predictor_usage,  # Which covariates are active
            "no3ratio": "_no3ratio" in fwd_model_name,  # Forward model used centred NO₃ form
        },
    }

    return data, sampler_kwargs


# ═══════════════════════════════════════════════════════════════════════════════
# FORWARD CALIBRATION DATA BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

_FWD_HYPERPARAMS = ["t0", "k", "b", "v"]


def _fit_gen_logi_to_get_residuals(t: np.ndarray, proxy: np.ndarray) -> np.ndarray:
    """
    Fit generalized logistic (fixed upper asymptote = 1) to (t, proxy) and
    return residuals (proxy − predicted). Used internally to compute the
    temperature-only baseline before finding the optimal NO3 threshold.
    """
    from scipy.optimize import curve_fit
    from TEXAS.models.logistics import generalized_logistic_fixed_upper

    def _model(x, t0, b, k, v):
        return generalized_logistic_fixed_upper(x, t0=t0, b=b, k=k, v=v, Q=1.0)

    try:
        popt, _ = curve_fit(
            _model, t, proxy,
            p0=[25.0, 0.2, 0.04, 1.0],
            bounds=([-5, 0.001, 1e-4, 0.01], [50, 0.99, 2.0, 50.0]),
            maxfev=20000,
        )
        return proxy - _model(t, *popt)
    except RuntimeError as e:
        raise RuntimeError(
            f"Generalized logistic fit failed while computing residuals for NO3 "
            f"threshold calculation: {e}\n"
            "Pass proxy_residuals_crtp= to provide pre-computed residuals."
        )


def _auto_no3_cutoff(
    no3: np.ndarray,
    t_crtp: np.ndarray,
    proxy_crtp: np.ndarray,
    proxy_residuals: Optional[np.ndarray] = None,
) -> float:
    """
    Auto-calculate no3_cutoff via find_optimal_no3_threshold (Spearman method).
    NaN rows are dropped across all arrays before scoring.
    """
    from TEXAS.models.multivariate import find_optimal_no3_threshold

    if proxy_residuals is not None:
        stack = np.column_stack([no3, proxy_residuals])
        valid = np.all(np.isfinite(stack), axis=1)
        no3_clean = no3[valid]
        res_clean = proxy_residuals[valid]
        n_excluded = int((~valid).sum())
        if n_excluded:
            print(f"      ({n_excluded} samples excluded due to NaN values)")
    else:
        stack = np.column_stack([no3, t_crtp, proxy_crtp])
        valid = np.all(np.isfinite(stack), axis=1)
        no3_clean = no3[valid]
        t_clean = t_crtp[valid]
        proxy_clean = proxy_crtp[valid]
        n_excluded = int((~valid).sum())
        print(
            f"      Computing proxy residuals from generalized logistic fit "
            f"(N={int(valid.sum())}/{len(no3)} samples"
            + (f", {n_excluded} excluded with NaN NO3)" if n_excluded else ")")
        )
        res_clean = _fit_gen_logi_to_get_residuals(t_clean, proxy_clean)

    optimal_cutoff, _ = find_optimal_no3_threshold(
        no3_values=no3_clean,
        residuals=res_clean,
        score_method="spearmanr",
    )
    return round(float(optimal_cutoff), 1)


def _extract_culmeso_hyperpriors(posterior: xr.Dataset) -> Dict[str, Any]:
    """
    Extract prior_mean_* / prior_sd_* hyperpriors from a culmeso forward posterior.
    Returns a dict with those keys plus '_suffix' and '_n_draws' for logging.
    """
    vars_ = list(posterior.data_vars)
    used_suffix = None
    for sfx in ["culmeso", "culmesocore", "crtp", "meso", "cul"]:
        if f"t0_{sfx}" in vars_:
            used_suffix = sfx
            break
    if not used_suffix:
        raise ValueError(
            "Cannot find a parameter suffix in culmeso_posterior "
            "(expected e.g. t0_culmeso). Check that you passed the correct dataset."
        )

    if "chain" in posterior.dims:
        flat = posterior.stack(sample=("chain", "draw")).reset_index("sample")
        n_draws = int(flat.dims["sample"])
    elif "sample" in posterior.dims:
        flat, n_draws = posterior, int(posterior.dims["sample"])
    elif "draw" in posterior.dims:
        flat, n_draws = posterior, int(posterior.dims["draw"])
    else:
        raise ValueError("Cannot find a draw dimension in culmeso_posterior.")

    result: Dict[str, Any] = {"_suffix": used_suffix, "_n_draws": n_draws}
    for p in _FWD_HYPERPARAMS:
        key = f"{p}_{used_suffix}"
        if key in flat:
            vals = flat[key].values.ravel()
            result[f"prior_mean_{p}"] = float(np.mean(vals))
            result[f"prior_sd_{p}"]  = float(np.std(vals))
    return result


def build_fwd_data(
    *,
    # Culture observations
    t_cul=None,
    proxy_cul=None,
    # Mesocosm observations
    t_meso=None,
    proxy_meso=None,
    # Coretop observations
    t_crtp=None,
    proxy_crtp=None,
    # Optional coretop predictors
    gdgt23ratio_crtp=None,
    no3_crtp=None,
    no3_cutoff: Optional[float] = None,
    proxy_residuals_crtp: Optional[np.ndarray] = None,
    # Stage-1 culmeso posterior — auto-extracts hyperpriors and no3_cutoff
    culmeso_posterior: Optional[xr.Dataset] = None,
    # Manual hyperprior overrides (alternative or supplement to culmeso_posterior)
    prior_mean_t0=None, prior_sd_t0=None,
    prior_mean_k=None,  prior_sd_k=None,
    prior_mean_b=None,  prior_sd_b=None,
    prior_mean_v=None,  prior_sd_v=None,
) -> Dict[str, Any]:
    """
    Build the Stan data dictionary for forward calibration models.

    Handles all forward model variants:
      - culmeso / Q1_culmeso / v1_culmeso  : pass t_cul, proxy_cul, t_meso, proxy_meso
      - culmesocore                         : add t_crtp, proxy_crtp
      - hier_crtp_multiv                    : add gdgt23ratio_crtp, no3_crtp
      - hier_crtp_multiv_priorApprox        : add culmeso_posterior (extracts hyperpriors)
      - hier_crtp_univ_priorApprox          : add culmeso_posterior (no predictors needed)

    Args:
        t_cul, proxy_cul:           Culture temperature and proxy arrays.
        t_meso, proxy_meso:         Mesocosm temperature and proxy arrays.
        t_crtp, proxy_crtp:         Coretop temperature and proxy arrays.
        gdgt23ratio_crtp:           GDGT-2/GDGT-3 ratio for coretop samples.
                                    Sets use_gdgt23ratio=1 if non-zero/non-NaN.
        no3_crtp:                   Nitrate concentration for coretop samples.
                                    Sets use_no3=1 if non-zero/non-NaN.
        no3_cutoff:                 NO3 threshold for the nonthermal correction.
                                    Priority: (1) this arg, (2) culmeso_posterior attrs,
                                    (3) auto-calculated via Spearman method.
        proxy_residuals_crtp:       Pre-computed proxy residuals for NO3 threshold
                                    calculation. If omitted, residuals are computed
                                    internally by fitting a generalized logistic curve.
                                    Warning: Stan models use generalized logistic — residuals
                                    from other functional forms may shift the threshold.
        culmeso_posterior:          xr.Dataset from a completed culmeso forward run.
                                    Auto-extracts prior_mean_*/prior_sd_* hyperpriors and
                                    no3_cutoff (if saved in attrs).
        prior_mean_*/prior_sd_*:    Manual hyperprior values. Override auto-extracted
                                    values from culmeso_posterior for individual params.

    Returns:
        dict: Stan-ready data dict with proxyObs_* keys, N_* counts, use_* flags,
              and hyperpriors — ready for get_posterior().
    """
    import warnings

    # ── Validate dataset pairs and sizes ──────────────────────────────────────
    _pairs = [
        ("culture",  "cul",  t_cul,  proxy_cul),
        ("mesocosm", "meso", t_meso, proxy_meso),
        ("coretop",  "crtp", t_crtp, proxy_crtp),
    ]
    for label, sfx, t, p in _pairs:
        if (t is None) != (p is None):
            raise ValueError(
                f"{label}: t_{sfx} and proxy_{sfx} must be provided together."
            )
        if t is not None and len(np.asarray(t)) != len(np.asarray(p)):
            raise ValueError(
                f"{label}: t_{sfx} (len={len(np.asarray(t))}) and "
                f"proxy_{sfx} (len={len(np.asarray(p))}) must have the same length."
            )

    if all(t is None for _, _, t, _ in _pairs):
        raise ValueError(
            "build_fwd_data() requires at least one dataset "
            "(culture, mesocosm, or coretop)."
        )
    if (gdgt23ratio_crtp is not None or no3_crtp is not None) and t_crtp is None:
        raise ValueError(
            "gdgt23ratio_crtp / no3_crtp require coretop data (t_crtp, proxy_crtp)."
        )

    # ── Build data dict ────────────────────────────────────────────────────────
    data: Dict[str, Any] = {}
    summary_lines: List[str] = []

    def _range_str(t_arr, p_arr):
        return (
            f"N={len(t_arr)}"
            f"  (t: {t_arr.min():.1f}–{t_arr.max():.1f}°C,"
            f" proxy: {p_arr.min():.3f}–{p_arr.max():.3f})"
        )

    # Culture
    if t_cul is not None:
        t_arr = np.asarray(t_cul, dtype=float)
        p_arr = np.asarray(proxy_cul, dtype=float)
        data.update({"N_cul": len(t_arr), "t_cul": t_arr, "proxyObs_cul": p_arr})
        summary_lines.append(f"   culture:   {_range_str(t_arr, p_arr)}")
    else:
        summary_lines.append("   culture:   —")

    # Mesocosm
    if t_meso is not None:
        t_arr = np.asarray(t_meso, dtype=float)
        p_arr = np.asarray(proxy_meso, dtype=float)
        data.update({"N_meso": len(t_arr), "t_meso": t_arr, "proxyObs_meso": p_arr})
        summary_lines.append(f"   mesocosm:  {_range_str(t_arr, p_arr)}")
    else:
        summary_lines.append("   mesocosm:  —")

    # Coretop + predictors
    if t_crtp is not None:
        t_arr  = np.asarray(t_crtp,    dtype=float)
        p_arr  = np.asarray(proxy_crtp, dtype=float)
        N_crtp = len(t_arr)
        data.update({"N_crtp": N_crtp, "t_crtp": t_arr, "proxyObs_crtp": p_arr})
        summary_lines.append(f"   coretop:   {_range_str(t_arr, p_arr)}")

        pred_parts: List[str] = []

        # GDGT-2/3 ratio
        if gdgt23ratio_crtp is not None:
            g_arr = np.asarray(gdgt23ratio_crtp, dtype=float)
            if len(g_arr) != N_crtp:
                raise ValueError(
                    f"gdgt23ratio_crtp length ({len(g_arr)}) != N_crtp ({N_crtp})."
                )
            use_g = int(not (np.all(np.isnan(g_arr)) or np.all(g_arr == 0)))
            data.update({"gdgt23ratio_crtp": g_arr, "use_gdgt23ratio": use_g})
            pred_parts.append(f"gdgt23ratio {'✓' if use_g else '✗'}")
        else:
            data.update({"gdgt23ratio_crtp": np.zeros(N_crtp), "use_gdgt23ratio": 0})

        # NO3
        if no3_crtp is not None:
            n_arr = np.asarray(no3_crtp, dtype=float)
            if len(n_arr) != N_crtp:
                raise ValueError(
                    f"no3_crtp length ({len(n_arr)}) != N_crtp ({N_crtp})."
                )
            use_n = int(not (np.all(np.isnan(n_arr)) or np.all(n_arr == 0)))
            data.update({"no3_crtp": n_arr, "use_no3": use_n})

            if use_n:
                # Determine no3_cutoff — priority: explicit > posterior attrs > auto-calc
                if no3_cutoff is not None:
                    final_cutoff  = float(no3_cutoff)
                    cutoff_source = "user-provided"
                elif (culmeso_posterior is not None
                      and culmeso_posterior.attrs.get("no3_cutoff") is not None):
                    final_cutoff  = float(culmeso_posterior.attrs["no3_cutoff"])
                    cutoff_source = "from culmeso_posterior attrs"
                else:
                    print("   🔍 Auto-calculating no3_cutoff (Spearman method)...")
                    if proxy_residuals_crtp is not None:
                        warnings.warn(
                            "Pre-computed proxy_residuals_crtp provided. "
                            "Note: Stan models use generalized logistic functional form — "
                            "residuals from other models may produce a suboptimal threshold.",
                            UserWarning, stacklevel=2,
                        )
                    final_cutoff = _auto_no3_cutoff(
                        n_arr, t_arr, p_arr,
                        proxy_residuals=proxy_residuals_crtp,
                    )
                    cutoff_source = "auto-calculated (Spearman)"
                    print(f"      → no3_cutoff = {final_cutoff:.3g} µmol/L")

                # Validate cutoff
                if final_cutoff <= 0:
                    warnings.warn(
                        f"no3_cutoff={final_cutoff} ≤ 0. _no3ratio Stan models require "
                        "cutoff > 0 (used as log10(no3/cutoff) denominator). "
                        "Specify a positive no3_cutoff= explicitly.",
                        UserWarning, stacklevel=2,
                    )
                no3_min = float(np.nanmin(n_arr))
                no3_max = float(np.nanmax(n_arr))
                if not (no3_min <= final_cutoff <= no3_max):
                    warnings.warn(
                        f"no3_cutoff={final_cutoff:.3g} is outside the range of no3_crtp "
                        f"({no3_min:.3g}–{no3_max:.3g} µmol/L). The NO3 correction may "
                        "not apply to any samples. Check your data or threshold value.",
                        UserWarning, stacklevel=2,
                    )

                data["no3_cutoff"] = final_cutoff
                pred_parts.append(
                    f"no3 ✓  (no3_cutoff={final_cutoff:.3g}, {cutoff_source})"
                )
            else:
                data["no3_cutoff"] = 0.0
                pred_parts.append("no3 ✗  (all zeros/NaN — correction disabled)")
        else:
            data.update({"no3_crtp": np.zeros(N_crtp), "use_no3": 0, "no3_cutoff": 0.0})

        summary_lines.append(
            f"   predictors: {', '.join(pred_parts) if pred_parts else 'none'}"
        )
    else:
        summary_lines.append("   coretop:   —")
        summary_lines.append("   predictors: none")

    # ── Hyperpriors ────────────────────────────────────────────────────────────
    manual_hp = {
        "prior_mean_t0": prior_mean_t0, "prior_sd_t0": prior_sd_t0,
        "prior_mean_k":  prior_mean_k,  "prior_sd_k":  prior_sd_k,
        "prior_mean_b":  prior_mean_b,  "prior_sd_b":  prior_sd_b,
        "prior_mean_v":  prior_mean_v,  "prior_sd_v":  prior_sd_v,
    }

    if culmeso_posterior is not None:
        hp      = _extract_culmeso_hyperpriors(culmeso_posterior)
        suffix  = hp.pop("_suffix")
        n_draws = hp.pop("_n_draws")
        data.update(hp)
        for k, v in manual_hp.items():   # manual overrides win
            if v is not None:
                data[k] = float(v)
        param_lines = [
            f"      {p}: mean={data[f'prior_mean_{p}']:.3g}  sd={data[f'prior_sd_{p}']:.3g}"
            for p in _FWD_HYPERPARAMS if f"prior_mean_{p}" in data
        ]
        summary_lines.append(
            f"   hyperpriors from culmeso posterior  (suffix={suffix}, {n_draws} draws):"
        )
        summary_lines.extend(param_lines)
    else:
        provided = {k: float(v) for k, v in manual_hp.items() if v is not None}
        data.update(provided)
        if provided:
            summary_lines.append("   hyperpriors: manual")
            for k, v in provided.items():
                summary_lines.append(f"      {k}: {v:.3g}")
        else:
            summary_lines.append("   hyperpriors: none")

    # ── Print summary ──────────────────────────────────────────────────────────
    print("📦 build_fwd_data summary:")
    for line in summary_lines:
        print(line)

    return data