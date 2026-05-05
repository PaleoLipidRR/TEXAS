# TEXAS/ensemble/generator.py

import numpy as np
import xarray as xr
from typing import Callable, List, Optional, Dict, Any, Literal

from .detection import detect_model_and_params
from TEXAS.stan.io import load_posterior
from TEXAS.stan.sampler import StanSampler, StanCompiler

def generate_ensemble(
    post_ds: xr.Dataset,
    model_function: Callable[..., np.ndarray],
    x_vals: np.ndarray,
    param_names: List[str],
    suffix: Optional[str] = None,
    n_draws: int = 500,
    seed: Optional[int] = 42,
    percentiles: List[float] = [5, 50, 95],
    return_full_ensemble: bool = False,
    # Multivariate model parameters
    gdgt23ratio: Optional[np.ndarray] = None,
    no3: Optional[np.ndarray] = None,
    no3_cutoff: Optional[float] = None,
    # NEW authoritative hints from detector
    is_multivariate: Optional[bool] = None,
    use_gdgt23ratio_flag: Optional[bool] = None,
    use_no3_flag: Optional[bool] = None,
) -> Dict[str, np.ndarray]:
    """
    Generate an ensemble of curves from a posterior dataset using any model function.
    (Exact port of your old stan_utils.py version.)
    """
    if seed is not None:
        np.random.seed(seed)

    # 1) require suffix from detector or explicit arg
    if suffix is None:
        raise ValueError(
            "Suffix must be specified explicitly or via detect_model_and_params()."
        )

    # 2) build full var names & check
    full_vars = [f"{p}_{suffix}" for p in param_names]
    missing = [v for v in full_vars if v not in post_ds.data_vars]
    if missing:
        expected = full_vars
        avail = [v for v in post_ds.data_vars if any(v.startswith(f"{p}_") or v == p for p in param_names)]
        raise ValueError(
            f"Missing parameters: {missing}. Suffix='{suffix}'.\n"
            f"Expected: {expected}\n"
            f"Available (matching): {sorted(avail)}"
        )

    # 3) decide multivariate & use_* flags (prefer caller hints)
    if is_multivariate is None:
        is_multi = "multivariate" in model_function.__name__
    else:
        is_multi = bool(is_multivariate)

    # STRICT attr-based flags only (no data_vars scanning)
    if use_gdgt23ratio_flag is None:
        # apply only if the attr exists and is truthy
        use_gdgt = bool(post_ds.attrs.get("use_gdgt23ratio", False))
    else:
        use_gdgt = bool(use_gdgt23ratio_flag)

    if use_no3_flag is None:
        # apply only if the attr exists and is truthy
        use_no3 = bool(post_ds.attrs.get("use_no3", False))
    else:
        use_no3 = bool(use_no3_flag)

    # Resolve cutoff only if NO3 correction is enabled by attrs/flag
    if use_no3:
        eff_no3_cutoff = (
            no3_cutoff
            if no3_cutoff is not None
            else post_ds.attrs.get("no3_cutoff", 0.0)
        )
    else:
        eff_no3_cutoff = 0.0

    # 4) sample draws
    df = post_ds[full_vars].to_dataframe().reset_index()
    total = len(df)
    if n_draws > total:
        print(f"Warning: only {total} draws available, returning those")
        n_draws = total
    sampled = df.sample(n=n_draws, random_state=seed).reset_index(drop=True)

    # 5) generate
    x = np.asarray(x_vals)
    ensemble = np.zeros((n_draws, x.size))
    for i,row in enumerate(sampled.itertuples(index=False)):
        params = {p: getattr(row, f"{p}_{suffix}") for p in param_names}
        if is_multi:
            if use_gdgt and gdgt23ratio is not None:
                params["gdgt23ratio"] = gdgt23ratio
            if use_no3 and no3 is not None:
                params["no3"] = no3
                params["no3_cutoff"] = eff_no3_cutoff
        try:
            ensemble[i] = model_function(x, **params)
        except Exception as e:
            raise RuntimeError(f"Draw {i} failed with {params}: {e}")

    # 6) package results
    out: Dict[str, Any] = {"x_vals": x}
    for q in percentiles:
        out[f"p{int(q)}"] = np.percentile(ensemble, q, axis=0)
        
    if return_full_ensemble:
        out["ensemble"] = ensemble
        out["metadata"] = {
            "n_draws": n_draws,
            "suffix": suffix,
            "param_names": param_names,
            "model_function": model_function.__name__,
            "seed": seed,
            "percentiles": percentiles,
            "is_multivariate": is_multi,
            "use_gdgt23ratio": bool(use_gdgt),
            "use_no3": bool(use_no3),
            "gdgt23ratio_provided": gdgt23ratio is not None,
            "no3_provided": no3 is not None,
            "no3_cutoff_effective": float(eff_no3_cutoff),
        }
    return out

