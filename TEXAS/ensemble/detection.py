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
    If suffix is None, will guess based on a defined priority order.
    """
    vars_ = set(posterior_ds.data_vars)

    # Guess suffix if not given
    if suffix is None:
        # Define preferred suffix order
        priority_suffixes = ["crtp", "culmesocore", "culmeso", "meso", "cul", "univ"]

        # Gather suffixes present in the dataset
        available_suffixes = set()
        for v in vars_:
            if "_" in v:
                sfx = v.split("_")[-1]
                available_suffixes.add(sfx)

        # Choose the highest-priority available suffix
        for preferred in priority_suffixes:
            if preferred in available_suffixes:
                suffix = preferred
                break

        if suffix is None:
            raise ValueError("No recognized parameter suffixes found in posterior_ds")

    # Detect presence of optional parameters
    has_v   = f"v_{suffix}" in vars_
    has_Q   = f"Q_{suffix}" in vars_
    has_gdz = f"beta0_gdgt23ratio_{suffix}" in vars_
    has_no3 = f"beta0_no3_{suffix}" in vars_

    # Build param list and select model
    if has_v and has_Q:
        params = ["t0", "b", "k", "v", "Q"]
        if has_gdz: params.append("beta0_gdgt23ratio")
        if has_no3: params.append("beta0_no3")
        model_fn = (
            generalized_logistic_fixed_upper_multivariate
            if has_gdz or has_no3 else
            generalized_logistic_fixed_upper
        )
    else:
        params = ["t0", "b", "k"]
        if has_gdz: params.append("beta0_gdgt23ratio")
        if has_no3: params.append("beta0_no3")
        model_fn = (
            simple_logistic_fixed_upper_multivariate
            if has_gdz or has_no3 else
            logistic_fixed_upper
        )

    return {
        "model_function": model_fn,
        "param_names": params,
        "suffix": suffix,
    }
