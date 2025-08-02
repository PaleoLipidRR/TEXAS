# TEXAS/models/multivariate.py

import numpy as np
from .logistics import (
    logistic_fixed_upper,
    generalized_logistic_fixed_upper
)

def simple_logistic_fixed_upper_multivariate(
    x,
    t0=None,
    x0=None,
    b=None,
    k=None,
    beta0_gdgt23ratio=None,
    gdgt23ratio=None,
    beta0_no3=None,
    no3=None,
    no3_cutoff=50.0
):
    """
    3-parameter logistic (upper asymptote fixed at 1) plus optional linear corrections.

    y = b + (1 - b) / (1 + exp(-k*(x - inflection))) 
        + beta0_gdgt23ratio * gdgt23ratio 
        + beta0_no3 * log10(no3) [only where 0 < no3 < no3_cutoff]

    Parameters
    ----------
    x : array-like
    t0 / x0 : float
        Inflection.
    b : float
        Lower asymptote.
    k : float
        Slope.
    beta0_gdgt23ratio : float, optional
    gdgt23ratio : array-like, optional
    beta0_no3 : float, optional
    no3 : array-like, optional
    no3_cutoff : float, default 50.0
    """
    # base
    inf = t0 if t0 is not None else x0
    mu = logistic_fixed_upper(x, inf, k, b)
    mu = np.array(mu, copy=True)

    # gdgt23ratio
    if beta0_gdgt23ratio is not None and gdgt23ratio is not None:
        arr = np.asarray(gdgt23ratio)
        if arr.shape != mu.shape:
            raise ValueError(f"gdgt23ratio.shape {arr.shape} != x.shape {mu.shape}")
        mu += beta0_gdgt23ratio * arr

    # no3
    if beta0_no3 is not None and no3 is not None:
        arr = np.asarray(no3)
        if arr.shape != mu.shape:
            raise ValueError(f"no3.shape {arr.shape} != x.shape {mu.shape}")
        mask = (arr > 0) & (arr < no3_cutoff)
        mu[mask] += beta0_no3 * np.log10(arr[mask])

    return mu


def generalized_logistic_fixed_upper_multivariate(
    x,
    t0=None,
    x0=None,
    b=None,
    k=None,
    v=None,
    Q=None,
    beta0_gdgt23ratio=None,
    gdgt23ratio=None,
    beta0_no3=None,
    no3=None,
    no3_cutoff=50.0
):
    """
    5-parameter generalized logistic (upper asymptote fixed at 1) plus corrections.

    y = b + (1 - b) / (1 + Q*exp(-k*(x - inf)))^(1/v)
        + beta0_gdgt23ratio * gdgt23ratio 
        + beta0_no3 * log10(no3) [only where 0 < no3 < no3_cutoff]
    """
    # base
    inf = t0 if t0 is not None else x0
    mu = generalized_logistic_fixed_upper(x, inf, b, k, v, Q)
    mu = np.array(mu, copy=True)

    # gdgt23ratio
    if beta0_gdgt23ratio is not None and gdgt23ratio is not None:
        arr = np.asarray(gdgt23ratio)
        if arr.shape != mu.shape:
            raise ValueError(f"gdgt23ratio.shape {arr.shape} != x.shape {mu.shape}")
        mu += beta0_gdgt23ratio * arr

    # no3
    if beta0_no3 is not None and no3 is not None:
        arr = np.asarray(no3)
        if arr.shape != mu.shape:
            raise ValueError(f"no3.shape {arr.shape} != x.shape {mu.shape}")
        mask = (arr > 0) & (arr < no3_cutoff)
        mu[mask] += beta0_no3 * np.log10(arr[mask])

    return mu
