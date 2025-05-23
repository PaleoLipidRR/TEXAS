from pathlib import Path
from typing import Union, Optional, Dict, List, Tuple
import numpy as np
import xarray as xr
from cmdstanpy import CmdStanModel
import os


# ─── TYPES & HELPERS ───────────────────────────────────────────────────────────

def _ensure_numpy(x):
    return x.values if hasattr(x, "values") else np.asarray(x)

# ─── BUILD CALIBRATION DATASET ──────────────────────────────────────────────
def build_joint_calibration_data(
    culture: dict,
    mesocosm: dict,
    coretop: dict,
    predictors: Dict[str, Dict[str, np.ndarray]]
) -> Tuple[dict, dict]:
    """
    Build Stan-compatible data and predictor usage flags for joint GDGT calibration.

    Parameters:
    ----------
    culture, mesocosm, coretop : dict
        Each must contain a key "scaledRI" corresponding to ring index observations.

    predictors : dict of dict
        Must contain:
            "thermoT": {
                "culture": array-like,
                "mesocosm": array-like,
                "coretop": array-like
            }
        Optional:
            Any additional predictors (e.g., "gdgt23ratio") with only "coretop" values.

    Returns:
    -------
    data : dict
        Stan-ready data dictionary with appropriately named inputs.

    use_flags : dict
        Dictionary mapping optional predictor names to 1 (used) or 0 (not used).
    """
    OPTIONAL_PREDICTORS = ["gdgt23ratio", "depthIntg_thermoT_no3"]
    data = {}
    use_flags = {}

    # ─── Required predictor: thermoT ──────────────────────
    thermoT = predictors.get("thermoT")
    if thermoT is None:
        raise ValueError("Missing required predictor 'thermoT'")

    data["N_cul"] = len(culture["scaledRI"])
    data["scaledRI_cul"] = _ensure_numpy(culture["scaledRI"])
    data["thermoT_cul"] = _ensure_numpy(thermoT["culture"])

    data["N_meso"] = len(mesocosm["scaledRI"])
    data["scaledRI_meso"] = _ensure_numpy(mesocosm["scaledRI"])
    data["thermoT_meso"] = _ensure_numpy(thermoT["mesocosm"])

    data["N_coretop"] = len(coretop["scaledRI"])
    data["scaledRI_coretop"] = _ensure_numpy(coretop["scaledRI"])
    data["thermoT_coretop"] = _ensure_numpy(thermoT["coretop"])

    # ─── Optional predictors ──────────────────────────────
    print("[build_joint_calibration_data] Building Stan data block...")
    print("  ✓ Using required predictor: thermoT")

    for pred_name in OPTIONAL_PREDICTORS:
        if pred_name in predictors and "coretop" in predictors[pred_name]:
            data[pred_name] = _ensure_numpy(predictors[pred_name]["coretop"])
            data[f"use_{pred_name}"] = 1
            use_flags[pred_name] = 1
            print(f"  ✓ Using predictor: {pred_name}")
        else:
            data[pred_name] = np.zeros(data["N_coretop"])
            data[f"use_{pred_name}"] = 0
            use_flags[pred_name] = 0
            print(f"  ✗ Predictor missing for coretop: {pred_name}")

    return data, use_flags


