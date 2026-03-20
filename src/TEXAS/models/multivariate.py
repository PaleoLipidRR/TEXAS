# TEXAS/models/multivariate.py

import numpy as np
from .logistics import (
    logistic_fixed_upper,
    generalized_logistic_fixed_upper
)

try:
    import pandas as pd
    from scipy.stats import spearmanr
    _HAS_SCIPY_PANDAS = True
except ImportError:
    _HAS_SCIPY_PANDAS = False

def simple_logistic_fixed_upper_multivariate(
    x: np.ndarray,
    t0: float = None,
    x0: float = None,
    b: float = None,
    k: float = None,
    beta_G23: float = None,
    gdgt23ratio: np.ndarray = None,
    beta_NO3: float = None,
    no3: np.ndarray = None,
    no3_cutoff: float = 50.0
) -> np.ndarray:
    """
    3-parameter logistic (upper asymptote fixed at 1) plus optional linear corrections.
    y = b + (1 - b) / (1 + exp(-k*(x - inflection))) 
        + beta_G23 * gdgt23ratio 
        + beta_NO3 * log10(no3) [only where 0 < no3 < no3_cutoff]
    """
    # Base logistic
    inf = t0 if t0 is not None else x0
    mu = logistic_fixed_upper(x, t0=inf, k=k, b=b)
    mu = np.array(mu, copy=True)

    # GDGT-2/3 ratio correction
    if beta_G23 is not None and gdgt23ratio is not None:
        arr = np.asarray(gdgt23ratio)
        if arr.shape != mu.shape:
            raise ValueError(f"gdgt23ratio.shape {arr.shape} != x.shape {mu.shape}")
        mu += beta_G23 * arr

    # Nitrate correction
    if beta_NO3 is not None and no3 is not None:
        arr = np.asarray(no3)
        if arr.shape != mu.shape:
            raise ValueError(f"no3.shape {arr.shape} != x.shape {mu.shape}")
        mask = (arr > 0) & (arr < no3_cutoff)
        mu[mask] += beta_NO3 * np.log10(arr[mask])

    return mu


def generalized_logistic_fixed_upper_multivariate(
    x: np.ndarray,
    t0: float = None,
    x0: float = None,
    b: float = None,
    k: float = None,
    v: float = None,
    Q: float = None,
    beta_G23: float = None,
    gdgt23ratio: np.ndarray = None,
    beta_NO3: float = None,
    no3: np.ndarray = None,
    no3_cutoff: float = 50.0
) -> np.ndarray:
    """
    5-parameter generalized logistic (upper asymptote fixed at 1) plus optional corrections.
    y = b + (1 - b) / (1 + Q*exp(-k*(x - inf)))^(1/v)
        + beta_G23 * gdgt23ratio 
        + beta_NO3 * log10(no3) [only where 0 < no3 < no3_cutoff]
    
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
    if beta_G23 is not None and gdgt23ratio is not None:
        arr = np.asarray(gdgt23ratio)
        if arr.shape != mu.shape:
            raise ValueError(f"gdgt23ratio.shape {arr.shape} != x.shape {mu.shape}")
        mu += beta_G23 * arr

    # Nitrate correction
    if beta_NO3 is not None and no3 is not None:
        arr = np.asarray(no3)
        if arr.shape != mu.shape:
            raise ValueError(f"no3.shape {arr.shape} != x.shape {mu.shape}")
        mask = (arr > 0) & (arr < no3_cutoff)
        mu[mask] += beta_NO3 * np.log10(arr[mask])

    return mu


def find_optimal_no3_threshold(
    no3_values: np.ndarray,
    residuals: np.ndarray,
    threshold_range=None,
    min_points: int = 5,
):
    """Find the NO3 threshold that maximises the negative Spearman correlation
    between log10(NO3) and model residuals.

    Used to select the ``no3_cutoff`` parameter for the multivariate logistic
    models: points below the threshold carry an NO3 correction; points above
    are treated as nutrient-replete and excluded from the NO3 term.

    Parameters
    ----------
    no3_values : array-like
        Nitrate concentrations (µmol/L).
    residuals : array-like
        Residuals from a temperature-only model fit on the same observations.
    threshold_range : array-like, optional
        NO3 thresholds to test.  Defaults to ``np.arange(0.5, 5, 0.01)``.
    min_points : int
        Minimum number of valid data points required to compute a correlation.

    Returns
    -------
    optimal_threshold : float
        Threshold (µmol/L) giving the most negative Spearman rho.
    results : pd.DataFrame
        One row per tested threshold; columns: ``threshold``, ``spearman_rho``,
        ``spearman_pval``, ``n_points``.

    Raises
    ------
    ImportError
        If pandas or scipy are not available.
    """
    if not _HAS_SCIPY_PANDAS:
        raise ImportError(
            "find_optimal_no3_threshold requires pandas and scipy. "
            "Install them with: pip install pandas scipy"
        )

    if threshold_range is None:
        threshold_range = np.arange(0.5, 5, 0.01)

    no3 = np.asarray(no3_values, dtype=float)
    resid = np.asarray(residuals, dtype=float)

    rows = []
    for thr in threshold_range:
        mask = no3 <= thr
        no3_sub = no3[mask]
        res_sub = resid[mask]
        valid = np.isfinite(no3_sub) & np.isfinite(res_sub) & (no3_sub > 0)
        no3_v = no3_sub[valid]
        res_v = res_sub[valid]
        if len(no3_v) >= min_points:
            rho, pval = spearmanr(np.log10(no3_v), res_v)
            rows.append({
                "threshold": thr,
                "spearman_rho": rho,
                "spearman_pval": pval,
                "n_points": len(no3_v),
            })

    results = pd.DataFrame(rows)
    if results.empty:
        raise ValueError(
            f"No threshold in threshold_range produced >= {min_points} valid points. "
            "Try lowering min_points or widening threshold_range."
        )
    optimal = float(results.loc[results["spearman_rho"].idxmin(), "threshold"])
    return optimal, results
