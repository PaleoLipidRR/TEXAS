# TEXAS/ensemble/detection.py

import xarray as xr
from ..models.logistics import (
    logistic_fixed_upper,
    generalized_logistic_fixed_upper,
)
from ..models.multivariate import (
    simple_logistic_fixed_upper_multivariate,
    generalized_logistic_fixed_upper_multivariate,
)

def detect_model_and_params(posterior_ds: xr.Dataset, suffix: str):
    """
    Decide between simple vs generalized vs multivariate logistic:
      - checks for v/Q to pick generalized vs simple
      - checks for beta0_ predictors to pick multivariate variants

    Returns
    -------
    dict with keys:
      'model_function': callable,
      'param_names': List[str]
    """
    vars_ = set(posterior_ds.data_vars)
    has_v   = f"v_{suffix}" in vars_
    has_Q   = f"Q_{suffix}" in vars_
    has_gdz = f"beta0_gdgt23ratio_{suffix}" in vars_
    has_no3 = f"beta0_no3_{suffix}" in vars_

    if has_v and has_Q:
        # generalized logistic
        if has_gdz or has_no3:
            model_fn   = generalized_logistic_fixed_upper_multivariate
            params     = ["t0", "b", "k", "v", "Q"]
            if has_gdz:  params.append("beta0_gdgt23ratio")
            if has_no3:  params.append("beta0_no3")
        else:
            model_fn   = generalized_logistic_fixed_upper
            params     = ["t0", "b", "k", "v", "Q"]
    else:
        # simple logistic
        if has_gdz or has_no3:
            model_fn   = simple_logistic_fixed_upper_multivariate
            params     = ["t0", "b", "k"]
            if has_gdz:  params.append("beta0_gdgt23ratio")
            if has_no3:  params.append("beta0_no3")
        else:
            model_fn   = logistic_fixed_upper
            params     = ["t0", "b", "k"]

    return {
        "model_function": model_fn,
        "param_names":    params,
    }