def build_inverse_data(
    scaledRI: np.ndarray,
    prior_mu_thermoT: np.ndarray,
    prior_sigma_thermoT: float,
    posterior: xr.Dataset,
    predictors: Dict[str, np.ndarray],
    use_flags: Optional[Dict[str, bool]] = None,
    n_draws: int = 1000,
    seed: Optional[int] = 42
) -> Tuple[dict, dict]:
    """
    Build Stan-compatible data and use flags for inverse prediction model.

    Parameters:
    ----------
    scaledRI : np.ndarray
        Ring index values from coretops to invert.

    prior_mu_thermoT : np.ndarray
        Prior mean estimates of temperature (same length as scaledRI).

    prior_sigma_thermoT : float
        Prior standard deviation on thermoT.

    posterior : xr.Dataset
        Posterior output from calibration model containing parameters like
        t0_coretop, k_coretop, b_coretop, sigma, and optional beta0_* terms.

    predictors : dict
        Dictionary of optional predictor arrays, e.g., {
            "gdgt23ratio": <array>,
            "depthIntg_thermoT_no3": <array>
        }

    use_flags : dict (optional)
        Dict specifying whether to use each optional predictor. If None, use
        the presence of predictor arrays to decide.

    n_draws : int
        Number of posterior draws to sample.

    seed : int
        Random seed for reproducibility.

    Returns:
    -------
    data : dict
        Dictionary formatted for Stan sampling.

    use_flags : dict
        Explicit flags for each optional predictor (1 = used, 0 = unused).
    """
    OPTIONAL_PREDICTORS = ["gdgt23ratio", "depthIntg_thermoT_no3"]

    if seed is not None:
        np.random.seed(seed)

    sel = np.random.choice(posterior.dims["draw"], size=n_draws, replace=True)
    P = posterior.isel(draw=sel)

    N = len(scaledRI)
    M = n_draws

    data = {
        "N": N,
        "scaledRI": np.asarray(scaledRI),
        "prior_mu_thermoT": np.asarray(prior_mu_thermoT),
        "prior_sigma_thermoT": prior_sigma_thermoT,
        "M": M,
        "t0_coretop": P["t0_coretop"].values,
        "k_coretop": P["k_coretop"].values,
        "b_coretop": P["b_coretop"].values,
        "sigma_coretop_scaledRI": P["sigma"].values,
    }

    if use_flags is None:
        use_flags = {}

    print("[build_inverse_data] Processing optional predictors...")
    for name in OPTIONAL_PREDICTORS:
        beta_name = f"beta0_{name}"
        use = use_flags.get(name, name in predictors)
        use_flags[name] = bool(use)

        if use:
            data[name] = np.asarray(predictors[name])
            data[beta_name] = P[beta_name].values
            print(f"  ✓ Using predictor: {name}")
        else:
            data[name] = np.zeros(N)
            data[beta_name] = np.zeros(M)
            print(f"  ✗ Skipping predictor: {name} (use_{name} = 0)")

        data[f"use_{name}"] = int(use)

    return data, use_flags


# ─── FORWARD & INVERSE LOGISTIC (GENERALIZED) ─────────────────────────────────

