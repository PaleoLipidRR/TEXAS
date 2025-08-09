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
from collections import Counter

# --- Shared suffix utilities ---
SUFFIX_PRIORITY = ["crtp", "culmesocore", "culmeso", "meso", "cul", "univ", ""]

def available_suffixes(posterior_ds: xr.Dataset, param_basenames):
    """
    Return a set of suffixes present for ANY of the given param basenames.
    Supports both 'base_suffix' and no-suffix ('base') styles.
    """
    vars_ = set(posterior_ds.data_vars)
    suffixes = set()
    for base in param_basenames:
        if base in vars_:
            suffixes.add("")  # no-suffix present
        prefix = f"{base}_"
        for v in vars_:
            if v.startswith(prefix):
                suffixes.add(v.split(prefix, 1)[1])
    return suffixes

def choose_suffix(posterior_ds: xr.Dataset, param_basenames, preferred: str | None = None):
    """
    Choose a suffix using global priority from SUFFIX_PRIORITY,
    constrained to suffixes that actually exist for the given basenames.
    If 'preferred' is supplied, require it to be present.
    """
    have = available_suffixes(posterior_ds, param_basenames)
    if preferred is not None:
        if preferred in have:
            return preferred
        raise ValueError(f"Requested suffix '{preferred}' not found. Available: {sorted(have)}")

    for s in SUFFIX_PRIORITY:
        if s in have:
            return s
    raise ValueError(f"No compatible suffix found. Available: {sorted(have)}")

def detect_model_and_params(posterior_ds: xr.Dataset, suffix: str = None):
    """
    Auto-detect which logistic model and parameters to use.
    Uses a shared suffix priority via choose_suffix().
    """
    vars_ = set(posterior_ds.data_vars)

    # Detect presence of optional parameter groups without assuming attrs
    has_v_any   = ("v" in vars_) or any(v.startswith("v_") for v in vars_)
    has_Q_any   = ("Q" in vars_) or any(v.startswith("Q_") for v in vars_)
    has_gdz_any = ("beta0_gdgt23ratio" in vars_) or any(v.startswith("beta0_gdgt23ratio_") for v in vars_)
    has_no3_any = ("beta0_no3" in vars_) or any(v.startswith("beta0_no3_") for v in vars_)

    # Build candidate basenames up-front for suffix selection
    basenames = ["t0", "b", "k"]
    if has_v_any and has_Q_any:
        basenames += ["v", "Q"]
    if has_gdz_any:
        basenames += ["beta0_gdgt23ratio"]
    if has_no3_any:
        basenames += ["beta0_no3"]

    # Choose suffix by priority (or validate preferred)
    suffix = choose_suffix(posterior_ds, basenames, preferred=suffix)

    # Now, re-evaluate presence WITH the chosen suffix
    has_v   = (f"v_{suffix}" in vars_) or (suffix == "" and "v" in vars_)
    has_Q   = (f"Q_{suffix}" in vars_) or (suffix == "" and "Q" in vars_)
    has_gdz = (f"beta0_gdgt23ratio_{suffix}" in vars_) or (suffix == "" and "beta0_gdgt23ratio" in vars_)
    has_no3 = (f"beta0_no3_{suffix}" in vars_) or (suffix == "" and "beta0_no3" in vars_)

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