def generate_ensemble_auto(
    post_ds: xr.Dataset,
    x_vals: np.ndarray,
    model_type: Literal["auto","forward","inverse"] = "auto",
    gdgt23ratio: Optional[np.ndarray] = None,
    no3: Optional[np.ndarray] = None,
    no3_cutoff: Optional[float] = None,
    return_full_ensemble: bool = False,
    suffix: Optional[str] = None,
    **kwargs
) -> Dict[str, np.ndarray]:
    """
    Sample draws from a forward posterior and compute calibration-curve percentiles.

    Inspects the posterior's ``stan_model_name`` attr and ``data_vars`` to
    determine the model function, parameter names, and optional-predictor
    flags automatically, then delegates to ``generate_ensemble``.

    Parameters
    ----------
    post_ds : xr.Dataset
        Forward calibration posterior returned by ``get_posterior()`` or
        loaded with ``load_posterior()``.
    x_vals : np.ndarray
        Temperature values (°C) at which to evaluate the calibration curve.
    model_type : {"auto", "forward", "inverse"}
        Force forward or inverse dispatch; ``"auto"`` (default) infers from
        the posterior.  InvT posteriors are not supported — use
        ``predict_T_from_proxyObs()`` instead.
    gdgt23ratio : np.ndarray, optional
        GDGT-2/3 ratio values; required when the posterior was fitted with
        a multivariate (GDGT-2/3) model.
    no3 : np.ndarray, optional
        NO₃ concentrations (µmol/L); required when the posterior uses the
        NO₃ correction.
    no3_cutoff : float, optional
        Override the NO₃ cutoff from the posterior attrs.
    return_full_ensemble : bool
        If ``True``, return the full M × N draw matrix in addition to
        percentiles.  Default ``False``.
    suffix : str, optional
        Force a specific parameter suffix (e.g. ``"crtp"``); overrides
        auto-detection.
    **kwargs
        Forwarded to ``generate_ensemble``.

    Returns
    -------
    dict
        Keys ``"p1"`` … ``"p99"`` (and optionally ``"ensemble"``) — each
        a numpy array of length ``len(x_vals)``.

    Raises
    ------
    NotImplementedError
        If called with an invT posterior.
    """
    model_name = post_ds.attrs.get("stan_model_name", "")
    is_inv = ("invT_" in model_name) or ("t_est" in post_ds.data_vars)

    if model_type in ("auto", "inverse") and is_inv:
        raise NotImplementedError(
            "generate_ensemble_auto() does not support invT posteriors. "
            "Use predict_T_from_proxyObs() for inverse temperature reconstruction."
        )

    elif model_type in ("auto", "forward") and not is_inv:
        det = detect_model_and_params(post_ds, suffix=suffix)  # <-- use explicit suffix
        # precedence: arg > detector > None (resolved inside generate_ensemble)
        resolved_no3_cutoff = no3_cutoff if no3_cutoff is not None else det.get("no3_cutoff")

        return generate_ensemble(
            post_ds=post_ds,
            model_function=det["model_function"],
            x_vals=x_vals,
            param_names=det["param_names"],
            suffix=det.get("suffix"),
            gdgt23ratio=gdgt23ratio,
            no3=no3,
            no3_cutoff=resolved_no3_cutoff,
            is_multivariate=det.get("is_multivariate"),
            use_gdgt23ratio_flag=det.get("use_gdgt23ratio"),
            use_no3_flag=det.get("use_no3"),
            return_full_ensemble=return_full_ensemble,
            **kwargs
        )
    else:
        raise ValueError(f"Cannot dispatch ensemble_auto(model_type={model_type}, is_inv={is_inv})")