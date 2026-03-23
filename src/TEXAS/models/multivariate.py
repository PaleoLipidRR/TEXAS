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
    log_method: str = "log10",
    score_method: str = "spearmanr",
    weight_method: str = "uniform",
):
    """Find the NO3 threshold that maximises the negative correlation between
    log(NO3) and model residuals.

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
        Minimum number of valid data points required to compute a score.
    log_method : {'log10', 'ln'}
        Log transform applied to NO3 values before scoring.

        ``'log10'`` (default)
            Base-10 logarithm — consistent with prior publication and the
            original Stan model formulation.
        ``'ln'``
            Natural logarithm — use to test sensitivity to the log base.

    score_method : {'spearmanr', 'R_squared'}
        Criterion used to select the optimal threshold.

        ``'spearmanr'`` (default)
            Most negative Spearman ρ between log(NO3) and residuals.
            Rank-based; robust to outliers.  Used in prior publication.
        ``'R_squared'``
            Highest no-intercept R² of ``RI_res = β · log(NO3)`` with β < 0.
            Penalises poor fit, not just rank order.  Consistent with a
            model where the correction is zero at no3 = 1 (log10) or
            no3 = 1 (ln).  For a zero-at-threshold formulation use
            ``find_optimal_no3_threshold_nointercept`` instead.

    weight_method : {'uniform', 'positive_residuals', 'negative_residuals'}
        Asymmetric weighting applied when ``score_method='R_squared'``
        (ignored for ``'spearmanr'``, which does not support sample weights).

        ``'uniform'`` (default)
            All points weighted equally — standard OLS.
        ``'positive_residuals'``
            ``w_i = max(res_i, ε)`` — up-weights observations with positive
            residuals.  Use for the NO₃ correction: nutrient-limited sites
            are expected to have positive RI residuals (observed RI > predicted
            from temperature alone).
        ``'negative_residuals'``
            ``w_i = max(-res_i, ε)`` — up-weights observations with negative
            residuals.  Use for the G23 correction: deep-water / high-G23
            sites are expected to have negative RI residuals.

    Returns
    -------
    optimal_threshold : float
        Threshold (µmol/L) giving the best score.
    results : pd.DataFrame
        One row per tested threshold.  Columns depend on ``score_method``:

        - ``'spearmanr'``:  ``threshold``, ``spearman_rho``,
          ``spearman_pval``, ``n_points``
        - ``'R_squared'``:  ``threshold``, ``beta``,
          ``r2_nointercept``, ``n_points``

    Raises
    ------
    ImportError
        If pandas or scipy are not available.
    ValueError
        If ``log_method`` or ``score_method`` are unrecognised, or no valid
        threshold is found.
    """
    if not _HAS_SCIPY_PANDAS:
        raise ImportError(
            "find_optimal_no3_threshold requires pandas and scipy. "
            "Install them with: pip install pandas scipy"
        )
    if log_method not in ("log10", "ln"):
        raise ValueError(f"log_method must be 'log10' or 'ln', got '{log_method}'")
    if score_method not in ("spearmanr", "R_squared"):
        raise ValueError(f"score_method must be 'spearmanr' or 'R_squared', got '{score_method}'")
    if weight_method not in ("uniform", "positive_residuals", "negative_residuals"):
        raise ValueError(
            f"weight_method must be 'uniform', 'positive_residuals', or "
            f"'negative_residuals', got '{weight_method}'"
        )

    if threshold_range is None:
        threshold_range = np.arange(0.5, 5, 0.01)

    _log = np.log10 if log_method == "log10" else np.log

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

        if len(no3_v) < min_points:
            continue

        x = _log(no3_v)

        if score_method == "spearmanr":
            rho, pval = spearmanr(x, res_v)
            rows.append({
                "threshold": thr,
                "spearman_rho": rho,
                "spearman_pval": pval,
                "n_points": len(no3_v),
            })
        else:  # R_squared
            eps = max(1e-9, 0.001 * np.std(res_v)) if np.std(res_v) > 0 else 1e-9
            if weight_method == "positive_residuals":
                w = np.where(res_v > 0, res_v, eps)
            elif weight_method == "negative_residuals":
                w = np.where(res_v < 0, -res_v, eps)
            else:
                w = np.ones_like(res_v)
            beta = np.dot(w * res_v, x) / np.dot(w * x, x)
            if beta >= 0:
                rows.append({"threshold": thr, "beta": beta,
                             "r2_nointercept": np.nan, "n_points": len(no3_v)})
                continue
            ss_res = np.sum(w * (res_v - beta * x) ** 2)
            ss_tot = np.sum(w * res_v ** 2)
            rows.append({"threshold": thr, "beta": beta,
                         "r2_nointercept": 1.0 - ss_res / ss_tot,
                         "n_points": len(no3_v)})

    results = pd.DataFrame(rows)
    if results.empty:
        raise ValueError(
            f"No threshold in threshold_range produced >= {min_points} valid points. "
            "Try lowering min_points or widening threshold_range."
        )

    if score_method == "spearmanr":
        optimal = float(results.loc[results["spearman_rho"].idxmin(), "threshold"])
    else:
        valid_rows = results.dropna(subset=["r2_nointercept"])
        if valid_rows.empty:
            raise ValueError(
                "No threshold produced a negative β. "
                "Check that residuals have the expected NO3 signal direction."
            )
        optimal = float(valid_rows.loc[valid_rows["r2_nointercept"].idxmax(), "threshold"])

    return optimal, results


