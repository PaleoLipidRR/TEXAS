from pathlib import Path
from typing import Union, Optional, Dict, List, Tuple, Sequence
import subprocess
from datetime import datetime
import numpy as np
import xarray as xr
from cmdstanpy import CmdStanModel
import os
import time
import re
import warnings

def check_tbb_env():
    """
    Check if TBB_CXX_TYPE is set correctly. Warn user if missing.
    """
    if "TBB_CXX_TYPE" not in os.environ:
        warnings.warn(
            "Environment variable TBB_CXX_TYPE is not set. "
            "Stan model compilation may fail.\n"
            "Recommended fix: Run `export TBB_CXX_TYPE=gcc` before launching Jupyter.\n"
            "If you use clang++, set it to `clang` instead."
        )
        # Optional: Uncomment to raise an error instead
        # raise EnvironmentError("TBB_CXX_TYPE must be set for Stan model compilation.")


check_tbb_env()


# ─── TYPES & HELPERS ───────────────────────────────────────────────

# Module‐level cache of compiled models
_MODEL_CACHE: dict = {}

def refresh_stan_models(stan_models_dir: str = None, n_jobs: int = 4, clean: bool = True):
    """
    For every .stan file in stan_models_dir:
      1) Delete any existing .hpp, .o, and executable with the same base name.
      2) Clear the in‐memory CmdStanModel cache (_MODEL_CACHE).
      3) Call CmdStanModel.compile() (with make_options) so that each .stan is
         recompiled against the prebuilt CMDSTAN toolchain.

    This assumes you have already set:
      os.environ["CMDSTAN"] = "/home/.../.cmdstan/cmdstan-2.36.0"

    Arguments
    ---------
    stan_models_dir : str
        Path to the folder containing your .stan files. If None, defaults
        to a "stan_models" subfolder next to this script.
    n_jobs : int
        Number of parallel jobs to pass to `make` via make_options.
    clean : bool
        If True, remove any old .hpp/.o/executable files before recompiling.
    """
    # 1) Resolve stan_models_dir
    script_dir = Path(__file__).resolve().parent
    stan_dir = Path(stan_models_dir or (script_dir / "stan_models")).resolve()
    if not stan_dir.exists():
        raise FileNotFoundError(f"Stan models directory not found: {stan_dir}")

    stan_files = sorted(stan_dir.glob("*.stan"))
    if not stan_files:
        print("🔍 No .stan files found.")
        return

    # 2) Delete old artifacts (.hpp, .o, executable) if requested
    for stan_file in stan_files:
        stem = stan_file.stem  # e.g. "jnt_cul_meso"
        hpp_path = stan_dir / f"{stem}.hpp"
        o_path   = stan_dir / f"{stem}.o"
        exe_path = stan_dir / stem

        if clean:
            for p in (hpp_path, o_path, exe_path):
                try:
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass  # ignore if it’s already gone

    # 3) Clear the CmdStanModel cache so that compile() will rebuild each time
    _MODEL_CACHE.clear()

    print(f"🔧 (Re)compiling {len(stan_files)} Stan model(s) via CmdStanPy…")

    # 4) Recompile each .stan using CmdStanModel.compile(make_options=[...])
    for stan_file in stan_files:
        try:
            model = CmdStanModel(stan_file=str(stan_file))
            # Pass make_options to tell `make` how many jobs (-j<n_jobs>) to use
            model.compile(force=True)
            print(f"✅ Compiled: {stan_file.name}")
        except Exception as e:
            print(f"❌ Failed to compile: {stan_file.name}")
            print(str(e))

    print("🚀 Done compiling Stan models.")

def _ensure_numpy(x):
    return x.values if hasattr(x, "values") else np.asarray(x)

def filter_stan_compatible(data: dict) -> dict:
    """Return a shallow copy of `data` containing only Stan-compatible types."""
    allowed_types = (int, float, list, np.ndarray)
    return {k: v for k, v in data.items() if isinstance(v, allowed_types)}

# ─── METADATA EXTRACTION ────────────────────────────────────────────────────

