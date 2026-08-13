# TEXAS/ensemble/detection.py

import xarray as xr
from ..models.logistics import (
    logistic_fixed_upper,
    generalized_logistic_fixed_upper,
)
from ..models.multivariate import (
    simple_logistic_fixed_upper_multivariate,
    generalized_logistic_fixed_upper_multivariate,
    generalized_logistic_fixed_upper_bounded_t,
)

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
    attrs_ = set(posterior_ds.attrs)

    # Detect presence of optional parameter groups without assuming attrs
    has_v_any   = ("v" in vars_) or any(v.startswith("v_") for v in vars_)
    has_gdz_any = ("use_gdgt23ratio" in attrs_)
    has_no3_any = ("use_no3" in attrs_)

    # Additive (beta-on-mu) or bounded-T (gamma-on-T0)? Decided from the
    # variables present, not from stan_model_name — this module has always
    # inferred structure from data_vars, and a posterior renamed or downloaded
    # from Zenodo still carries its parameters.
    is_bounded_t = any(v == "gamma_G23" or v.startswith("gamma_G23_")
                       or v == "gamma_NO3" or v.startswith("gamma_NO3_")
                       for v in vars_)
    coef_G23 = "gamma_G23" if is_bounded_t else "beta_G23"
    coef_NO3 = "gamma_NO3" if is_bounded_t else "beta_NO3"

    # Build candidate basenames up-front for suffix selection
    basenames = ["t0", "b", "k"]
    if has_v_any:
        basenames.append("v")
    if has_gdz_any:
        basenames += [coef_G23]
    if has_no3_any:
        basenames += [coef_NO3]

    # Choose suffix by priority (or validate preferred)
    suffix = choose_suffix(posterior_ds, basenames, preferred=suffix)

    # Now, re-evaluate presence WITH the chosen suffix
    has_v   = (f"v_{suffix}" in vars_) or (suffix == "" and "v" in vars_)
    has_gdz = ("use_gdgt23ratio" in attrs_)
    has_no3 = ("use_no3" in attrs_) 
    detected_no3_cutoff = 0.0
    if has_no3:
        detected_no3_cutoff = posterior_ds.attrs.get("no3_cutoff", 0.0)

    # Build param list and select model
    is_generalized = has_v

    if is_generalized:
        params = ["t0", "b", "k"]
        if has_v:
            params.append("v")
        if has_gdz:
            params.append(coef_G23)
        if has_no3:
            params.append(coef_NO3)

        if has_gdz or has_no3:
            model_fn = (generalized_logistic_fixed_upper_bounded_t
                        if is_bounded_t else
                        generalized_logistic_fixed_upper_multivariate)
        else:
            model_fn = generalized_logistic_fixed_upper
    else:
        params = ["t0", "b", "k"]
        if has_gdz:
            params.append(coef_G23)
        if has_no3:
            params.append(coef_NO3)

        # There is no simple-logistic bounded-T model: bounded-T exists only as
        # the generalized curve. Raise rather than silently fitting the additive
        # form to gamma coefficients, which would be wrong by a whole
        # parameterisation and would look plausible.
        if is_bounded_t:
            raise ValueError(
                "Bounded-T coefficients (gamma_*) found on a posterior with no "
                "v parameter. Bounded-T is only defined for the generalized "
                "logistic; this posterior looks malformed."
            )
        model_fn = (
            simple_logistic_fixed_upper_multivariate
            if has_gdz or has_no3 else
            logistic_fixed_upper
        )

    return {
        "model_function": model_fn,
        "param_names": params,
        "suffix": suffix,
        "is_multivariate": bool(has_gdz or has_no3),
        "use_gdgt23ratio": bool(has_gdz),
        "use_no3": bool(has_no3),
        "no3_cutoff": detected_no3_cutoff,
    }