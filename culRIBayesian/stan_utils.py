from pathlib import Path
from typing import Union, Optional, Dict, List, Callable
from typing_extensions import Literal
from dataclasses import dataclass
import numpy as np
import xarray as xr
from cmdstanpy import CmdStanModel

# ─── TYPES & HELPERS ───────────────────────────────────────────────────────────


def _ensure_numpy(x: Union[np.ndarray, xr.DataArray]) -> np.ndarray:
    """Convert xarray.DataArray (or similar) to NumPy array."""
    return x.values if hasattr(x, "values") else np.asarray(x)

# ─── FORWARD / INVERSE LOGISTIC FUNCTIONS ────────────────────────────────────

def pred_logistic(
    x: np.ndarray, x0: np.ndarray, k: np.ndarray, L: np.ndarray, b: np.ndarray
) -> np.ndarray:
    """Forward logistic: temperature → scaled RI."""
    x, x0, k, L, b = map(_ensure_numpy, (x, x0, k, L, b))
    return L / (1 + np.exp(-k * (x[:, None] - x0))) + b

def pred_logistic_multivariate(
    x: np.ndarray,
    z: np.ndarray,
    x0: np.ndarray,
    k: np.ndarray,
    L: np.ndarray,
    b: np.ndarray,
    beta0: np.ndarray,
    beta1: np.ndarray
) -> np.ndarray:
    """Forward multivariate: (temperature, z) → scaled RI."""
    x, z = map(_ensure_numpy, (x, z))
    x0, k, L, b, beta0, beta1 = map(_ensure_numpy, (x0, k, L, b, beta0, beta1))
    base   = L / (1 + np.exp(-k * (x[:, None] - x0))) + b
    linear = beta0 * z[:, None] + beta1
    return base + linear

def inv_logistic(
    y: np.ndarray, x0: np.ndarray, k: np.ndarray, L: np.ndarray, b: np.ndarray
) -> np.ndarray:
    """Inverse logistic: scaled RI → temperature."""
    y, x0, k, L, b = map(_ensure_numpy, (y, x0, k, L, b))
    arg = L / (y[:, None] - b) - 1
    return x0[None, :] - (1.0 / k[None, :]) * np.log(arg)

def inv_logistic_multivariate(
    y: np.ndarray,
    z: np.ndarray,
    x0: np.ndarray,
    k: np.ndarray,
    L: np.ndarray,
    b: np.ndarray,
    beta0: np.ndarray,
    beta1: np.ndarray
) -> np.ndarray:
    """Inverse multivariate: (scaled RI, z) → temperature."""
    y, z = map(_ensure_numpy, (y, z))
    x0, k, L, b, beta0, beta1 = map(_ensure_numpy, (x0, k, L, b, beta0, beta1))
    linear = beta0[None, :] * z[:, None] + beta1[None, :]
    base   = y[:, None] - linear
    arg    = L[None, :] / (base - b[None, :]) - 1.0
    return x0[None, :] - (1.0 / k[None, :]) * np.log(arg)

# ─── MODEL SPECIFICATION & CACHE ──────────────────────────────────────────────
# Allowed model names
ModelName = Literal[
    "logistic_free_upper",
    "logistic_fixed_upper",
    "logistic_fixed_upper_multivariate",
    "logistic_fixed_upper_multivariate_fixedbeta1",
    "hierarchical_coretop",
]

@dataclass
class ModelSpec:
    params:       List[str]    # names of parameters in the posterior dataset
    fn:           Callable     # inv function (for make_ensemble)
    needs_z:      bool = False # whether the model is multivariate
    L_from_b:     bool = False # whether L should be computed as 1 - b
    zero_beta1:   bool = False # whether beta1 should be forced to zero

_MODEL_SPECS: Dict[ModelName, ModelSpec] = {
    "logistic_free_upper": ModelSpec(
        params=["x0","k","L","b"], fn=inv_logistic
    ),
    "logistic_fixed_upper": ModelSpec(
        params=["x0","k","b"], fn=inv_logistic,
        L_from_b=True
    ),
    "logistic_fixed_upper_multivariate": ModelSpec(
        params=["x0","k","b","beta0","beta1"],
        fn=inv_logistic_multivariate,
        needs_z=True,
        L_from_b=True
    ),
    "logistic_fixed_upper_multivariate_fixedbeta1": ModelSpec(
        params=["x0","k","b","beta0"],
        fn=inv_logistic_multivariate,
        needs_z=True,
        L_from_b=True,
        zero_beta1=True
    ),
    "hierarchical_coretop": ModelSpec(
        params=["x0_3", "k_3", "b_3"],
        fn=inv_logistic,     # or pred_logistic for forward
        L_from_b=True,
    ),    
}

# cache compiled Stan models
_MODEL_CACHE: Dict[Path, CmdStanModel] = {}

# ─── STAN INTERFACE ──────────────────────────────────────────────────────────

