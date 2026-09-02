# TEXAS/quality.py
"""Per-observation quality flags for an inverse reconstruction.

``predict_T_from_proxyObs`` already warns about whole-call mistakes --- passing
a predictor the calibration cannot use, or omitting one it needs. Those fire
once and describe the call. This module answers the other question: *which rows
of my record should I trust?*

The motivating case is a Scaled RI below the curve's lower asymptote ``b``. The
inverse likelihood is Gaussian in ``mu``::

    mu = b + (1 - b) / (1 + exp(-k*(T - T0)))^(1/v)          -> (b, 1)

so as ``T`` falls, ``mu`` approaches ``b`` and stops. An observation below ``b``
cannot be reproduced at any temperature. Nothing errors: the Gaussian
likelihood simply keeps improving as ``T`` decreases, with no interior maximum,
and the only thing arresting the chain is the temperature prior. The sampler
converges, R-hat is clean, and the reported median is a readout of
``prior_mu_t`` and ``prior_sigma_t`` rather than a measurement. Under the
default ``constraint_type="unconstrained"`` there is no lower bound on ``t_est``
at all, so the value returned can be physically impossible. The same happens in
mirror image above the upper asymptote.

These rows do not announce themselves, which is why they need a flag rather
than a warning.

All checks are vectorised over the N observations and return one row each, so
the result filters directly::

    result = predict_T_from_proxyObs(proxyObs=ri, prior_mu_t=25, prior_sigma_t=10)
    good = result["flags"]["any_flag"] == False
    trustworthy_sst = result["p50"][good.to_numpy()]
"""
from __future__ import annotations

import warnings
from typing import Any, Dict, Optional, Union

import numpy as np
import pandas as pd
import xarray as xr

from .ensemble.detection import choose_suffix

__all__ = [
    "compute_quality_flags",
    "FLAG_COLUMNS",
    "ADVISORY_COLUMNS",
    "DIAGNOSTIC_COLUMNS",
]


# Boolean columns, in the order they appear in the returned frame.
FLAG_COLUMNS = (
    "proxy_below_floor",
    "proxy_above_ceiling",
    "proxy_extrapolated",
    "predictor_missing",
    "predictor_extrapolated",
    "no3_correction_inactive",
    "outside_domain",
    "prior_dominated",
)

# Reported but excluded from ``any_flag``: these describe how the reconstruction
# was configured, not a reason to distrust the row.
#
# NO3 outside the correction window is nearly always deliberate --- ``no3=10``
# against a cutoff of 1.0 is the documented way to switch the correction off, so
# it fires on every row of such a run. Letting it vote would mark an entire
# healthy record as suspect and make the filter useless.
ADVISORY_COLUMNS = ("no3_correction_inactive",)

# The subset of FLAG_COLUMNS that ``any_flag`` actually ORs.
DEFECT_COLUMNS = tuple(c for c in FLAG_COLUMNS if c not in ADVISORY_COLUMNS)

# Graded companions to the booleans. A boolean says "this crossed the line";
# these say by how much, so a marginal row reads differently from a hopeless one.
DIAGNOSTIC_COLUMNS = (
    "frac_draws_below_floor",
    "frac_draws_above_ceiling",
    "posterior_prior_width_ratio",
)

# A row is flagged as prior-dominated when its posterior SD is at least this
# fraction of the prior SD -- i.e. the data narrowed the prior by less than
# ~15%. Not a physical constant; a reporting convention, exposed as a kwarg.
DEFAULT_PRIOR_DOMINATED_RATIO = 0.85


def _flat(da: xr.DataArray) -> np.ndarray:
    """Collapse (chain, draw) into a single draw axis."""
    return np.asarray(da.values).reshape(-1)


def _resolve_param(ds: xr.Dataset, basename: str, suffix: str) -> Optional[np.ndarray]:
    """Return draws for ``basename`` under ``suffix``, or None if absent."""
    for name in (f"{basename}_{suffix}" if suffix else basename, basename):
        if name in ds.data_vars:
            return _flat(ds[name])
    return None


def _as_column(value: Any, n: int, name: str) -> Optional[np.ndarray]:
    """Broadcast a scalar or length-N array to shape (N,); None passes through."""
    if value is None:
        return None
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 0:
        return np.full(n, float(arr))
    arr = arr.reshape(-1)
    if arr.size != n:
        raise ValueError(
            f"{name} has length {arr.size} but there are {n} observations; "
            "pass a scalar to broadcast, or one value per observation."
        )
    return arr


