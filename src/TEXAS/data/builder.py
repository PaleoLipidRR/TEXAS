# TEXAS/data/builder.py

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
    mode: str = "ensemble"        # Only 'ensemble' is supported
    n_draws: int = 100            # Size of the forward-parameter ensemble (M)
    seed: int = 42
    no3_cutoff: Optional[float] = 0.0
    suffix: Optional[str] = None   # Force a specific fwd parameter suffix

# Core forward parameters always required from the forward posterior
_FORWARD_PARAMS = ["t0", "k", "b"]
# Extra params for generalized logistic models (optional)
_EXTRA_PARAMS = ["v", "Q"]

def build_invT_inputData(
    scaledRI: Union[np.ndarray, List[float]],
    prior_mu_t: Union[np.ndarray, float],
    prior_sigma_t: float,
    fwd_posterior_name: str,
    predictors: Optional[Dict[str, np.ndarray]] = None,
    config: Optional[InvTConfig] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Build the `data` dictionary for Stan and a `sampler_kwargs` dictionary.
    """
    config = config or InvTConfig()
    np.random.seed(config.seed)
    predictors = predictors or {}

    post: xr.Dataset = load_posterior(fwd_posterior_name)
    vars_ = list(post.data_vars)

    
    # Flatten chains and draws if they exist, otherwise identify the draw dimension.
    if "chain" in post.dims:
        post = post.stack(sample=("chain", "draw")).reset_index("sample")
        draw_dim_name = "sample"
    else:
        # If no 'chain' dim, the main sampling dim is likely 'draw' or 'sample'
        if "sample" in post.dims:
            draw_dim_name = "sample"
        elif "draw" in post.dims:
            draw_dim_name = "draw"
        else:
            raise ValueError("Could not find a 'draw' or 'sample' dimension in the posterior file.")
    

    # ------------------ Prepare core inputs ------------------
    y = np.asarray(scaledRI, dtype=float)
    N = y.size

    mu_t = (np.full(N, float(prior_mu_t))
            if np.isscalar(prior_mu_t)
            else np.asarray(prior_mu_t, dtype=float))
    if mu_t.shape[0] != N:
        raise ValueError(f"prior_mu_t length ({mu_t.shape[0]}) must match scaledRI length ({N})")

    if config.mode != "ensemble":
        raise NotImplementedError(f"Only 'ensemble' mode is supported, not '{config.mode}'")

    # ----- Select the correct forward parameter suffix -----
    PRIORITY_SUFFIXES = ["crtp", "culmesocore", "culmes", "meso", "cul"]
    used_suffix = config.suffix
    if not used_suffix:
        for sfx in PRIORITY_SUFFIXES:
            if all(f"{p}_{sfx}" in vars_ for p in _FORWARD_PARAMS):
                used_suffix = sfx
                break
        if not used_suffix:
            raise ValueError("Could not find a valid parameter suffix in the forward posterior.")
    else:
        missing = [v for v in [f"{p}_{used_suffix}" for p in _FORWARD_PARAMS] if v not in vars_]
        if missing:
            raise ValueError(f"User suffix '{used_suffix}' is missing required parameters: {missing}")
    
    # ------------------ Draw parameter ensemble ------------------
    # This now correctly uses the identified draw dimension name
    draw_indices = np.random.choice(post.dims[draw_dim_name], config.n_draws, replace=True)
    P = post.isel({draw_dim_name: draw_indices})

    data: Dict[str, Any] = {
        "N": N, "scaledRI": y, "prior_mu_t": mu_t,
        "prior_sigma_t": float(prior_sigma_t), "M": int(config.n_draws),
    }

    used_posts: List[str] = []
    
    # These arrays will now be correctly shaped (M,) from the start.
    for p in _FORWARD_PARAMS:
        key = f"{p}_{used_suffix}"
        data[p] = np.asarray(P[key].values, dtype=float)
        used_posts.append(key)

    for p in _EXTRA_PARAMS:
        key = f"{p}_{used_suffix}"
        if key in P:
            data[p] = np.asarray(P[key].values, dtype=float)
            used_posts.append(key)

    sigma_key = f"sigma_scaledRI_{used_suffix}"
    if sigma_key in P:
        data["sigma_scaledRI"] = np.asarray(P[sigma_key].values, dtype=float)
        used_posts.append(sigma_key)
    else:
        data["sigma_scaledRI"] = np.full(config.n_draws, 0.1, dtype=float)

    # ------------------ Process optional predictors ------------------
    predictor_usage = {}
    for pred in OPTIONAL_PREDICTORS:
        use_flag = bool(post.attrs.get(f"use_{pred}", False))
        predictor_usage[pred] = use_flag
        
        arr = ensure_numpy(predictors.get(pred, np.zeros(N, dtype=float)))
        if arr.shape[0] != N:
            raise ValueError(f"Predictor '{pred}' length ({arr.shape[0]}) must equal N ({N})")
        
        data[pred] = arr
        data[f"use_{pred}"] = 1 if use_flag else 0
        
        if use_flag:
            beta_key = f"beta0_{pred}_{used_suffix}"
            if beta_key not in P:
                raise ValueError(f"Expected '{beta_key}' in forward posterior but not found.")
            data[f"beta0_{pred}"] = np.asarray(P[beta_key].values, dtype=float)
            used_posts.append(beta_key)

    # Handle special logic for the nitrate cutoff
    if data.get("use_no3"):
        if np.allclose(data["no3"], 0):
            data["no3_cutoff"] = 0.0
        else:
            # 1. Prioritize the cutoff from the forward posterior's attributes.
            cutoff_from_attrs = post.attrs.get("no3_cutoff")
            
            if cutoff_from_attrs is not None:
                final_cutoff = float(cutoff_from_attrs)
                print(f"💡 Using no3_cutoff from forward posterior attributes: {final_cutoff}")
            # 2. Fallback to the InvTConfig object if not found in attributes.
            elif config.no3_cutoff is not None:
                final_cutoff = config.no3_cutoff
                print(f"💡 Using no3_cutoff from InvTConfig: {final_cutoff}")
            # 3. If neither is available, use a default and warn the user.
            else:
                final_cutoff = 0.0
                print(f"⚠️ no3_cutoff not specified. Using default value: {final_cutoff}")
            
            data["no3_cutoff"] = final_cutoff
    else:
        data["no3_cutoff"] = 0.0

    # Sampler kwargs with metadata for downstream use
    sampler_kwargs: Dict[str, Any] = {
        "chains": 4, "iter_warmup": 500, "iter_sampling": 1000,
        "seed": int(config.seed),
        "_metadata": {
            "posteriors_used": used_posts,
            "calibration_model_name": post.attrs.get("stan_model_name", ""),
            "used_suffix": used_suffix,
            "predictor_usage": predictor_usage,
        },
    }

    return data, sampler_kwargs