def get_posteriors(
    data: dict,
    stan_filename: str,
    stan_models_dir: Union[Path,str] = None,
    chains: int = 4,
    iter_warmup: int = 500,
    iter_sampling: int = 1000,
    seed: Optional[int] = 42
) -> xr.Dataset:
    """
    Compile (once) & sample a CmdStan .stan file, returning all draws
    in an xarray.Dataset with a single 'draw' dimension.
    """
    if stan_models_dir is None:
        stan_models_dir = Path(__file__).parent / "stan_models"
    stan_models_dir = Path(stan_models_dir)
    model_path = stan_models_dir / stan_filename

    if model_path not in _MODEL_CACHE:
        _MODEL_CACHE[model_path] = CmdStanModel(stan_file=str(model_path))
    model = _MODEL_CACHE[model_path]

    if seed is not None:
        np.random.seed(seed)
    fit = model.sample(
        data=data,
        chains=chains,
        iter_warmup=iter_warmup,
        iter_sampling=iter_sampling,
        seed=seed,
        parallel_chains=chains,
        show_console=True
    )

    ds = xr.Dataset()
    for var in fit.stan_variables().keys():
        arr = fit.stan_variable(var)
        ds[var] = xr.DataArray(
            arr,
            dims=("draw",) + arr.shape[1:],
            name=var
        )
    return ds

# ─── INVERSE ENSEMBLE (scaledRI → temperature) ───────────────────────────────

def make_ensemble(
    y:            np.ndarray,
    posterior:    xr.Dataset,
    model_name:   ModelName,
    z:            Optional[np.ndarray] = None,
    n_draws:      int = 1000,
    seed:         Optional[int] = None
) -> np.ndarray:
    """
    Draw n_draws samples from the posterior and invert:
    - Univariate:  inv_logistic(y, x0,k,L,b)
    - Multivariate: inv_logistic_multivariate(y,z,x0,k,L,b,beta0,beta1)
    Returns array shape (n_draws, y.size).
    """
    spec = _MODEL_SPECS[model_name]
    if seed is not None:
        np.random.seed(seed)

    sel = np.random.choice(posterior.dims["draw"], size=n_draws, replace=True)
    P   = posterior.isel(draw=sel)[spec.params]

    if model_name == "hierarchical_coretop":
        # P currently has vars ["x0_3","k_3","b_3"]
        # rename them to ["x0","k","b"] before we compute L and call inv_logistic
        P = P.rename_vars({"x0_3": "x0", "k_3": "k", "b_3": "b"})
        params_list = ["x0","k","b"]
    else:
        params_list = spec.params

    # derive L if requested
    if spec.L_from_b:
        try:
            P["L"] = 1 - P["b"]
        except KeyError:
            raise ValueError(f"Model {model_name!r} requires 'b' to compute 'L', but 'b' is missing in the posterior dataset.")
    # zero beta1 if requested
    if spec.zero_beta1:
        P["beta1"] = xr.zeros_like(P["beta0"])

    # build argument list
    arg_names = list(params_list)
    if spec.L_from_b:
        arg_names.append("L")
    if spec.zero_beta1:
        arg_names.append("beta1")
    args = {p: P[p] for p in arg_names}

    if spec.needs_z:
        if z is None:
            raise ValueError(f"{model_name!r} requires 'z', but none was provided")
        return spec.fn(y=y, z=z, **args)
    return spec.fn(y=y, **args)

# ─── FORWARD ENSEMBLE (temperature → scaledRI) ────────────────────────────────

def make_forward_ensemble(
    x:            np.ndarray,
    posterior:    xr.Dataset,
    model_name:   ModelName,
    z:            Optional[np.ndarray] = None,
    n_draws:      int = 1000,
    seed:         Optional[int] = None
) -> np.ndarray:
    """
    Draw n_draws samples from the posterior and forward‐predict:
    - Univariate:  pred_logistic(x, x0,k,L,b)
    - Multivariate: pred_logistic_multivariate(x,z,x0,k,L,b,beta0,beta1)
    Returns array shape (n_draws, x.size).
    """
    spec = _MODEL_SPECS[model_name]
    if seed is not None:
        np.random.seed(seed)

    sel = np.random.choice(posterior.dims["draw"], size=n_draws, replace=True)
    P   = posterior.isel(draw=sel)[spec.params]

    if model_name == "hierarchical_coretop":
        # P currently has vars ["x0_3","k_3","b_3"]
        # rename them to ["x0","k","b"] before we compute L and call inv_logistic
        P = P.rename_vars({"x0_3": "x0", "k_3": "k", "b_3": "b"})
        params_list = ["x0","k","b"]
    else:
        params_list = spec.params
    # derive L if requested

    if spec.L_from_b:
        try:
            P["L"] = 1 - P["b"]
        except KeyError:
            raise ValueError(f"Model {model_name!r} requires 'b' to compute 'L', but 'b' is missing in the posterior dataset.")
    # zero beta1 if requested
    if spec.zero_beta1:
        P["beta1"] = xr.zeros_like(P["beta0"])

    arg_names = list(params_list)
    if spec.L_from_b:
        arg_names.append("L")
    if spec.zero_beta1:
        arg_names.append("beta1")
    args = {p: P[p] for p in arg_names}

    if spec.needs_z:
        if z is None:
            raise ValueError(f"{model_name!r} requires 'z', but none was provided")
        # broadcast z to match x if needed
        if z.shape != x.shape:
            z = np.broadcast_to(z, x.shape)
        return pred_logistic_multivariate(x, z, **args)

    return pred_logistic(x, **args)
