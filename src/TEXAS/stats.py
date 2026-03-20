# TEXAS/stats.py
"""Lightweight statistical utilities for frequentist calibration analysis.

Public API
----------
f_test(rss_reduced, rss_full, k_reduced, k_full, n) -> (F, p)
    F-test for nested model comparison.

bootstrap_se(fit_fn, X, y, p0, bounds, n_boot=500, seed=42) -> (se, boots)
    Parametric bootstrap standard errors for scipy curve_fit models.
    Correctly handles collinear parameters (e.g. x0/Q in generalized logistic)
    where the Jacobian-based covariance is near-singular.
"""

import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import f as _f_dist


def f_test(
    rss_reduced: float,
    rss_full: float,
    k_reduced: int,
    k_full: int,
    n: int,
) -> tuple:
    """F-test for nested model comparison.

    Tests whether the additional parameters in the full model significantly
    reduce residual variance relative to the reduced model.

    Parameters
    ----------
    rss_reduced : float
        Residual sum of squares for the reduced (fewer-parameter) model.
    rss_full : float
        Residual sum of squares for the full model.
    k_reduced : int
        Number of free parameters in the reduced model.
    k_full : int
        Number of free parameters in the full model.
    n : int
        Number of observations.

    Returns
    -------
    F : float
        F-statistic.
    p : float
        p-value (right-tail probability under H0 that the full model adds
        nothing beyond the reduced model).

    Raises
    ------
    ValueError
        If k_full <= k_reduced or n <= k_full.
    """
    df1 = k_full - k_reduced
    df2 = n - k_full
    if df1 <= 0:
        raise ValueError(
            f"k_full ({k_full}) must be greater than k_reduced ({k_reduced})"
        )
    if df2 <= 0:
        raise ValueError(
            f"n - k_full ({n} - {k_full} = {df2}) must be positive"
        )
    F = ((rss_reduced - rss_full) / df1) / (rss_full / df2)
    p = float(1 - _f_dist.cdf(F, df1, df2))
    return float(F), p


def bootstrap_se(
    fit_fn,
    X: np.ndarray,
    y: np.ndarray,
    p0: list,
    bounds: tuple,
    n_boot: int = 500,
    seed: int = 42,
) -> tuple:
    """Row-resampling bootstrap standard errors for a scipy curve_fit model.

    Correctly captures joint parameter uncertainty for collinear parameters
    (e.g. x0/Q in the generalized logistic) where the Jacobian-based
    covariance matrix is near-singular.  Occasional failed fits on extreme
    resamples are silently skipped; if fewer than 10 replicates converge,
    all SEs are returned as NaN.

    Parameters
    ----------
    fit_fn : callable
        Model function with signature ``f(X, *params)``.
    X : ndarray, shape (n,) or (n, p)
        Predictor array.
    y : ndarray, shape (n,)
        Response vector.
    p0 : list
        Initial parameter guess passed to ``curve_fit``.
    bounds : tuple
        ``(lower_bounds, upper_bounds)`` passed to ``curve_fit``.
    n_boot : int
        Number of bootstrap replicates (default 500).
    seed : int
        Random seed for reproducibility (default 42).

    Returns
    -------
    se : ndarray, shape (n_params,)
        Bootstrap standard error per parameter.
    boots : ndarray, shape (n_successful, n_params)
        Full bootstrap distribution of parameter estimates.
    """
    rng = np.random.default_rng(seed)
    n = len(y)
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        X_b = X[idx]
        y_b = y[idx]
        try:
            p, _ = curve_fit(fit_fn, X_b, y_b, p0=p0, bounds=bounds,
                             max_nfev=10000)
            boots.append(p)
        except RuntimeError:
            pass
    boots = np.array(boots)
    if len(boots) < 10:
        return np.full(len(p0), np.nan), boots
    return boots.std(axis=0), boots
