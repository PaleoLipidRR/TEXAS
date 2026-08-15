# TEXAS/models/multivariate.py

import warnings

import numpy as np
from .logistics import (
    logistic_fixed_upper,
    generalized_logistic_fixed_upper,
    inverse_generalized_logistic_fixed_upper,
)


def _broadcast_predictor(values, shape, name):
    """Coerce an optional predictor to ``shape``.

    Accepts a scalar (applied to every sample) or an array broadcastable to
    ``shape`` (per-sample values).  Returns a float array of exactly ``shape``.
    Raises ``ValueError`` with a clear message if the array cannot be
    broadcast (e.g. a length-3 array against 5 samples).
    """
    arr = np.asarray(values, dtype=float)
    try:
        return np.broadcast_to(arr, shape).astype(float, copy=False)
    except ValueError:
        raise ValueError(
            f"{name} shape {arr.shape} is not broadcastable to the proxy shape "
            f"{shape}; pass a single value or one value per sample."
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
    beta_G23: float = None,
    gdgt23ratio: np.ndarray = None,
    beta_NO3: float = None,
    no3: np.ndarray = None,
    no3_cutoff: float = 50.0
) -> np.ndarray:
    """
    4-parameter generalized logistic (upper asymptote fixed at 1, Q fixed at 1)
    plus optional corrections.
    y = b + (1 - b) / (1 + exp(-k*(x - inf)))^(1/v)
        + beta_G23 * gdgt23ratio
        + beta_NO3 * log10(no3) [only where 0 < no3 < no3_cutoff]

    If v is None it defaults to 1.0 (reducing to the standard logistic).
    """
    inf = t0 if t0 is not None else x0
    if inf is None:
        raise ValueError("Missing required parameter: t0 (or x0).")

    # Default v to 1.0 if not provided (allows fixing it)
    v_val = v if v is not None else 1.0

    mu = generalized_logistic_fixed_upper(x, t0=inf, b=b, k=k, v=v_val)
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


def generalized_logistic_fixed_upper_t0shift(
    x: np.ndarray,
    t0: float = None,
    x0: float = None,
    b: float = None,
    k: float = None,
    v: float = None,
    gamma_G23: float = None,
    gdgt23ratio: np.ndarray = None,
    gamma_NO3: float = None,
    no3: np.ndarray = None,
    no3_cutoff: float = 50.0
) -> np.ndarray:
    """
    Bounded-T counterpart of :func:`generalized_logistic_fixed_upper_multivariate`.

    The corrections shift the curve's location parameter rather than the mean::

        t0_eff = t0 + gamma_G23 * gdgt23ratio
                    + gamma_NO3 * log10(no3)   [only where 0 < no3 < no3_cutoff]
        y      = b + (1 - b) / (1 + exp(-k*(x - t0_eff)))^(1/v)

    That keeps ``y`` inside ``(b, 1)`` for every finite predictor value, which is
    the entire point of the parameterisation — the additive form can push the
    mean outside the proxy's range. Mirrors ``bounded_mu()`` in
    ``gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_t0shift.stan``, including
    the NO3 gate.

    One deliberate difference from the Stan model: there, the gate is applied to
    the OBSERVED nitrate while ``log10`` is taken of the LATENT (EIV) value. A
    plotted curve has only one nitrate array to work from, so it is used for
    both — exactly as the additive Python function already does.

    **That difference is not cosmetic.** Fed this function's own convention, the
    per-draw ``mu_max`` sits ~0.1 above the ``mu_max`` Stan recorded in generated
    quantities; fed the latent values from ``true_no3_crtp`` /
    ``true_gdgt23ratio_crtp``, it reproduces Stan to 8e-7 (float32 storage
    precision), which is how the formula here was verified. So a curve drawn
    from observed predictors is the right thing for plotting against observed
    data, but it is not the in-sample fit and should not be compared to one
    digit for digit. The additive model has the same property.

    If v is None it defaults to 1.0 (reducing to the standard logistic).
    """
    inf = t0 if t0 is not None else x0
    if inf is None:
        raise ValueError("Missing required parameter: t0 (or x0).")

    v_val = v if v is not None else 1.0

    x_arr = np.asarray(x, dtype=float)
    t0_eff = np.full(x_arr.shape, float(inf))

    if gamma_G23 is not None and gdgt23ratio is not None:
        arr = np.asarray(gdgt23ratio)
        if arr.shape != x_arr.shape:
            raise ValueError(f"gdgt23ratio.shape {arr.shape} != x.shape {x_arr.shape}")
        t0_eff = t0_eff + gamma_G23 * arr

    if gamma_NO3 is not None and no3 is not None:
        arr = np.asarray(no3)
        if arr.shape != x_arr.shape:
            raise ValueError(f"no3.shape {arr.shape} != x.shape {x_arr.shape}")
        mask = (arr > 0) & (arr < no3_cutoff)
        t0_eff = t0_eff.copy()
        t0_eff[mask] += gamma_NO3 * np.log10(arr[mask])

    return b + (1.0 - b) / np.power(1.0 + np.exp(-k * (x_arr - t0_eff)), 1.0 / v_val)