def extract_and_update_metadata(
        ds: xr.Dataset, 
        data: dict, 
        stan_filename: str, 
        site_name: Optional[str] = None,
        posteriors_used: Optional[List[str]] = None,
        version: str = "1.0.0"
) -> xr.Dataset:
    from datetime import datetime

    direct_keys = [
        "calibration_model_name", "N_cul", "N_meso", "N_crtp", "N",
        "prior_mu_t", "prior_sigma_t", "M"
    ]
    optional_predictors = ["gdgt23ratio", "no3"]
    suffixes = ["cul", "meso", "crtp", "downcore"]

    metadata = {
        "stan_model_name": stan_filename,
        "generated_by": "culRI-Bayesian",
        "version": version,
        "run_time": datetime.now().isoformat(),
        "run_duration (sec)": None,
        "temptype": None,  # will be set later
    }

    # Handle direct values
    for key in direct_keys:
        if key in data:
            val = data[key]
            if isinstance(val, (np.integer, int)): metadata[key] = int(val)
            elif isinstance(val, (np.floating, float)): metadata[key] = float(val)
            elif isinstance(val, (list, np.ndarray)): metadata[key] = float(np.median(val))
            else: metadata[key] = val

    # Summarize all available scaledRI_* arrays
    for suf in suffixes:
        key = f"scaledRI_{suf}"
        if key in data:
            arr = np.asarray(data[key])
            metadata.update({
                f"{key}_mean": float(np.mean(arr)),
                f"{key}_std": float(np.std(arr)),
                f"{key}_min": float(np.min(arr)),
                f"{key}_max": float(np.max(arr)),
                f"{key}_len": int(len(arr)),
            })

    # Summarize all optional predictors per group, if used
    for suf in suffixes:
        for predictor in optional_predictors:
            use_flag = f"use_{predictor}"
            key = f"{predictor}_{suf}"
            if data.get(use_flag, 0) == 1 and key in data:
                arr = np.asarray(data[key])
                metadata.update({
                    f"{key}_mean": float(np.mean(arr)),
                    f"{key}_std": float(np.std(arr)),
                    f"{key}_min": float(np.min(arr)),
                    f"{key}_max": float(np.max(arr)),
                    f"{key}_len": int(len(arr)),
                    use_flag: 1,
                })
                
                if predictor == "no3":
                    no3_cutoff = data.get("no3_cutoff", 0.0)
                    if no3_cutoff < 0:
                        raise ValueError("no3_cutoff must be a positive real number if no3 is used.")
                    metadata["no3_cutoff"] = float(no3_cutoff)

    # Include custom metadata if available
    if "calibration_suffix_used" in data:
        metadata["calibration_suffix_used"] = data["calibration_suffix_used"]

    if posteriors_used is not None:
        metadata["posteriors_used"] = posteriors_used
    elif "posteriors_used" in data:
        metadata["posteriors_used"] = data["posteriors_used"]

    if site_name:
        metadata["SiteName"] = site_name

    ds.attrs.update(metadata)
    return ds

def extract_priors_from_stan(stan_path: Union[str, Path], data: Optional[Dict[str, float]] = None) -> Dict[str, str]:
    """
    Extracts priors from a Stan file's model block.
    If data is provided, replaces symbolic values (e.g., prior_mean_t0) with their numerical equivalents.
    """
    priors = {}
    in_model_block = False

    with open(stan_path, "r") as f:
        for line in f:
            stripped = line.strip()

            if stripped.startswith("model"):
                in_model_block = True
                continue

            if in_model_block:
                if stripped.startswith("}"):
                    break

                match = re.match(r"(\w+)\s*~\s*([a-zA-Z_]\w*)\s*\(([^)]*)\)(\s*T\[[^\]]+\])?", stripped)
                if match:
                    param, dist, args, trunc = match.groups()
                    args_parts = [a.strip() for a in args.split(",")]

                    # Resolve symbols from `data` if provided
                    if data is not None:
                        resolved_parts = []
                        for part in args_parts:
                            if part in data:
                                val = data[part]
                                if isinstance(val, (float, int)):
                                    resolved_parts.append(f"{val:.4g}")
                                else:
                                    resolved_parts.append(str(val))
                            else:
                                resolved_parts.append(part)
                        args_str = ", ".join(resolved_parts)
                    else:
                        args_str = ", ".join(args_parts)

                    prior_str = f"{dist}({args_str})"
                    if trunc:
                        prior_str += f" {trunc.strip()}"
                    priors[param] = prior_str

    return priors