def compute_quality_flags(
    proxyObs: Union[np.ndarray, list],
    fwd_posterior: xr.Dataset,
    *,
    predictors: Optional[Dict[str, Any]] = None,
    prior_sigma_t: Optional[float] = None,
    result: Optional[Dict[str, Any]] = None,
    tex86: Optional[Union[float, np.ndarray]] = None,
    suffix: Optional[str] = None,
    domain_confidence: float = 0.90,
    prior_dominated_ratio: float = DEFAULT_PRIOR_DOMINATED_RATIO,
) -> pd.DataFrame:
    """Flag observations a reconstruction cannot support, one row per input.

    Parameters
    ----------
    proxyObs : array-like, shape (N,)
        The observations handed to the inverse model.
    fwd_posterior : xr.Dataset
        The forward calibration the reconstruction used. Both the parameter
        draws and the ``attrs`` recording the calibration's own data range are
        read from it.
    predictors : dict, optional
        ``{"gdgt23ratio": ..., "no3": ...}`` as passed to the reconstruction.
        Scalars are broadcast. Absent predictors that the calibration uses are
        reported by ``predictor_missing``.
    prior_sigma_t : float, optional
        The temperature prior SD. Required for ``prior_dominated``; without it
        that column is ``pd.NA``.
    result : dict, optional
        The reconstruction result. ``prior_dominated`` needs ``p16``/``p84``
        from it; without it that column is ``pd.NA``.
    tex86 : float or array-like, optional
        TEX86 for the same samples. The published calibration-domain ellipse is
        two-dimensional (TEX86 x Scaled RI), so ``outside_domain`` can only be
        evaluated when both are available; it is ``pd.NA`` otherwise.
    suffix : str, optional
        Parameter suffix to read (``"crtp"``, ``"culmeso"``, ...). Chosen by the
        usual priority when omitted.
    domain_confidence : float, default 0.90
        Confidence level of the Mahalanobis ellipse.
    prior_dominated_ratio : float, default 0.85
        Posterior/prior SD ratio at or above which a row is prior-dominated.

    Returns
    -------
    pd.DataFrame
        N rows. Boolean columns from :data:`FLAG_COLUMNS`, graded columns from
        :data:`DIAGNOSTIC_COLUMNS`, and ``any_flag``.

        A check that could not be evaluated is ``pd.NA``, never ``False`` ---
        "not assessed" and "passed" are different answers, and collapsing them
        would quietly launder the first into the second. ``any_flag`` therefore
        ORs only what was actually evaluated, and only the defect columns:
        :data:`ADVISORY_COLUMNS` are reported but do not vote.
    """
    y = np.asarray(proxyObs, dtype=float).reshape(-1)
    n = y.size
    attrs = fwd_posterior.attrs
    predictors = dict(predictors or {})

    out: Dict[str, Any] = {}

    suffix = choose_suffix(fwd_posterior, ["t0", "b", "k"], preferred=suffix)
    b = _resolve_param(fwd_posterior, "b", suffix)
    if b is None:
        raise ValueError(
            f"No lower-asymptote parameter 'b' (suffix {suffix!r}) in this "
            "posterior; the floor and ceiling checks cannot be evaluated."
        )

    use_g23 = bool(attrs.get("use_gdgt23ratio", 0))
    use_no3 = bool(attrs.get("use_no3", 0))
    g23 = _as_column(predictors.get("gdgt23ratio"), n, "gdgt23ratio")
    no3 = _as_column(predictors.get("no3"), n, "no3")

    # ── 1-2. Below the floor / above the ceiling ────────────────────────────
    # Where the attainable range of mu sits depends on the parameterization:
    #
    #   t0shift  (gamma on T0)  mu = b + (1-b)/(...)      -> (b, 1) for every
    #                           draw, whatever the predictors do. Bounded by
    #                           construction; that is the point of the model.
    #   additive (beta on mu)   mu = b + corr + (1-b)/(...) -> (b+corr, 1+corr),
    #                           so the floor moves with the predictors and
    #                           differs per observation as well as per draw.
    #
    # Either way the floor is a distribution over draws, not one number, so the
    # honest summary is the fraction of the calibration that rules a point out.
    is_t0shift = any(
        v == "gamma_G23" or v.startswith("gamma_G23_")
        or v == "gamma_NO3" or v.startswith("gamma_NO3_")
        for v in fwd_posterior.data_vars
    )

    if is_t0shift:
        # (n_draws,) -> compare against every observation at once.
        floor = b[None, :]
        ceiling = np.ones_like(floor)
    else:
        corr = np.zeros((n, b.size))
        if use_g23 and g23 is not None:
            beta_g23 = _resolve_param(fwd_posterior, "beta_G23", suffix)
            if beta_g23 is not None:
                corr += np.outer(np.nan_to_num(g23), beta_g23)
        if use_no3 and no3 is not None:
            beta_no3 = _resolve_param(fwd_posterior, "beta_NO3", suffix)
            if beta_no3 is not None:
                cutoff = float(attrs.get("no3_cutoff", 0.0))
                # Mirrors the Stan model: the correction applies only inside
                # the window, and is exactly zero outside it.
                active = (no3 > 0.0) & (no3 < cutoff)
                logno3 = np.where(active, np.log10(np.where(active, no3, 1.0) + 1e-9), 0.0)
                corr += np.outer(np.nan_to_num(logno3), beta_no3)
        floor = b[None, :] + corr
        ceiling = 1.0 + corr

    finite = np.isfinite(y)
    yy = np.where(finite, y, np.nan)[:, None]
    with np.errstate(invalid="ignore"):
        frac_below = np.nanmean((yy < floor).astype(float), axis=1)
        frac_above = np.nanmean((yy > ceiling).astype(float), axis=1)
    frac_below = np.where(finite, frac_below, np.nan)
    frac_above = np.where(finite, frac_above, np.nan)

    out["frac_draws_below_floor"] = frac_below
    out["frac_draws_above_ceiling"] = frac_above
    # Flag once the majority of the calibration says the value is unreachable.
    out["proxy_below_floor"] = _bool_or_na(frac_below > 0.5, finite)
    out["proxy_above_ceiling"] = _bool_or_na(frac_above > 0.5, finite)

    # ── 3. Outside the calibration's own proxy range ────────────────────────
    lo = attrs.get("proxyObs_crtp_min", attrs.get("proxyObs_min"))
    hi = attrs.get("proxyObs_crtp_max", attrs.get("proxyObs_max"))
    if lo is not None and hi is not None:
        out["proxy_extrapolated"] = _bool_or_na(
            (y < float(lo)) | (y > float(hi)), finite
        )
    else:
        out["proxy_extrapolated"] = pd.array([pd.NA] * n, dtype="boolean")

    # ── 4. A predictor the calibration uses, missing for this row ───────────
    # Absent is not neutral: Stan receives 0, which asserts a ratio of zero
    # rather than switching the correction off.
    missing = np.zeros(n, dtype=bool)
    assessed_missing = True
    if use_g23:
        missing |= np.isnan(g23) if g23 is not None else np.ones(n, dtype=bool)
    if use_no3:
        missing |= np.isnan(no3) if no3 is not None else np.ones(n, dtype=bool)
    if not (use_g23 or use_no3):
        assessed_missing = False
    out["predictor_missing"] = (
        pd.array(missing, dtype="boolean")
        if assessed_missing
        else pd.array([pd.NA] * n, dtype="boolean")
    )

    # ── 5. Predictors outside the calibration's range ───────────────────────
    pred_extrap = np.zeros(n, dtype=bool)
    assessed_extrap = False
    for key, arr, prefix in (
        ("gdgt23ratio", g23, "gdgt23ratio_crtp"),
        ("no3", no3, "no3_crtp"),
    ):
        p_lo, p_hi = attrs.get(f"{prefix}_min"), attrs.get(f"{prefix}_max")
        if arr is None or p_lo is None or p_hi is None:
            continue
        assessed_extrap = True
        with np.errstate(invalid="ignore"):
            pred_extrap |= np.nan_to_num(
                (arr < float(p_lo)) | (arr > float(p_hi)), nan=False
            ).astype(bool)
    out["predictor_extrapolated"] = (
        pd.array(pred_extrap, dtype="boolean")
        if assessed_extrap
        else pd.array([pd.NA] * n, dtype="boolean")
    )

    # ── 6. NO3 outside the correction window ───────────────────────────────
    # Usually deliberate -- no3=10 with a cutoff of 1.0 is the documented way to
    # switch the correction off -- but it should be visible rather than assumed.
    if use_no3 and no3 is not None:
        cutoff = float(attrs.get("no3_cutoff", 0.0))
        with np.errstate(invalid="ignore"):
            inactive = ~((no3 > 0.0) & (no3 < cutoff))
        out["no3_correction_inactive"] = _bool_or_na(inactive, np.isfinite(no3))
    else:
        out["no3_correction_inactive"] = pd.array([pd.NA] * n, dtype="boolean")

    # ── 7. Outside the published calibration domain ─────────────────────────
    out["outside_domain"] = _domain_flag(
        y, tex86, n, attrs, domain_confidence
    )

    # ── 8. Prior-dominated posterior ────────────────────────────────────────
    ratio = np.full(n, np.nan)
    if result is not None and prior_sigma_t and prior_sigma_t > 0:
        p16, p84 = result.get("p16"), result.get("p84")
        if p16 is not None and p84 is not None:
            post_sd = (np.asarray(p84, dtype=float) - np.asarray(p16, dtype=float)) / 2.0
            if post_sd.size == n:
                ratio = post_sd / float(prior_sigma_t)
    out["posterior_prior_width_ratio"] = ratio
    out["prior_dominated"] = _bool_or_na(
        ratio >= prior_dominated_ratio, np.isfinite(ratio)
    )

    df = pd.DataFrame(
        {c: out[c] for c in FLAG_COLUMNS + DIAGNOSTIC_COLUMNS},
        index=pd.RangeIndex(n),
    )
    # Only evaluated checks vote, and only defects: a column that is entirely
    # pd.NA contributes nothing rather than poisoning every row to NA, and the
    # advisory columns are reported without counting against the row.
    df["any_flag"] = (
        df[list(DEFECT_COLUMNS)].fillna(False).any(axis=1).astype("boolean")
    )
    return df


