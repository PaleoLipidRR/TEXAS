from pathlib import Path
from typing import Union, Optional, Dict, List, Tuple, Sequence
import numpy as np
import xarray as xr
from cmdstanpy import CmdStanModel
import os
import time
import re


# ─── TYPES & HELPERS ───────────────────────────────────────────────────────────

def _ensure_numpy(x):
    return x.values if hasattr(x, "values") else np.asarray(x)

def extract_metadata(data: dict, exclude_keys: List[str] = None) -> dict:
    exclude_keys = exclude_keys or []
    metadata = {}
    for key, value in data.items():
        if key in exclude_keys:
            continue
        if np.isscalar(value) or (isinstance(value, (np.ndarray, list)) and len(value) <= 10):
            metadata[key] = value if np.isscalar(value) else list(np.array(value).flatten())
        elif isinstance(value, (np.ndarray, list)):
            metadata[key] = f"<array len={len(value)}>"
        else:
            metadata[key] = str(value)
    return metadata


# ─── BUILD CALIBRATION DATASET ──────────────────────────────────────────────
def build_joint_calibration_data(
    cul: dict,
    meso: dict,
    crtp: dict,
    predictors: Dict[str, Dict[str, np.ndarray]]
) -> Tuple[dict, dict]:
    """
    Build Stan-compatible data and predictor usage flags for joint GDGT calibration.

    Parameters:
    ----------
    cul, meso, coretop : dict
        Each must contain a key "scaledRI" corresponding to ring index observations.

    predictors : dict of dict
        Must contain:
            "thermoT": {
                "cul": array-like,
                "meso": array-like,
                "crtp": array-like
            }
        Optional:
            Any additional predictors (e.g., "gdgt23ratio") with only "crtp" values.

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

    data["N_cul"] = len(cul["scaledRI"])
    data["scaledRI_cul"] = _ensure_numpy(cul["scaledRI"])
    data["thermoT_cul"] = _ensure_numpy(thermoT["cul"])

    data["N_meso"] = len(meso["scaledRI"])
    data["scaledRI_meso"] = _ensure_numpy(meso["scaledRI"])
    data["thermoT_meso"] = _ensure_numpy(thermoT["meso"])

    data["N_crtp"] = len(crtp["scaledRI"])
    data["scaledRI_crtp"] = _ensure_numpy(crtp["scaledRI"])
    data["thermoT_crtp"] = _ensure_numpy(thermoT["crtp"])

    # ─── Optional predictors ──────────────────────────────
    print("[build_joint_calibration_data] Building Stan data block...")
    print("  ✓ Using required predictor: thermoT")

    for pred_name in OPTIONAL_PREDICTORS:
        if pred_name in predictors and "crtp" in predictors[pred_name]:
            data[pred_name] = _ensure_numpy(predictors[pred_name]["crtp"])
            data[f"use_{pred_name}"] = 1
            use_flags[pred_name] = 1
            print(f"  ✓ Using predictor: {pred_name}")
        else:
            data[pred_name] = np.zeros(data["N_crtp"])
            data[f"use_{pred_name}"] = 0
            use_flags[pred_name] = 0
            print(f"  ✗ Predictor missing for crtp: {pred_name}")

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
        Ring index values from crtps to invert.

    prior_mu_thermoT : np.ndarray
        Prior mean estimates of temperature (same length as scaledRI).

    prior_sigma_thermoT : float
        Prior standard deviation on thermoT.

    posterior : xr.Dataset
        Posterior output from calibration model containing parameters like
        t0_crtp, k_crtp, b_crtp, sigma, and optional beta0_* terms.

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
        "t0_crtp": P["t0_crtp"].values,
        "k_crtp": P["k_crtp"].values,
        "b_crtp": P["b_crtp"].values,
        "sigma_crtp_scaledRI": P["sigma"].values,
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
    seed: Optional[int] = 42,
    verbose: bool = True
) -> xr.Dataset:
    
    start_time = time.time()
    if stan_models_dir is None:
        stan_models_dir = Path(__file__).parent / "stan_models"
    model_path = Path(stan_models_dir) / f"{stan_filename}.stan"

    if model_path not in _MODEL_CACHE:
        _MODEL_CACHE[model_path] = CmdStanModel(stan_file=str(model_path))
    model = _MODEL_CACHE[model_path]

    # Optional predictors: only set if coretop data is present
    if "N_crtp" in data:
        # gdgt23ratio_crtp
        if "gdgt23ratio_crtp" in data:
            data["use_gdgt23ratio"] = 1
        else:
            data["gdgt23ratio_crtp"] = np.zeros(data["N_crtp"])
            data["use_gdgt23ratio"] = 0

        # no3_crtp
        if "no3_crtp" in data:
            data["use_no3"] = 1
        else:
            data["no3_crtp"] = np.zeros(data["N_crtp"])
            data["use_no3"] = 0
    else:
        # If no coretop data, turn off optional predictors
        data["use_gdgt23ratio"] = 0
        data["use_no3"] = 0

    if seed is not None:
        np.random.seed(seed)

    try:
        fit = model.sample(
            data=data,
            chains=chains,
            iter_warmup=iter_warmup,
            iter_sampling=iter_sampling,
            seed=seed,
            parallel_chains=chains,
            show_console=False,
            show_progress=True,
            save_profile=True
        )
    except RuntimeError as e:
        raise RuntimeError(f"Stan sampling failed: {e}")

    # Optional: warn about divergent transitions
    diagnostics = fit.diagnose()
    if verbose:
        print(f"Sampling completed in {time.time() - start_time:.1f} seconds")
        if "divergent" in diagnostics:
            print("⚠️ Sampling diagnostics warning:\n", diagnostics)

    # Convert to xarray
    ds = xr.Dataset()
    for var in fit.stan_variables():
        arr = fit.stan_variable(var)
        dim_names = ["draw"] + [f"dim_{i}" for i in range(1, arr.ndim)]
        coords = {name: np.arange(sz) for name, sz in zip(dim_names, arr.shape)}
        ds[var] = xr.DataArray(data=arr, dims=dim_names, coords=coords, name=var)
    
    ds.attrs.update({
        'model_name': stan_filename,
        'generated_by': 'culRI-Bayesian',
        'version': '1.0.0'
    })

    ds.attrs.update(extract_metadata(data, exclude_keys=["scaledRI_*", "gdgt23ratio_*", "no3_*"]))

    
    return ds, diagnostics

def get_invT_posterior(
    data: dict,
    stan_filename: str,
    stan_models_dir: Union[Path, str] = None,
    chains: int = 4,
    iter_warmup: int = 500,
    iter_sampling: int = 1000,
    seed: Optional[int] = 42,
    verbose: bool = True
) -> xr.Dataset:
    
    import time
    start_time = time.time()
    if stan_models_dir is None:
        stan_models_dir = Path(__file__).parent / "stan_models"
    model_path = Path(stan_models_dir) / f"{stan_filename}.stan"

    if model_path not in _MODEL_CACHE:
        _MODEL_CACHE[model_path] = CmdStanModel(stan_file=str(model_path))
    model = _MODEL_CACHE[model_path]

    # Validate required core inputs
    base_keys = ["N_downcore", "scaledRI_downcore", "prior_mu_t", "prior_sigma_t", "M"]
    missing = [k for k in base_keys if k not in data]
    if missing:
        raise ValueError(f"Missing required keys for invT model: {missing}")

    # Automatically find t0_*, k_*, b_*, sigma_*, beta0_gdgt23ratio_*, beta0_no3_* matching M
    param_prefixes = ["t0", "k", "b", "sigma_scaledRI", "beta0_gdgt23ratio", "beta0_no3"]
    dynamic_keys = {}

    for prefix in param_prefixes:
        matched_keys = [key for key in data if key.startswith(f"{prefix}_") and len(np.atleast_1d(data[key])) == data["M"]]
        if len(matched_keys) > 1:
            raise ValueError(f"Multiple keys found for {prefix}_*: {matched_keys}")
        elif len(matched_keys) == 1:
            dynamic_keys[prefix] = matched_keys[0]

    # Inject standardized keys into data
    for std_name, actual_name in dynamic_keys.items():
        data[std_name] = data[actual_name]

    # Optional predictor: gdgt23ratio
    if "gdgt23ratio_downcore" in data:
        data["use_gdgt23ratio"] = 1
        if len(data["gdgt23ratio_downcore"]) != data["N_downcore"]:
            raise ValueError("Length of gdgt23ratio_downcore must equal N_downcore")
        if "beta0_gdgt23ratio" not in data:
            data["beta0_gdgt23ratio"] = np.zeros(data["M"])
    else:
        data["gdgt23ratio_downcore"] = np.zeros(data["N_downcore"])
        data["beta0_gdgt23ratio"] = np.zeros(data["M"])
        data["use_gdgt23ratio"] = 0

    # Optional predictor: no3
    if "no3_downcore" in data:
        data["use_no3"] = 1
        if len(data["no3_downcore"]) != data["N_downcore"]:
            raise ValueError("Length of no3_downcore must equal N_downcore")
        if "beta0_no3" not in data:
            data["beta0_no3"] = np.zeros(data["M"])
    else:
        data["no3_downcore"] = np.zeros(data["N_downcore"])
        data["beta0_no3"] = np.zeros(data["M"])
        data["use_no3"] = 0

    if seed is not None:
        np.random.seed(seed)

    try:
        fit = model.sample(
            data=data,
            chains=chains,
            iter_warmup=iter_warmup,
            iter_sampling=iter_sampling,
            seed=seed,
            parallel_chains=chains,
            show_console=False,
            show_progress=True,
            save_profile=True
        )
    except RuntimeError as e:
        raise RuntimeError(f"Stan sampling failed: {e}")

    # Optional: check diagnostics
    diagnostics = fit.diagnose()
    if verbose:
        print(f"Sampling completed in {time.time() - start_time:.1f} seconds")
        if "divergent" in diagnostics:
            print("⚠️ Sampling diagnostics warning:\n", diagnostics)

    # Convert to xarray dataset
    ds = xr.Dataset()
    for var in fit.stan_variables():
        arr = fit.stan_variable(var)
        dim_names = ["draw"] + [f"dim_{i}" for i in range(1, arr.ndim)]
        coords = {name: np.arange(sz) for name, sz in zip(dim_names, arr.shape)}
        ds[var] = xr.DataArray(data=arr, dims=dim_names, coords=coords, name=var)

    ds.attrs.update({
        'model_name': stan_filename,
        'generated_by': 'culRI-Bayesian',
        'version': '1.0.0'
    })

    ds.attrs.update(extract_metadata(data, exclude_keys=["scaledRI_*", "gdgt23ratio_*", "no3_*"]))

    
    return ds, diagnostics

def get_invT_post_quantiles(
    posterior: xr.Dataset,
    quantiles: Sequence[float] = (0.01, 0.05, 0.1, 0.16, 0.25, 0.4, 0.5, 
                                  0.6, 0.75, 0.84, 0.9, 0.95, 0.99),
) -> xr.Dataset:
    """
    Extract specified quantiles from inverse temperature posterior samples.

    Parameters
    ----------
    posterior : xr.Dataset
        Posterior dataset returned from `get_invT_posterior`.

    quantiles : Sequence[float], optional
        Quantiles to compute (default: [0.025, 0.5, 0.975]).

    Returns
    -------
    xr.Dataset
        Dataset containing the selected quantiles for each parameter.
    """
    if not isinstance(posterior, xr.Dataset):
        raise TypeError("posterior must be an xarray.Dataset")

    if not all(0.0 <= q <= 1.0 for q in quantiles):
        raise ValueError("All quantiles must be between 0 and 1.")

    return posterior.quantile(quantiles, dim=["draw", "dim_2"], keep_attrs=True)

# ─── POSTERIOR LOADING ────────────────────────────────────────────────────
def save_posterior(
    posterior: xr.Dataset, 
    filename: str, 
    cache_dir: Union[str, Path] = None,
    overwrite: bool = True
) -> Path:
    if not isinstance(posterior, xr.Dataset):
        raise TypeError("posterior must be an xarray.Dataset")

    # Determine base directory (repo or notebook)
    try:
        base_dir = Path(__file__).parent.parent
    except NameError:
        base_dir = Path.cwd()  # e.g., notebook or REPL

    # Set default if not provided
    if cache_dir is None:
        output_dir = base_dir / 'posterior_cache'
    else:
        output_dir = Path(cache_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"{filename}.nc"

    if filepath.exists() and not overwrite:
        raise FileExistsError(f"{filepath} already exists and overwrite=False.")

    ## add filename to posterior attributes
    posterior.attrs['filename'] = str(filename)
    
    # Save with compression
    encoding = {var: {"zlib": True} for var in posterior.data_vars}
    posterior.to_netcdf(filepath, encoding=encoding)

    print(f"Posterior saved to {filepath}")
    return filepath


def load_posterior(
    model_name: str, 
    cache_dir: str = 'posterior_cache'
) -> xr.Dataset:
    try:
        base_dir = Path(__file__).parent.parent
    except NameError:
        base_dir = Path.cwd()  # fallback for Jupyter or REPL

    output_dir = base_dir / cache_dir
    output_dir.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists

    filepath = output_dir / f"{model_name}.nc"

    if not filepath.exists():
        raise FileNotFoundError(f"Posterior file not found: {filepath}")

    ds = xr.load_dataset(filepath)
    return ds