def pred_logistic_general(
    x: np.ndarray,
    t0: np.ndarray,
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
    t0_arr, k_arr, b_arr, L_arr = map(_ensure_numpy, (t0, k, b, L))
    # base logistic term
    base = L_arr[:, None] / (1 + np.exp(-k_arr[:, None] * (x_arr[None, :] - t0_arr[:, None]))) + b_arr[:, None]
    # add linear factors
    lin = np.zeros_like(base)
    for name, beta in betas.items():
        fac = _ensure_numpy(factors[name])
        beta_arr = _ensure_numpy(beta)
        lin += beta_arr[:, None] * fac[None, :]
    return base + lin


def inv_logistic_general(
    y: np.ndarray,
    t0: np.ndarray,
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
    t0_arr, k_arr, b_arr, L_arr = map(_ensure_numpy, (t0, k, b, L))
    # compute linear combination per draw & obs
    lin = np.zeros((t0_arr.size, y_arr.size))
    for name, beta in betas.items():
        fac = _ensure_numpy(factors[name])
        beta_arr = _ensure_numpy(beta)
        lin += beta_arr[:, None] * fac[None, :]
    # subtract linear terms
    y_corr = y_arr[None, :] - lin
    # invert logistic
    arg = L_arr[:, None] / (y_corr - b_arr[:, None]) - 1
    return t0_arr[:, None] - (1.0 / k_arr[:, None]) * np.log(arg)

# ─── STAN INTERFACE & CACHE ─────────────────────────────────────────────────

_MODEL_CACHE: Dict[Path, CmdStanModel] = {}

def get_posterior(
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
    Draw samples from a posterior with parameters: t0,k,b,L and any beta0_* keys,
    then invert: x = inv_logistic_general(y, t0,k,b,L, betas, factors)
    *factors: pass arrays named by suffix after 'beta0_', e.g. z3, aa3
    """
    if seed is not None:
        np.random.seed(seed)
    # bootstrap draws
    sel = np.random.choice(posterior.dims["draw"], size=n_draws, replace=True)
    P = posterior.isel(draw=sel)
    # extract base params
    ### auto-detect t0 from all named params with "t0_" prefix
    ### and use one with _coretop suffix if available
    ### if not, use the last one found
    ### "L_" is optional, but if not found, use (1 - b)
    
    search_key_list = ["t0_", "k_", "b_"]
    for search_key in search_key_list:
        keys = [key for key in P.data_vars if key.startswith(search_key)]
        if not keys:
            raise ValueError(f"No {search_key} parameters found in posterior dataset.")
        if len(keys) > 1:
            print(f'''Multiple {search_key} parameters found: {keys}. Use {search_key}_coretop by default.''')
            ### check for _coretop suffix
            coretop_keys = [key for key in keys if key.endswith("_coretop")]
            if coretop_keys:
                keys = coretop_keys
            else:
                ### use the last one found
                keys = [keys[-1]]
                
        
        key = keys[0]
        if search_key == "t0_":
            t0 = P[key]
        elif search_key == "k_":
            k = P[key]
        elif search_key == "b_":
            b = P[key]
    

    # derive or extract L
    L = P["L"].values if "L" in P else (1 - b).values
    # collect beta arrays
    betas = {}
    for var in P.data_vars:
        if var.startswith("beta0_"):
            key = var.replace("beta0_", "")
            betas[key] = P[var].values
    # ensure factors provided for each beta
    for name in betas:
        if name not in factors:
            raise ValueError(f"Missing factor array for beta0_{name}")
    return inv_logistic_general(y=y, t0=t0, k=k, b=b, L=L,
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
    t0 = P["t0_coretop"].values
    k  = P["k_coretop"].values
    b  = P["b_coretop"].values
    L = P["L"].values if "L" in P else (1 - P["b_coretop"]).values
    betas = {}
    for var in P.data_vars:
        if var.startswith("beta0_"):
            key = var.replace("beta0_", "")
            betas[key] = P[var].values
    for name in betas:
        if name not in factors:
            raise ValueError(f"Missing factor array for beta0_{name}")
    return pred_logistic_general(x=x, t0=t0, k=k, b=b, L=L,
                                 betas=betas, factors=factors)

# ─── POSTERIOR LOADING ────────────────────────────────────────────────────
def save_posterior(posterior: xr.Dataset, model_name: str, cache_dir='posterior_cache'):
    base_dir = Path(__file__).parent.parent  # or adjust as needed to reach project root
    output_dir = base_dir / cache_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"{model_name}.nc"

    # Add metadata
    posterior.attrs['model_name'] = model_name
    posterior.attrs['generated_by'] = 'culRI-Bayesian'
    posterior.attrs['version'] = '1.0.0'

    encoding = {var: {"zlib": True} for var in posterior.data_vars}
    posterior.to_netcdf(filepath, encoding=encoding)

    print(f"Posterior saved to {filepath}")

def load_posterior(model_name, cache_dir='posterior_cache'):
    base_dir = Path(__file__).parent.parent  # or adjust as needed to reach project root
    output_dir = base_dir / cache_dir
    output_dir.mkdir(parents=True, exist_ok=True)    
    filepath = output_dir / f"{model_name}.nc"

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Posterior file not found: {filepath}")
    return xr.load_dataset(filepath)


