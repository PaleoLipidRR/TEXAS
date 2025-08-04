import xarray as xr
from ..models.logistics import (
    logistic_fixed_upper,
    generalized_logistic_fixed_upper,
)
from ..models.multivariate import (
    simple_logistic_fixed_upper_multivariate,
    generalized_logistic_fixed_upper_multivariate,
)
from collections import Counter

def detect_model_and_params(posterior_ds: xr.Dataset, suffix: str = None):
    """
    Auto-detect which logistic model and parameters to use.
    If suffix is None, will guess the most common suffix in posterior_ds.
    """
    vars_ = set(posterior_ds.data_vars)
    # Guess suffix if not given
    if suffix is None:
        # Collect all suffixes for standard params
        all_suffixes = []
        for v in vars_:
            if "_" in v:
                sfx = v.split("_")[-1]
                all_suffixes.append(sfx)
        if not all_suffixes:
            raise ValueError("No parameters with suffix found in posterior_ds")
        suffix = Counter(all_suffixes).most_common(1)[0][0]

    # Detect presence
    has_v   = f"v_{suffix}" in vars_
    has_Q   = f"Q_{suffix}" in vars_
    has_gdz = f"beta0_gdgt23ratio_{suffix}" in vars_
    has_no3 = f"beta0_no3_{suffix}" in vars_

    # Build param list
    if has_v and has_Q:
        # generalized logistic
        params     = ["t0", "b", "k", "v", "Q"]
        if has_gdz:  params.append("beta0_gdgt23ratio")
        if has_no3:  params.append("beta0_no3")
        if has_gdz or has_no3:
            model_fn   = generalized_logistic_fixed_upper_multivariate
        else:
            model_fn   = generalized_logistic_fixed_upper
    else:
        params     = ["t0", "b", "k"]
        if has_gdz:  params.append("beta0_gdgt23ratio")
        if has_no3:  params.append("beta0_no3")
        if has_gdz or has_no3:
            model_fn   = simple_logistic_fixed_upper_multivariate
        else:
            model_fn   = logistic_fixed_upper

    return {
        "model_function": model_fn,
        "param_names":    params,
        "suffix":         suffix,
    }