def find_optimal_no3_threshold_nointercept(
    no3_values: np.ndarray,
    residuals: np.ndarray,
    threshold_range=None,
    min_points: int = 5,
    no3_mode: str = "log10ratio",
    log_method: str = "log10",
    weight_method: str = "uniform",
):
    """Find the NO3 threshold that maximises the no-intercept R² of
    ``RI_res = β · x``, consistent with the no3ratio Stan model formulation
    where the correction is exactly zero at the threshold boundary.

    Unlike ``find_optimal_no3_threshold`` (Spearman-based, used in prior
    publication), this function optimises for the threshold that best explains
    residual variance under the zero-intercept constraint.

    Parameters
    ----------
    no3_values : array-like
        Nitrate concentrations (µmol/L).
    residuals : array-like
        Residuals from a temperature-only model fit on the same observations.
    threshold_range : array-like, optional
        NO3 thresholds to test.  Defaults to ``np.arange(0.5, 5, 0.01)``.
    min_points : int
        Minimum number of valid data points required to fit the regression.
    no3_mode : {'log10ratio', 'log10'}
        Predictor used in the no-intercept regression:

        ``'log10ratio'`` (default)
            ``x = log10(no3 / threshold)`` — zero at the boundary; consistent
            with the ``_no3ratio`` Stan models.  The optimal threshold is where
            the no-intercept model best fits the data with correction = 0 at T.

        ``'log10'``
            ``x = log10(no3)`` — zero at no3 = 1 µmol/L regardless of T;
            consistent with the original Stan models.  Use this to compare the
            no-intercept R² criterion against the Spearman criterion while
            keeping the original predictor form.

    log_method : {'log10', 'ln'}
        Log transform applied to NO3 values.  ``'log10'`` (default) matches
        the Stan model formulations; ``'ln'`` tests sensitivity to log base.

    weight_method : {'uniform', 'positive_residuals', 'negative_residuals'}
        Asymmetric weighting for the no-intercept regression.

        ``'uniform'`` (default)
            All points weighted equally — standard no-intercept OLS.
        ``'positive_residuals'``
            ``w_i = max(res_i, ε)`` — up-weights observations with positive
            residuals.  Use for the NO₃ correction: nutrient-limited sites
            are expected to have positive RI residuals (observed RI > predicted
            from temperature alone).
        ``'negative_residuals'``
            ``w_i = max(-res_i, ε)`` — up-weights observations with negative
            residuals.  Use for the G23 correction: deep-water / high-G23
            sites are expected to have negative RI residuals.

        In all cases, ``ε = 0.001 · std(residuals)`` so that off-direction
        points are suppressed but never fully excluded (avoids numerical
        instability when nearly all residuals are on one side).

    Returns
    -------
    optimal_threshold : float
        Threshold (µmol/L) giving the highest no-intercept R² with β < 0.
    results : pd.DataFrame
        One row per tested threshold; columns: ``threshold``, ``beta``,
        ``r2_nointercept``, ``n_points``.

    Raises
    ------
    ImportError
        If pandas or scipy are not available.
    ValueError
        If no valid threshold is found or parameters are unrecognised.
    """
    if not _HAS_SCIPY_PANDAS:
        raise ImportError(
            "find_optimal_no3_threshold_nointercept requires pandas and scipy. "
            "Install them with: pip install pandas scipy"
        )
    if no3_mode not in ("log10ratio", "log10"):
        raise ValueError(f"no3_mode must be 'log10ratio' or 'log10', got '{no3_mode}'")
    if log_method not in ("log10", "ln"):
        raise ValueError(f"log_method must be 'log10' or 'ln', got '{log_method}'")
    if weight_method not in ("uniform", "positive_residuals", "negative_residuals"):
        raise ValueError(
            f"weight_method must be 'uniform', 'positive_residuals', or "
            f"'negative_residuals', got '{weight_method}'"
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

        if len(no3_v) < min_points:
            continue

        _log = np.log10 if log_method == "log10" else np.log
        x = _log(no3_v / thr) if no3_mode == "log10ratio" else _log(no3_v)

        # Asymmetric weights (scale ε to residual spread)
        eps = max(1e-9, 0.001 * np.std(res_v)) if np.std(res_v) > 0 else 1e-9
        if weight_method == "positive_residuals":
            w = np.where(res_v > 0, res_v, eps)
        elif weight_method == "negative_residuals":
            w = np.where(res_v < 0, -res_v, eps)
        else:
            w = np.ones_like(res_v)

        # Weighted no-intercept OLS: β = <w·res, x> / <w·x, x>
        beta = np.dot(w * res_v, x) / np.dot(w * x, x)

        if beta >= 0:
            rows.append({"threshold": thr, "beta": beta,
                         "r2_nointercept": np.nan, "n_points": len(no3_v)})
            continue

        ss_res = np.sum(w * (res_v - beta * x) ** 2)
        ss_tot = np.sum(w * res_v ** 2)      # denominator for weighted no-intercept R²
        r2 = 1.0 - ss_res / ss_tot

        rows.append({"threshold": thr, "beta": beta,
                     "r2_nointercept": r2, "n_points": len(no3_v)})

    results = pd.DataFrame(rows)
    if results.empty:
        raise ValueError(
            f"No threshold in threshold_range produced >= {min_points} valid points. "
            "Try lowering min_points or widening threshold_range."
        )

    valid_rows = results.dropna(subset=["r2_nointercept"])
    if valid_rows.empty:
        raise ValueError(
            "No threshold produced a negative β. "
            "Check that residuals have the expected NO3 signal direction."
        )

    optimal = float(valid_rows.loc[valid_rows["r2_nointercept"].idxmax(), "threshold"])
    return optimal, results