def inverse_generalized_logistic_fixed_upper_multivariate(
    y: np.ndarray,
    t0: float = None,
    x0: float = None,
    b: float = None,
    k: float = None,
    v: float = None,
    beta_G23: float = None,
    gdgt23ratio: np.ndarray = None,
    beta_NO3: float = None,
    no3: np.ndarray = None,
    no3_cutoff: float = 50.0,
) -> np.ndarray:
    """Invert :func:`generalized_logistic_fixed_upper_multivariate`.

    Given proxy observations ``y`` (e.g. Scaled Ring Index), return the
    temperature ``x`` (e.g. SST) that the forward model maps to ``y`` for a
    *single* parameter set.  The two non-thermal corrections are additive and
    independent of temperature, so inversion subtracts them off and then
    inverts the pure thermal curve analytically::

        y_thermal = y - beta_G23 * gdgt23ratio
                      - beta_NO3 * log10(no3)   [only where 0 < no3 < no3_cutoff]
        x = t0 - ln(((1 - b) / (y_thermal - b))**v - 1) / k

    ``gdgt23ratio`` and ``no3`` may each be a single scalar (applied to every
    sample) or an array of per-sample values broadcastable to ``y``.  Supply
    the *same* covariate values that applied to those observations — they are
    additive predictors, not solved for.

    The thermal inverse is defined only for ``b < y_thermal < 1``.  Proxy
    values outside that range are physically unreachable for the given
    parameters and are returned as ``np.nan`` (a single ``RuntimeWarning`` is
    emitted if any occur).

    .. note::
       This is a deterministic **point** inverse for one parameter set (e.g.
       posterior means).  For uncertainty-aware paleotemperature
       reconstruction that marginalises over the full forward posterior, use
       :func:`TEXAS.predict.predict_T_from_proxyObs` (the Bayesian Stan path).

    Parameters
    ----------
    y : array-like
        Proxy observations (Scaled Ring Index) to invert.  Scalar or array.
    t0, x0 : float
        Inflection point (prefer ``t0``; ``x0`` accepted for legacy callers).
    b : float
        Lower asymptote.
    k : float
        Slope.
    v : float, optional
        Generalized-logistic shape parameter; defaults to 1.0 (standard
        logistic), matching the forward function.
    beta_G23 : float, optional
        GDGT-2/3 ratio coefficient.  Correction applied only if both
        ``beta_G23`` and ``gdgt23ratio`` are given.
    gdgt23ratio : array-like, optional
        GDGT-2/3 ratio: scalar or one value per sample.
    beta_NO3 : float, optional
        Nitrate coefficient.  Correction applied only if both ``beta_NO3`` and
        ``no3`` are given, and only where ``0 < no3 < no3_cutoff``.
    no3 : array-like, optional
        Nitrate concentration (µmol/L): scalar or one value per sample.
    no3_cutoff : float
        Upper NO3 bound for the correction; must match the forward call.

    Returns
    -------
    x : np.ndarray
        Reconstructed temperature, ``np.nan`` where ``y`` is unreachable.
        A 0-d array is returned for scalar input, matching the forward
        function's convention.

    Raises
    ------
    ValueError
        If required parameters (``t0``/``x0``, ``b``, ``k``) are missing, or a
        predictor array cannot be broadcast to the shape of ``y``.
    """
    inf = t0 if t0 is not None else x0
    if inf is None:
        raise ValueError("Missing required parameter: t0 (or x0).")
    if b is None or k is None:
        raise ValueError("Missing required parameters: b, k.")

    v_val = v if v is not None else 1.0

    y_arr = np.asarray(y, dtype=float)
    scalar_input = y_arr.ndim == 0
    # Work on a writable 1-D copy; reshape back to a 0-d array at the end.
    y_thermal = np.atleast_1d(np.array(y_arr, copy=True))
    shape = y_thermal.shape

    # Remove the (temperature-independent) GDGT-2/3 offset.
    if beta_G23 is not None and gdgt23ratio is not None:
        arr = _broadcast_predictor(gdgt23ratio, shape, "gdgt23ratio")
        y_thermal = y_thermal - beta_G23 * arr

    # Remove the NO3 offset, using the same mask the forward applies.
    if beta_NO3 is not None and no3 is not None:
        arr = _broadcast_predictor(no3, shape, "no3")
        mask = (arr > 0) & (arr < no3_cutoff)
        y_thermal[mask] = y_thermal[mask] - beta_NO3 * np.log10(arr[mask])

    # Domain guard: after removing the (per-sample) non-thermal corrections,
    # y_thermal lies on the base thermal curve, which spans (b, 1) for any
    # v > 0.  The analytical inverse is real only there; outside it the log
    # argument is non-positive.  Note the guard is on y_thermal, not the raw
    # proxy y — y's own valid range is shifted per sample by its corrections.
    valid = (y_thermal > b) & (y_thermal < 1.0)
    n_invalid = int(np.count_nonzero(~valid))
    if n_invalid:
        warnings.warn(
            f"{n_invalid} of {y_thermal.size} sample(s) have a thermal (corrected) "
            f"proxy outside the base-curve range (b, 1) = ({b}, 1); the proxy is "
            "unreachable for these parameters and they return NaN.",
            RuntimeWarning,
            stacklevel=2,
        )

    out = np.full(shape, np.nan, dtype=float)
    if np.any(valid):
        out[valid] = inverse_generalized_logistic_fixed_upper(
            y_thermal[valid], t0=inf, b=b, k=k, v=v_val
        )

    return out.reshape(()) if scalar_input else out


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


# Legacy alias — the T0-shift model was called "bounded-T" before the
# 2026-08-15 rename; keep the old callable name working.
generalized_logistic_fixed_upper_bounded_t = generalized_logistic_fixed_upper_t0shift
