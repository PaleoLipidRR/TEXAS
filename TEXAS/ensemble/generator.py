# TEXAS/ensemble/generator.py

import numpy as np
import xarray as xr
from typing import Callable, List, Optional, Dict, Any

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
    no3_cutoff: float = 50.0
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

    # 3) detect multivariate
    name = model_function.__name__
    is_multi = "multivariate" in name
    use_gdgt = post_ds.attrs.get("use_gdgt23ratio",False)
    use_no3 = post_ds.attrs.get("use_no3",False)
    # fallback if attrs missing:
    if "use_gdgt23ratio" not in post_ds.attrs:
        use_gdgt = any(v.startswith("beta0_gdgt23ratio_") for v in post_ds.data_vars)
    if "use_no3" not in post_ds.attrs:
        use_no3 = any(v.startswith("beta0_no3_") for v in post_ds.data_vars)

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
                params["no3_cutoff"] = no3_cutoff
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
            "model_function": name,
            "seed": seed,
            "percentiles": percentiles,
            "is_multivariate": is_multi,
            "use_gdgt23ratio": bool(use_gdgt),
            "use_no3": bool(use_no3),
            "gdgt23ratio_provided": gdgt23ratio is not None,
            "no3_provided": no3 is not None,
        }
    return out

def generate_ensemble_auto(
    post_ds: xr.Dataset,
    x_vals: np.ndarray,
    model_type: str = "auto",
    gdgt23ratio: Optional[np.ndarray] = None,
    no3: Optional[np.ndarray] = None,
    no3_cutoff: float = 50.0,
    **kwargs
) -> Dict[str, np.ndarray]:
    """
    Automatically generate ensemble with auto‐detected model types.
    (Exact port of your old stan_utils.py version.)
    """
    # detect inverse‐T vs forward
    model_name = post_ds.attrs.get("stan_model_name","")
    is_inv = ("invT_" in model_name) or ("t_est" in post_ds.data_vars)

    if model_type in ("auto","inverse") and is_inv:
        # dispatch to invT Stan code
        # we assume you have written a helper for inverse‐T ensembles:
        from .invT import generate_invT_ensemble  # you’ll need to implement this
        return generate_invT_ensemble(
            post_ds, x_vals,
            gdgt23ratio=gdgt23ratio,
            no3=no3,
            no3_cutoff=no3_cutoff,
            **kwargs
        )
    elif model_type in ("auto","forward") and not is_inv:
        # dispatch to forward pipeline
        det = detect_model_and_params(post_ds, suffix=kwargs.get("suffix"))
        print("DEBUG: Detected model and params",det)
        return generate_ensemble(
            post_ds=post_ds,
            model_function=det["model_function"],
            x_vals=x_vals,
            param_names=det["param_names"],
            suffix=det.get("suffix"),
            gdgt23ratio=gdgt23ratio,
            no3=no3,
            no3_cutoff=no3_cutoff,
            **kwargs
        )
    else:
        raise ValueError(f"Cannot dispatch ensemble_auto(model_type={model_type}, is_inv={is_inv})")