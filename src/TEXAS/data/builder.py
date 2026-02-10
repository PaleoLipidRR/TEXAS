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

from TEXAS.constants import OPTIONAL_PREDICTORS
from TEXAS.data.filter import ensure_numpy
from TEXAS.stan.io import load_posterior

@dataclass
class InvTConfig:
    """Configuration for the inverse-T Stan data builder."""
    mode: str = "ensemble"        # Only 'ensemble' is supported (historical artifact)
    n_draws: int = 100            # Number of posterior samples to use (M)
                                  # Larger M → better approximation of integral
                                  # but slower inference
    seed: int = 42                # For reproducible sampling of M draws
    no3_cutoff: Optional[float] = 0.0
    suffix: Optional[str] = None   # Force a specific fwd parameter suffix (e.g., 'crtp')

# ═══════════════════════════════════════════════════════════════════════════════
# PARAMETER NAMING CONVENTIONS
# ═══════════════════════════════════════════════════════════════════════════════
# Core forward parameters always required from the forward posterior
_FORWARD_PARAMS = ["t0", "k", "b"]  # Generalized logistic core parameters

# Extra params for generalized logistic models (optional, depending on model)
_EXTRA_PARAMS = ["v", "Q"]  # Asymmetry and shape parameters


def build_invT_inputData(
    scaledRI: Union[np.ndarray, List[float]],
    prior_mu_t: Union[np.ndarray, float],
    prior_sigma_t: float,
    fwd_posterior_name: str,
    predictors: Optional[Dict[str, np.ndarray]] = None,
    config: Optional[InvTConfig] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Build the `data` dictionary for Stan's inverse model and sampler configuration.
    
    WORKFLOW:
    ─────────
    1. Load forward calibration posterior from .nc file
    2. Randomly sample M parameter sets from that posterior
    3. Extract calibration curve parameters (t0, k, b, Q, v, sigma)
    4. Package optional environmental predictors (GDGT-2/3, NO3) if used
    5. Return data dict (for Stan) + sampler_kwargs (for CmdStanPy)
    
    Args:
        scaledRI: Observed Ring Index values to predict temperature from (length N)
        prior_mu_t: Prior mean temperature (scalar or array of length N)
        prior_sigma_t: Prior temperature uncertainty (e.g., 10°C)
        fwd_posterior_name: Name of saved forward calibration (without .nc extension)
        predictors: Optional environmental covariates {'gdgt23ratio': array, 'no3': array}
        config: Configuration object controlling M, seed, etc.
    
    Returns:
        data: Dictionary for Stan's data block
        sampler_kwargs: Dictionary for CmdStanPy sampling configuration
    """
    config = config or InvTConfig()
    np.random.seed(config.seed)  # Ensure reproducible M-sample selection
    predictors = predictors or {}

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 1: LOAD FORWARD CALIBRATION POSTERIOR
    # ═══════════════════════════════════════════════════════════════════════════
    # This loads the .nc file produced by your forward TEXAS-Bay calibration.
    # Expected structure: xr.Dataset with dims (chain, draw) and data_vars like:
    #   - t0_crtp, k_crtp, b_crtp, v_crtp, Q_crtp, sigma_scaledRI_crtp
    #   - beta0_gdgt23ratio_crtp, beta0_no3_crtp (if multivariate)
    # ───────────────────────────────────────────────────────────────────────────
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
    y = np.asarray(scaledRI, dtype=float)  # Observed Ring Index (proxy data)
    N = y.size  # Number of observations (e.g., coretop samples or PETM section)

    # Prior on temperature: Can be scalar (same prior for all N) or array (site-specific)
    mu_t = (np.full(N, float(prior_mu_t))
            if np.isscalar(prior_mu_t)
            else np.asarray(prior_mu_t, dtype=float))
    if mu_t.shape[0] != N:
        raise ValueError(f"prior_mu_t length ({mu_t.shape[0]}) must match scaledRI length ({N})")

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
    # represents one self-consistent set of parameters {t0, k, b, Q, v, sigma}.
    # 
    # The inverse model will average predictions across all M draws, naturally
    # accounting for calibration uncertainty.
    # ───────────────────────────────────────────────────────────────────────────
    draw_indices = np.random.choice(post.dims[draw_dim_name], config.n_draws, replace=True)
    P = post.isel({draw_dim_name: draw_indices})  # Subset to M samples
    # Now P has shape (sample=M, ...) instead of (sample=4000, ...)

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 6: INITIALIZE DATA DICTIONARY FOR STAN
    # ═══════════════════════════════════════════════════════════════════════════
    data: Dict[str, Any] = {
        "N": N,                     # Number of observations
        "scaledRI": y,              # Observed Ring Index values
        "prior_mu_t": mu_t,         # Prior temperature mean
        "prior_sigma_t": float(prior_sigma_t),  # Prior temperature uncertainty
        "M": int(config.n_draws),   # Number of forward posterior samples
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
    # STEP 8: EXTRACT EXTRA PARAMETERS (v, Q) IF PRESENT
    # ═══════════════════════════════════════════════════════════════════════════
    # Generalized logistic models include v (shape) and Q (asymmetry) parameters.
    # Standard logistic models fix Q=1 and don't estimate v.
    # ───────────────────────────────────────────────────────────────────────────
    for p in _EXTRA_PARAMS:
        key = f"{p}_{used_suffix}"
        if key in P:
            data[p] = np.asarray(P[key].values, dtype=float)  # Shape: (M,)
            used_posts.append(key)

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 9: EXTRACT RESIDUAL ERROR PARAMETER
    # ═══════════════════════════════════════════════════════════════════════════
    # sigma_scaledRI[m] = measurement/model error for calibration sample m
    # If not available in posterior, use a default value.
    # ───────────────────────────────────────────────────────────────────────────
    sigma_key = f"sigma_scaledRI_{used_suffix}"
    if sigma_key in P:
        data["sigma_scaledRI"] = np.asarray(P[sigma_key].values, dtype=float)  # Shape: (M,)
        used_posts.append(sigma_key)
    else:
        # Fallback to constant error if not estimated in forward model
        data["sigma_scaledRI"] = np.full(config.n_draws, 0.1, dtype=float)

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
        
        if use_flag:
            # Extract the coefficient from forward posterior
            beta_key = f"beta0_{pred}_{used_suffix}"  # e.g., "beta0_gdgt23ratio_crtp"
            if beta_key not in P:
                raise ValueError(f"Expected '{beta_key}' in forward posterior but not found.")
            data[f"beta0_{pred}"] = np.asarray(P[beta_key].values, dtype=float)  # Shape: (M,)
            used_posts.append(beta_key)

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
    sampler_kwargs: Dict[str, Any] = {
        "chains": 4,           # Number of MCMC chains
        "iter_warmup": 500,    # Warmup iterations per chain
        "iter_sampling": 1000, # Sampling iterations per chain
        "seed": int(config.seed),
        "_metadata": {
            "posteriors_used": used_posts,  # Which parameters were extracted
            "calibration_model_name": post.attrs.get("stan_model_name", ""),
            "used_suffix": used_suffix,  # e.g., "crtp"
            "predictor_usage": predictor_usage,  # Which covariates are active
        },
    }

    return data, sampler_kwargs