# ─── BUILD DATA ────────────────────────────────────────────────────

def infer_posterior_suffixes(data_vars):
    """
    Infer the suffix used in t0/k/b parameters only (not enforcing sigma to match).
    Returns:
        used_suffix (str or None): If consistent suffix is found across all t0/k/b.
        suffix_map (dict): Mapping from param to detected suffix.
    """
    import re
    core_params = ["t0", "k", "b"]
    suffixes = {}
    for param in core_params:
        candidates = [v for v in data_vars if v.startswith(f"{param}_")]
        for var in candidates:
            match = re.match(f"{param}_(.+)", var)
            if match:
                suffix = match.group(1)
                suffixes[param] = suffix
                break  # Take the first valid one
    if len(suffixes) == len(core_params) and len(set(suffixes.values())) == 1:
        return list(suffixes.values())[0], suffixes
    return None, suffixes



def build_invT_inputData(
    scaledRI: np.ndarray,
    prior_mu_t: Union[np.ndarray, float],
    prior_sigma_t: float,
    fwd_posterior_name: str,
    predictors: Optional[Dict[str, np.ndarray]] = None,
    use_flags: Optional[Dict[str, bool]] = None,
    n_draws: int = 100,
    seed: Optional[int] = 42,
    reduction: str = "mean",     # 'mean', 'median', or None
    mode: str = "meanprior_bayes"  # 'meanprior_bayes' or 'ensemble' 
) -> Tuple[dict, dict]:
    """
    Build Stan input data for inverse T model. Supports Bayesian meanprior and ensemble modes.
    """
    OPTIONAL_PREDICTORS = ["gdgt23ratio", "no3"]
    PRIORITY_SUFFIXES = ["crtp", "culmesocore", "culmeso", "meso", "cul"]

    if mode not in {"meanprior_bayes", "ensemble"}:
        raise ValueError(f"Unsupported mode: {mode}")

    if seed is not None:
        np.random.seed(seed)

    predictors = predictors or {}
    use_flags = use_flags or {}

    posterior = load_posterior(model_name=fwd_posterior_name)
    N = len(scaledRI)

    if np.isscalar(prior_mu_t):
        prior_mu_t = np.full(N, prior_mu_t)
    if len(prior_mu_t) != N:
        raise ValueError(f"Length mismatch: prior_mu_t={len(prior_mu_t)} vs scaledRI={N}")

    def find_suffix_for_all_params(params, priority_suffixes):
        for suffix in priority_suffixes:
            if all(f"{p}_{suffix}" in posterior for p in params):
                return suffix
        return None

    used_suffix = find_suffix_for_all_params(["t0", "k", "b"], PRIORITY_SUFFIXES)
    if used_suffix is None:
        raise ValueError("Could not determine consistent posterior suffix for t0/k/b")

    def summarize(var, method="mean"):
        vals = posterior[var].values
        return np.median(vals) if method == "median" else np.mean(vals)

    def summarize_std(var):
        vals = posterior[var].values
        std_val = np.std(vals)
        if np.isnan(std_val) or std_val <= 0:
            raise ValueError(f"Invalid std for {var}: {std_val}")
        return std_val

    posteriors_used = []

    if mode == "meanprior_bayes":
        data = {
            "N": N,
            "scaledRI": np.asarray(scaledRI),
            "prior_mu_t": np.asarray(prior_mu_t),
            "prior_sigma_t": prior_sigma_t,  # could be a vector in the future
            "mu_t0": summarize(f"t0_{used_suffix}", reduction),
            "mu_k": summarize(f"k_{used_suffix}", reduction),
            "mu_b": summarize(f"b_{used_suffix}", reduction),
            "std_t0": summarize_std(f"t0_{used_suffix}"),
            "std_k": summarize_std(f"k_{used_suffix}"),
            "std_b": summarize_std(f"b_{used_suffix}"),
        }
        sigma_key = f"sigma_scaledRI_{used_suffix}"
        if sigma_key in posterior:
            mu_sigma_scaledRI = summarize(sigma_key, reduction)
            std_sigma_scaledRI = summarize_std(sigma_key)
        else:
            mu_sigma_scaledRI = 0.1
            std_sigma_scaledRI = 0.05

        data["mu_sigma_scaledRI"] = mu_sigma_scaledRI
        data["std_sigma_scaledRI"] = std_sigma_scaledRI


        posteriors_used.extend([
            f"t0_{used_suffix}", f"k_{used_suffix}", f"b_{used_suffix}", f"sigma_scaledRI_{used_suffix}"
        ])

        for name in OPTIONAL_PREDICTORS:
            for suffix in PRIORITY_SUFFIXES:
                beta_name = f"beta0_{name}_{suffix}"
                if name in predictors and beta_name in posterior:
                    values = np.asarray(predictors[name])
                    if not np.all(values == 0):
                        data[name] = values
                        data[f"mu_beta0_{name}"] = summarize(beta_name, reduction)
                        data[f"std_beta0_{name}"] = summarize_std(beta_name)
                        data[f"use_{name}"] = 1
                        posteriors_used.append(beta_name)
                        break
            else:
                data[name] = np.zeros(N)
                data[f"mu_beta0_{name}"] = 0.0
                data[f"std_beta0_{name}"] = 0.1  # fallback prior std
                data[f"use_{name}"] = 0

    elif mode == "ensemble":
        sel = np.random.choice(posterior.dims["draw"], size=n_draws, replace=True)
        P = posterior.isel(draw=sel)
        M = n_draws

        data = {
            "N": N,
            "scaledRI": np.asarray(scaledRI),
            "prior_mu_t": np.asarray(prior_mu_t),
            "prior_sigma_t": prior_sigma_t,
            "M": M,
            "t0": P[f"t0_{used_suffix}"].values,
            "k": P[f"k_{used_suffix}"].values,
            "b": P[f"b_{used_suffix}"].values,
        }

        sigma_key = None
        for suffix in PRIORITY_SUFFIXES:
            candidate = f"sigma_scaledRI_{suffix}"
            if candidate in P and len(P[candidate]) == M:
                sigma_key = candidate
                data["sigma_scaledRI"] = P[sigma_key].values
                break
        if sigma_key is None:
            data["sigma_scaledRI"] = np.ones(M) * 0.1

        posteriors_used.extend([f"t0_{used_suffix}", f"k_{used_suffix}", f"b_{used_suffix}"])
        if sigma_key:
            posteriors_used.append(sigma_key)

        for name in OPTIONAL_PREDICTORS:
            for suffix in PRIORITY_SUFFIXES:
                beta_name = f"beta0_{name}_{suffix}"
                if name in predictors and beta_name in P:
                    values = np.asarray(predictors[name])
                    if not np.all(values == 0):
                        data[name] = values
                        data[f"beta0_{name}"] = P[beta_name].values
                        data[f"use_{name}"] = 1
                        posteriors_used.append(beta_name)
                        break

    data["calibration_model_name"] = posterior.attrs.get("stan_model_name", "unknown_model")
    data["posteriors_used"] = posteriors_used
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
    temptype: str = None,
    stan_models_dir: Union[Path, str] = None,
    chains: int = 4,
    iter_warmup: int = 500,
    iter_sampling: int = 1000,
    set_adapt_delta: float = 0.99,
    seed: Optional[int] = 42,
    verbose: bool = True
) -> xr.Dataset:
    
    start_time = time.time()
    
    if temptype not in {"thermoT","sst","cultureT"}:
        raise ValueError(f"Unsupported temperature type: {temptype}. Expected 'thermoT' or 'sst' or 'cultureT.")
    
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
            if data["no3_cutoff"] < 0:
                raise ValueError("no3_crtp provided but no3_cutoff is not set (positive real number).")
                
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
            save_profile=True, 
            adapt_delta=set_adapt_delta
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
    
    ds = extract_and_update_metadata(ds, data, stan_filename)
    run_seconds = time.time() - start_time
    ds.attrs["run_duration (sec)"] = round(run_seconds, 2)
    ds.attrs["temptype"] = temptype
    

    prior_settings = extract_priors_from_stan(model_path, data)
    if prior_settings:
        ds.attrs["priors"] = [f"{k}: {v}" for k, v in prior_settings.items()]  # ← safe for NetCDF


    return ds, diagnostics

