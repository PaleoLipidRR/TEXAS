# TEXAS/models/multivariate.py

import numpy as np
from .logistics import (
    logistic_fixed_upper,
    generalized_logistic_fixed_upper
)

def simple_logistic_fixed_upper_multivariate(
    x: np.ndarray,
    t0: float = None,
    x0: float = None,
    b: float = None,
    k: float = None,
    beta0_gdgt23ratio: float = None,
    gdgt23ratio: np.ndarray = None,
    beta0_no3: float = None,
    no3: np.ndarray = None,
    no3_cutoff: float = 50.0
) -> np.ndarray:
    """
    3-parameter logistic (upper asymptote fixed at 1) plus optional linear corrections.
    y = b + (1 - b) / (1 + exp(-k*(x - inflection))) 
        + beta0_gdgt23ratio * gdgt23ratio 
        + beta0_no3 * log10(no3) [only where 0 < no3 < no3_cutoff]
    """
    # Base logistic
    inf = t0 if t0 is not None else x0
    mu = logistic_fixed_upper(x, t0=inf, k=k, b=b)
    mu = np.array(mu, copy=True)

    # GDGT-2/3 ratio correction
    if beta0_gdgt23ratio is not None and gdgt23ratio is not None:
        arr = np.asarray(gdgt23ratio)
        if arr.shape != mu.shape:
            raise ValueError(f"gdgt23ratio.shape {arr.shape} != x.shape {mu.shape}")
        mu += beta0_gdgt23ratio * arr

    # Nitrate correction
    if beta0_no3 is not None and no3 is not None:
        arr = np.asarray(no3)
        if arr.shape != mu.shape:
            raise ValueError(f"no3.shape {arr.shape} != x.shape {mu.shape}")
        mask = (arr > 0) & (arr < no3_cutoff)
        mu[mask] += beta0_no3 * np.log10(arr[mask])

    return mu


def generalized_logistic_fixed_upper_multivariate(
    x: np.ndarray,
    t0: float = None,
    x0: float = None,
    b: float = None,
    k: float = None,
    v: float = None,
    Q: float = None,
    beta0_gdgt23ratio: float = None,
    gdgt23ratio: np.ndarray = None,
    beta0_no3: float = None,
    no3: np.ndarray = None,
    no3_cutoff: float = 50.0
) -> np.ndarray:
    """
    5-parameter generalized logistic (upper asymptote fixed at 1) plus optional corrections.
    y = b + (1 - b) / (1 + Q*exp(-k*(x - inf)))^(1/v)
        + beta0_gdgt23ratio * gdgt23ratio 
        + beta0_no3 * log10(no3) [only where 0 < no3 < no3_cutoff]
    
    If v or Q are None, they default to 1.0 (reducing to simpler forms).
    """
    inf = t0 if t0 is not None else x0
    if inf is None:
        raise ValueError("Missing required parameter: t0 (or x0).")
    
    # Default v and Q to 1.0 if not provided (allows fixing them)
    v_val = v if v is not None else 1.0
    Q_val = Q if Q is not None else 1.0
    
    mu = generalized_logistic_fixed_upper(x, t0=inf, b=b, k=k, v=v_val, Q=Q_val)
    mu = np.array(mu, copy=True)

    # GDGT-2/3 ratio correction
    if beta0_gdgt23ratio is not None and gdgt23ratio is not None:
        arr = np.asarray(gdgt23ratio)
        if arr.shape != mu.shape:
            raise ValueError(f"gdgt23ratio.shape {arr.shape} != x.shape {mu.shape}")
        mu += beta0_gdgt23ratio * arr

    # Nitrate correction
    if beta0_no3 is not None and no3 is not None:
        arr = np.asarray(no3)
        if arr.shape != mu.shape:
            raise ValueError(f"no3.shape {arr.shape} != x.shape {mu.shape}")
        mask = (arr > 0) & (arr < no3_cutoff)
        mu[mask] += beta0_no3 * np.log10(arr[mask])

    return mu
