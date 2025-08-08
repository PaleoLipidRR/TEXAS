# TEXAS/data/builder.py

from typing import Dict, Optional, List, Union, Tuple
from dataclasses import dataclass

import numpy as np
import xarray as xr
import warnings

from TEXAS.constants import OPTIONAL_PREDICTORS
from TEXAS.data.filter import ensure_numpy
from TEXAS.stan.io import load_posterior

@dataclass
class InvTConfig:
    """Configuration for inverse-T Stan data builder (ensemble-only)."""
    mode: str = "ensemble"        # Only 'ensemble' is supported now
    n_draws: int = 100             # Size of forward-parameter ensemble (M)
    seed: int = 42
    no3_cutoff: Optional[float] = 0.0
    suffix: Optional[str] = None   # Force a specific suffix if provided

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
) -> Tuple[Dict[str, Union[int, float, np.ndarray]], Dict[str, object]]:
    """Build Stan `data` (ensemble mode only) and sampler kwargs."""
    config = config or InvTConfig()

    np.random.seed(config.seed)
    predictors = predictors or {}

    post: xr.Dataset = load_posterior(fwd_posterior_name)
    vars_ = list(post.data_vars)

    # ----------------------------- inputs -----------------------------
    y = np.asarray(scaledRI, dtype=float)
    N = y.size

    mu_t = (np.full(N, float(prior_mu_t))
            if np.isscalar(prior_mu_t)
            else np.asarray(prior_mu_t, dtype=float))
    if mu_t.shape[0] != N:
        raise ValueError("prior_mu_t length must match scaledRI length")

    if config.mode != "ensemble":
        raise ValueError(f"Only 'ensemble' mode is supported, but got: {config.mode}")

    # ------------------------- suffix selection ------------------------
    PRIORITY_SUFFIXES = ["crtp", "culmesocore", "culmes", "meso", "cul"]
    user_suffix = config.suffix

    if user_suffix:
        required_vars = [f"{p}_{user_suffix}" for p in _FORWARD_PARAMS]
        missing = [v for v in required_vars if v not in vars_]
        if missing:
            raise ValueError(
                f"User-specified suffix '{user_suffix}' is missing required parameters: {missing}"
            )
        used_suffix = user_suffix
    else:
        used_suffix = None
        for sfx in PRIORITY_SUFFIXES:
            if all(f"{p}_{sfx}" in vars_ for p in _FORWARD_PARAMS):
                used_suffix = sfx
                break
        if used_suffix is None:
            raise ValueError("Could not determine suffix for forward parameters from posterior.")

    # --------------------------- ensemble draw -------------------------
    draws = np.random.choice(post.dims["draw"], config.n_draws, replace=True)
    P = post.isel(draw=draws)

    data: Dict[str, Union[int, float, np.ndarray]] = {
        "N": N,
        "scaledRI": y,
        "prior_mu_t": mu_t,
        "prior_sigma_t": float(prior_sigma_t),
        "M": int(config.n_draws),
    }

    used_posts: List[str] = []

    # Required forward parameters
    for p in _FORWARD_PARAMS:
        key = f"{p}_{used_suffix}"
        if key not in P:
            raise ValueError(f"Required parameter missing in forward posterior: {key}")
        data[p] = np.asarray(P[key].values, dtype=float)
        used_posts.append(key)

    # Optional parameters (only include if present)
    for p in _EXTRA_PARAMS:
        key = f"{p}_{used_suffix}"
        if key in P:
            data[p] = np.asarray(P[key].values, dtype=float)
            used_posts.append(key)

    # sigma_scaledRI (fallback if missing)
    sigma_key = f"sigma_scaledRI_{used_suffix}"
    if sigma_key in P:
        data["sigma_scaledRI"] = np.asarray(P[sigma_key].values, dtype=float)
        used_posts.append(sigma_key)
    else:
        data["sigma_scaledRI"] = np.full(config.n_draws, 0.1, dtype=float)

    # Optional predictors
    predictor_usage = {}
    for pred in OPTIONAL_PREDICTORS:
        use_flag = bool(post.attrs.get(f"use_{pred}", False))

        arr = ensure_numpy(predictors.get(pred))
        if arr is None:
            arr = np.zeros(N, dtype=float)

        arr = np.asarray(arr, dtype=float)
        if arr.shape[0] != N:
            raise ValueError(f"Predictor `{pred}` length ({arr.shape[0]}) must equal N ({N})")

        data[pred] = arr
        predictor_usage[pred] = use_flag

        if use_flag:
            beta_key = f"beta0_{pred}_{used_suffix}"
            if beta_key not in P:
                raise ValueError(f"Expected {beta_key} in forward posterior but not found.")
            data[f"beta0_{pred}"] = np.asarray(P[beta_key].values, dtype=float)
            data[f"use_{pred}"] = 1
            used_posts.append(beta_key)
        else:
            data[f"use_{pred}"] = 0

    # Handle no3_cutoff logic
    if int(data.get("use_no3", 0)) == 1:
        if np.allclose(data["no3"], 0):
            # Predictor is all zeros → disable effect
            data["no3_cutoff"] = 0.0
        else:
            if config.no3_cutoff is not None:
                cutoff = float(config.no3_cutoff)
            else:
                cutoff = float(post.attrs.get("no3_cutoff", 50.0))  # fallback default
            data["no3_cutoff"] = cutoff
    else:
        data["no3_cutoff"] = 0.0

    # Sampler kwargs with predictor usage in metadata
    sampler_kwargs: Dict[str, object] = {
        "chains": 4,
        "iter_warmup": 500,
        "iter_sampling": 1000,
        "seed": int(config.seed),
        "_metadata": {
            "posteriors_used": used_posts,
            "calibration_model_name": post.attrs.get("stan_model_name", ""),
            "used_suffix": used_suffix,
            "predictor_usage": predictor_usage,  # ✅ New
        },
    }

    return data, sampler_kwargs
