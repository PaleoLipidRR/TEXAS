from pathlib import Path
from typing import Union, Optional, Dict, List
import numpy as np
import xarray as xr
from cmdstanpy import CmdStanModel

# ─── TYPES & HELPERS ───────────────────────────────────────────────────────────

def _ensure_numpy(x):
    return x.values if hasattr(x, "values") else np.asarray(x)

# ─── FORWARD & INVERSE LOGISTIC (GENERALIZED) ─────────────────────────────────

def pred_logistic_general(
    x: np.ndarray,
    x0: np.ndarray,
    k: np.ndarray,
    b: np.ndarray,
    L: np.ndarray,
    betas: Dict[str, np.ndarray],
    factors: Dict[str, np.ndarray]
) -> np.ndarray:
    """
    Forward logistic with arbitrary linear factors:
      y = logistic(x) + sum_j beta_j * factor_j
    Returns array shape (n_draws, x.size).
    """
    x_arr = _ensure_numpy(x)
    x0_arr, k_arr, b_arr, L_arr = map(_ensure_numpy, (x0, k, b, L))
    # base logistic term
    base = L_arr[:, None] / (1 + np.exp(-k_arr[:, None] * (x_arr[None, :] - x0_arr[:, None]))) + b_arr[:, None]
    # add linear factors
    lin = np.zeros_like(base)
    for name, beta in betas.items():
        fac = _ensure_numpy(factors[name])
        beta_arr = _ensure_numpy(beta)
        lin += beta_arr[:, None] * fac[None, :]
    return base + lin


def inv_logistic_general(
    y: np.ndarray,
    x0: np.ndarray,
    k: np.ndarray,
    b: np.ndarray,
    L: np.ndarray,
    betas: Dict[str, np.ndarray],
    factors: Dict[str, np.ndarray]
) -> np.ndarray:
    """
    Inverse logistic with arbitrary linear factors:
      y = logistic(x) + sum_j beta_j * factor_j
    Returns array shape (n_draws, y.size).
    """
    y_arr = _ensure_numpy(y)
    x0_arr, k_arr, b_arr, L_arr = map(_ensure_numpy, (x0, k, b, L))
    # compute linear combination per draw & obs
    lin = np.zeros((x0_arr.size, y_arr.size))
    for name, beta in betas.items():
        fac = _ensure_numpy(factors[name])
        beta_arr = _ensure_numpy(beta)
        lin += beta_arr[:, None] * fac[None, :]
    # subtract linear terms
    y_corr = y_arr[None, :] - lin
    # invert logistic
    arg = L_arr[:, None] / (y_corr - b_arr[:, None]) - 1
    return x0_arr[:, None] - (1.0 / k_arr[:, None]) * np.log(arg)

# ─── STAN INTERFACE & CACHE ─────────────────────────────────────────────────

_MODEL_CACHE: Dict[Path, CmdStanModel] = {}

def get_posteriors(
    data: dict,
    stan_filename: str,
    stan_models_dir: Union[Path, str] = None,
    chains: int = 4,
    iter_warmup: int = 500,
    iter_sampling: int = 1000,
    seed: Optional[int] = 42
) -> xr.Dataset:
    if stan_models_dir is None:
        stan_models_dir = Path(__file__).parent / "stan_models"
    model_path = Path(stan_models_dir) / stan_filename
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
    for var in fit.stan_variables():
        arr = fit.stan_variable(var)
        dim_names = ["draw"] + [f"dim_{i}" for i in range(1, arr.ndim)]
        coords = {name: np.arange(sz) for name, sz in zip(dim_names, arr.shape)}
        ds[var] = xr.DataArray(data=arr, dims=dim_names, coords=coords, name=var)
    return ds

# ─── GENERAL ENSEMBLE FUNCTIONS ─────────────────────────────────────────────

def make_ensemble(
    y: np.ndarray,
    posterior: xr.Dataset,
    n_draws: int = 1000,
    seed: Optional[int] = None,
    **factors: np.ndarray
) -> np.ndarray:
    """
    Draw samples from a posterior with parameters: x0,k,b,L and any beta0_* keys,
    then invert: x = inv_logistic_general(y, x0,k,b,L, betas, factors)
    *factors: pass arrays named by suffix after 'beta0_', e.g. z3, aa3
    """
    if seed is not None:
        np.random.seed(seed)
    # bootstrap draws
    sel = np.random.choice(posterior.dims["draw"], size=n_draws, replace=True)
    P = posterior.isel(draw=sel)
    # extract base params
    x0 = P["x0"].values
    k  = P["k"].values
    b  = P["b"].values
    # derive or extract L
    L = P["L"].values if "L" in P else (1 - P["b"]).values
    # collect beta arrays
    betas = {name.replace("beta0_", ""): P[name].values
             for name in P.data_vars if name.startswith("beta0_")}
    # ensure factors provided for each beta
    for name in betas:
        if name not in factors:
            raise ValueError(f"Missing factor array for beta0_{name}")
    return inv_logistic_general(y=y, x0=x0, k=k, b=b, L=L,
                                 betas=betas, factors=factors)


def make_forward_ensemble(
    x: np.ndarray,
    posterior: xr.Dataset,
    n_draws: int = 1000,
    seed: Optional[int] = None,
    **factors: np.ndarray
) -> np.ndarray:
    if seed is not None:
        np.random.seed(seed)
    sel = np.random.choice(posterior.dims["draw"], size=n_draws, replace=True)
    P = posterior.isel(draw=sel)
    x0 = P["x0"].values
    k  = P["k"].values
    b  = P["b"].values
    L = P["L"].values if "L" in P else (1 - P["b"]).values
    betas = {name.replace("beta0_", ""): P[name].values
             for name in P.data_vars if name.startswith("beta0_")}
    for name in betas:
        if name not in factors:
            raise ValueError(f"Missing factor array for beta0_{name}")
    return pred_logistic_general(x=x, x0=x0, k=k, b=b, L=L,
                                 betas=betas, factors=factors)