def get_invT_posterior(
    data: dict,
    stan_filename: str,
    stan_models_dir: Union[Path, str] = None,
    site_name: Optional[str] = None,
    chains: int = 4,
    iter_warmup: int = 500,
    iter_sampling: int = 1000,
    set_adapt_delta: float = 0.99,
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

    if seed is not None:
        np.random.seed(seed)

    # Detect mode
    is_ensemble_mode = "M" in data
    is_bayes_meanprior = "mu_t0" in data and "std_t0" in data

    if not is_ensemble_mode and not is_bayes_meanprior:
        raise ValueError("Could not infer mode: expected either 'M' for ensemble or 'mu_t0'/'std_t0' for meanprior_bayes")

    # Validate required keys
    required_keys = ["N", "scaledRI", "prior_mu_t", "prior_sigma_t"]
    if is_ensemble_mode:
        required_keys += ["M", "t0", "k", "b", "sigma_scaledRI"]
    elif is_bayes_meanprior:
        required_keys += ["mu_t0", "std_t0", "mu_k", "std_k", "mu_b", "std_b", "mu_sigma_scaledRI", "std_sigma_scaledRI"]

    missing = [k for k in required_keys if k not in data]
    if missing:
        raise ValueError(f"Missing required keys for invT model: {missing}")

    # Standardize keys in ensemble mode
    posterior_suffixes = []
    if is_ensemble_mode:
        param_prefixes = ["t0", "k", "b", "sigma_scaledRI", "beta0_gdgt23ratio", "beta0_no3"]
        dynamic_keys = {}
        for prefix in param_prefixes:
            candidates = [k for k in data if k.startswith(f"{prefix}_") and len(np.atleast_1d(data[k])) == data["M"]]
            if len(candidates) > 1:
                raise ValueError(f"Multiple keys found for {prefix}_*: {candidates}")
            elif len(candidates) == 1:
                dynamic_keys[prefix] = candidates[0]
                posterior_suffixes.append(candidates[0])
        for std_key, actual_key in dynamic_keys.items():
            data[std_key] = data[actual_key]

    # Handle optional predictors
    for opt in ["gdgt23ratio", "no3"]:
        has_opt = opt in data and np.any(data[opt])
        use_flag = f"use_{opt}"
        beta_std = f"beta0_{opt}"
        data[use_flag] = int(has_opt)
        

        if not has_opt:
            data[opt] = np.zeros(data["N"])
            if is_ensemble_mode:
                data[beta_std] = np.zeros(data["M"])
            elif is_bayes_meanprior:
                data[f"mu_{beta_std}"] = 0.0
                data[f"std_{beta_std}"] = 0.1
        else:
            if is_ensemble_mode and beta_std not in data:
                data[beta_std] = np.zeros(data["M"])
            elif is_bayes_meanprior:
                if f"mu_{beta_std}" not in data:
                    data[f"mu_{beta_std}"] = 0.0
                    data[f"std_{beta_std}"] = 0.1

    # Run Stan
    try:
        stan_data = filter_stan_compatible(data)
        stan_data.pop("posteriors_used", None)
        stan_data.pop("calibration_model_name", None)

        fit = model.sample(
            data=stan_data,
            chains=chains,
            iter_warmup=iter_warmup,
            iter_sampling=iter_sampling,
            seed=seed,
            parallel_chains=chains,
            show_console=False,
            show_progress=True,
            save_profile=True,
            adapt_delta=set_adapt_delta
        )
    except RuntimeError as e:
        raise RuntimeError(f"Stan sampling failed: {e}")

    diagnostics = fit.diagnose()
    if verbose:
        print(f"Sampling completed in {time.time() - start_time:.1f} seconds")
        if "divergent" in diagnostics:
            print("⚠️ Sampling diagnostics warning:\n", diagnostics)

    # Convert to xarray.Dataset
    ds = xr.Dataset()
    for var in fit.stan_variables():
        arr = fit.stan_variable(var)
        dim_names = ["draw"] + [f"dim_{i}" for i in range(1, arr.ndim)]
        coords = {name: np.arange(sz) for name, sz in zip(dim_names, arr.shape)}
        ds[var] = xr.DataArray(data=arr, dims=dim_names, coords=coords, name=var)

    ds = extract_and_update_metadata(
        ds,
        data,
        stan_filename,
        site_name=site_name,
        posteriors_used=posterior_suffixes
    )
    ds.attrs["run_duration (sec)"] = round(time.time() - start_time, 2)

    if "prior_mu_t" in data and "prior_sigma_t" in data:
        mu_t_arr = np.asarray(data["prior_mu_t"])
        mu_t_val = float(np.median(mu_t_arr)) if mu_t_arr.ndim > 0 else float(mu_t_arr)
        ds.attrs["t_est_prior"] = f"normal({mu_t_val}, {data['prior_sigma_t']})"

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

    return posterior.quantile(quantiles, dim="draw", keep_attrs=True)

# ─── POSTERIOR LOADING ────────────────────────────────────────────────────
def save_posterior(
    posterior: xr.Dataset, 
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
    stan_model_name = posterior.attrs.get('stan_model_name', 'unknown_model')
    temptype = posterior.attrs.get('temptype', 'unknown')
    use_gdgt23ratio = posterior.attrs.get('use_gdgt23ratio', 0)
    use_no3 = posterior.attrs.get('use_no3', 0)
    if use_gdgt23ratio or use_no3:
        if use_gdgt23ratio:
            temptype += "_gdgt23ratio"
        if use_no3:
            if posterior.attrs.get("no3_cutoff", None) is None:
                # If no3 is used, ensure no3_cutoff is set
                raise ValueError("no3_cutoff must be a positive real number if no3 is used.")
            else:
                set_no3 = posterior.attrs.get("no3_cutoff")
                temptype += f"_no3_{set_no3}"
    filepath = output_dir / f"{stan_model_name}_{temptype}.nc"

    if filepath.exists() and not overwrite:
        raise FileExistsError(f"{filepath} already exists and overwrite=False.")

    ## add filename to posterior attributes
    posterior.attrs['filename'] = str(f"{stan_model_name}_{temptype}")
    
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

def save_invT_posterior(
    posterior: xr.Dataset, 
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
        output_dir = base_dir / 'invT_posterior_cache'
    else:
        output_dir = Path(cache_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    stan_model_name = posterior.attrs.get('stan_model_name', 'unknown_model')
    temptype = posterior.attrs.get('temptype', 'unknown')
    use_gdgt23ratio = posterior.attrs.get('use_gdgt23ratio', 0)
    use_no3 = posterior.attrs.get('use_no3', 0)
    if use_gdgt23ratio or use_no3:
        if use_gdgt23ratio:
            temptype += "_gdgt23ratio"
        if use_no3:
            if posterior.attrs.get("no3_cutoff", None) is None:
                # If no3 is used, ensure no3_cutoff is set
                raise ValueError("no3_cutoff must be a positive real number if no3 is used.")
            else:
                set_no3 = posterior.attrs.get("no3_cutoff")
                temptype += f"_no3_{set_no3}"
    filepath = output_dir / f"{stan_model_name}_{temptype}.nc"

    if filepath.exists() and not overwrite:
        raise FileExistsError(f"{filepath} already exists and overwrite=False.")

    ## add filename to posterior attributes
    posterior.attrs['filename'] = str(f"{stan_model_name}_{temptype}")

    # Save with compression
    encoding = {var: {"zlib": True} for var in posterior.data_vars}
    posterior.to_netcdf(filepath, encoding=encoding)

    print(f"Posterior saved to {filepath}")
    return filepath