def _bool_or_na(values: np.ndarray, assessed: np.ndarray) -> "pd.arrays.BooleanArray":
    """Nullable booleans: NA wherever the check could not be evaluated."""
    out = pd.array(np.asarray(values, dtype=bool), dtype="boolean")
    out[~np.asarray(assessed, dtype=bool)] = pd.NA
    return out


def _domain_flag(
    y: np.ndarray,
    tex86: Optional[Union[float, np.ndarray]],
    n: int,
    attrs: Dict[str, Any],
    confidence: float,
) -> "pd.arrays.BooleanArray":
    """Screen against the published calibration ellipse, when it applies.

    Uses ``detect_outliers_manual``: the ellipse plus the manuscript's warm-end
    exception, which retains samples with TEX86 and Scaled RI both above 0.75
    because the calibration itself retains them. The bare ellipse would flag
    warm samples the calibration actually covers.
    """
    na = pd.array([pd.NA] * n, dtype="boolean")
    if tex86 is None:
        return na

    # The ellipse is fitted on TEX86 x scaledRI_cren3. Screening a different
    # proxy against it would be comparing an index to an ellipse built for
    # another one.
    proxy_name = attrs.get("proxy_name")
    if proxy_name not in (None, "scaledRI_cren3"):
        warnings.warn(
            f"outside_domain not evaluated: the published calibration domain is "
            f"defined on scaledRI_cren3, but this reconstruction uses "
            f"{proxy_name!r}. Pass the matching proxy to screen against it.",
            UserWarning, stacklevel=3,
        )
        return na

    tx = _as_column(tex86, n, "tex86")
    try:
        from .data.screening import MahalanobisOutlierDetector

        detector = MahalanobisOutlierDetector.from_calibration(confidence=confidence)
        df = pd.DataFrame({"TEX86": tx, "scaledRI_cren3": y})
        flagged = detector.detect_outliers_manual(df, on_unscorable="ignore")
    except Exception as exc:  # noqa: BLE001 - a screen failure must not sink a run
        warnings.warn(
            f"outside_domain could not be evaluated ({type(exc).__name__}: {exc}); "
            "the column is left as NA.",
            UserWarning, stacklevel=3,
        )
        return na

    # The detector returns nullable booleans, with NA for rows it could not
    # score. Those rows are unassessed, so they are NA'd out by `scorable`
    # anyway; filling here only makes the dtype convertible.
    flagged = np.asarray(pd.Series(flagged).fillna(False), dtype=bool)
    scorable = np.isfinite(tx) & np.isfinite(y)
    return _bool_or_na(flagged, scorable)
