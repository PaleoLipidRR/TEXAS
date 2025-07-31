from pathlib import Path
from typing import Union, Optional, Dict, List, Tuple, Sequence
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
    mode: str = "meanprior_bayes",  # 'meanprior_bayes' or 'ensemble' 
    no3_cutoff: Optional[float] = None,
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
    
    # After parsing use_flags (or wherever you know use_no3):
    if use_flags.get("no3", False):
        if no3_cutoff is None or no3_cutoff <= 0:
            raise ValueError(
                "You set use_no3=True, so you must supply a positive "
                "no3_cutoff. If you really don’t want to filter, set "
                "use_no3=False."
            )
    else:
        # you won’t actually use the cutoff in Stan if use_no3 is 0,
        # but Stan still needs *some* number. 100 is fine:
        no3_cutoff = 0.0

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
        data["no3_cutoff"] = no3_cutoff
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
        data["no3_cutoff"] = no3_cutoff

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


# ─── ENSEMBLE GENERATION ─────────────────────────────────────────────────

def generate_ensemble(
    posterior_ds: xr.Dataset,
    model_function,
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
    
    Parameters
    ----------
    posterior_ds : xr.Dataset
        Posterior dataset containing parameter samples
    model_function : callable
        Function that takes (x_vals, **params) and returns model predictions
    x_vals : np.ndarray
        X values to evaluate the model at
    param_names : List[str]
        List of parameter names to extract from posterior (without suffix)
    suffix : str, optional
        Suffix to append to parameter names (e.g., 'culmesocore', 'crtp')
        If None, will try to auto-detect from available parameters
    n_draws : int, default 500
        Number of draws to sample from posterior
    seed : int, optional
        Random seed for reproducible sampling
    percentiles : List[float], default [5, 50, 95]
        Percentiles to compute from ensemble
    return_full_ensemble : bool, default False
        If True, returns the full ensemble array in addition to percentiles
    gdgt23ratio : np.ndarray, optional
        GDGT-2/3 ratio values for multivariate models (same length as x_vals)
    no3 : np.ndarray, optional
        Nitrate concentration values for multivariate models (same length as x_vals)
    no3_cutoff : float, default 50.0
        Upper cutoff for nitrate values (for multivariate models)
        
    Returns
    -------
    Dict[str, np.ndarray]
        Dictionary containing:
        - 'p{percentile}': Arrays for each requested percentile
        - 'ensemble': Full ensemble array (if return_full_ensemble=True)
        - 'x_vals': Input x values
        - 'metadata': Dictionary with generation metadata
        
    Examples
    --------
    # Basic usage with generalized logistic model
    results = generate_ensemble(
        posterior_ds=my_posterior,
        model_function=generalized_logistic_model_fixed_upper,
        x_vals=np.linspace(0, 100, 500),
        param_names=['t0', 'b', 'k', 'v', 'Q'],
        suffix='crtp',
        n_draws=500
    )
    
    # Multivariate model with gdgt23ratio and no3 corrections
    results = generate_ensemble(
        posterior_ds=my_posterior,
        model_function=generalized_logistic_model_fixed_upper_multivariate,
        x_vals=temp_vals,
        param_names=['t0', 'b', 'k', 'v', 'Q', 'beta0_gdgt23ratio', 'beta0_no3'],
        suffix='crtp',
        gdgt23ratio=gdgt23_values,
        no3=nitrate_values,
        n_draws=500
    )
    """
    if seed is not None:
        np.random.seed(seed)
    
    # Auto-detect suffix if not provided
    if suffix is None:
        # Look for the most common suffix among the parameters
        available_vars = list(posterior_ds.data_vars)
        suffixes = {}
        
        # For multivariate models, prioritize suffix that has beta0_ parameters
        multivariate_suffixes = set()
        for var in available_vars:
            if 'beta0_gdgt23ratio' in var or 'beta0_no3' in var:
                suffix_part = var.split('_')[-1]
                multivariate_suffixes.add(suffix_part)
        
        # Count suffix occurrences for base parameters
        for param in param_names:
            candidates = [var for var in available_vars if var.startswith(f"{param}_")]
            if candidates:
                # Extract suffix from first match
                suffix_part = candidates[0].replace(f"{param}_", "")
                suffixes[suffix_part] = suffixes.get(suffix_part, 0) + 1
        
        if suffixes:
            # If this is a multivariate model request, prioritize multivariate suffix
            if multivariate_suffixes and any('beta0_' in param for param in param_names):
                # Find suffix that has both base params and multivariate params
                for mv_suffix in multivariate_suffixes:
                    if mv_suffix in suffixes:
                        suffix = mv_suffix
                        print(f"Auto-detected suffix: '{suffix}' (prioritized for multivariate)")
                        break
                else:
                    # Fall back to most common suffix
                    suffix = max(suffixes, key=suffixes.get)
                    print(f"Auto-detected suffix: '{suffix}' (most common)")
            else:
                # Use the most common suffix
                suffix = max(suffixes, key=suffixes.get)
                print(f"Auto-detected suffix: '{suffix}'")
        else:
            raise ValueError(f"Could not auto-detect suffix for parameters {param_names}")
    
    # Build full parameter names
    full_param_names = [f"{param}_{suffix}" for param in param_names]
    
    # Validate that all parameters exist
    missing_params = [name for name in full_param_names if name not in posterior_ds.data_vars]
    if missing_params:
        available = [var for var in posterior_ds.data_vars if any(var.startswith(f"{p}_") for p in param_names)]
        raise ValueError(
            f"Missing parameters: {missing_params}\n"
            f"Available parameter variants: {available}"
        )
    
    # Check if this is a multivariate model by checking model function name
    model_func_name = model_function.__name__ if hasattr(model_function, '__name__') else str(model_function)
    is_multivariate = 'multivariate' in model_func_name
    
    # For backwards compatibility, also check dataset attributes
    use_gdgt23ratio = posterior_ds.attrs.get('use_gdgt23ratio', 0) == 1
    use_no3 = posterior_ds.attrs.get('use_no3', 0) == 1
    
    # Fallback: if no use_* attributes, check for parameter existence (old behavior)
    if 'use_gdgt23ratio' not in posterior_ds.attrs and 'use_no3' not in posterior_ds.attrs:
        use_gdgt23ratio = f"beta0_gdgt23ratio_{suffix}" in posterior_ds.data_vars
        use_no3 = f"beta0_no3_{suffix}" in posterior_ds.data_vars
    
    # Extract parameter data and sample draws
    posterior_df = posterior_ds[full_param_names].to_dataframe().reset_index()
    total_draws = len(posterior_df)
    
    if n_draws > total_draws:
        print(f"Warning: Requested {n_draws} draws but only {total_draws} available. Using all available draws.")
        n_draws = total_draws
    
    sampled_draws = posterior_df.sample(n=n_draws, replace=False, random_state=seed).reset_index(drop=True)
    
    # Initialize ensemble array
    ensemble = np.zeros((n_draws, len(x_vals)))
    
    # Generate ensemble
    for i in range(n_draws):
        row = sampled_draws.iloc[i]
        
        # Extract parameters and remove suffix
        params = {}
        for full_name in full_param_names:
            param_name = full_name.replace(f"_{suffix}", "")
            params[param_name] = row[full_name]
        
        # Add multivariate parameters if this is a multivariate model
        if is_multivariate:
            if use_gdgt23ratio and gdgt23ratio is not None:
                params['gdgt23ratio'] = gdgt23ratio
            if use_no3 and no3 is not None:
                params['no3'] = no3
                params['no3_cutoff'] = no3_cutoff
        
        try:
            # Call model function with parameters
            ensemble[i, :] = model_function(x_vals, **params)
        except Exception as e:
            raise RuntimeError(f"Error calling model function at draw {i} with params {params}: {e}")
    
    # Compute percentiles
    results = {
        'x_vals': x_vals,
        'metadata': {
            'n_draws': n_draws,
            'suffix': suffix,
            'param_names': param_names,
            'full_param_names': full_param_names,
            'model_function': model_function.__name__ if hasattr(model_function, '__name__') else str(model_function),
            'seed': seed,
            'percentiles': percentiles,
            'is_multivariate': is_multivariate,
            'use_gdgt23ratio': use_gdgt23ratio,
            'use_no3': use_no3,
            'gdgt23ratio_provided': gdgt23ratio is not None,
            'no3_provided': no3 is not None
        }
    }
    
    for percentile in percentiles:
        key = f'p{int(percentile)}'
        results[key] = np.percentile(ensemble, percentile, axis=0)
    
    if return_full_ensemble:
        results['ensemble'] = ensemble
    
    return results


def generalized_logistic_model_fixed_upper_multivariate(
    x, t0=None, x0=None, b=None, k=None, v=None, Q=None,
    beta0_gdgt23ratio=None, gdgt23ratio=None,
    beta0_no3=None, no3=None, no3_cutoff=50.0
):
    """
    Generalized logistic model with fixed upper asymptote at 1, including multivariate corrections.
    
    This function implements the same model as in the Stan code, including optional
    corrections for gdgt23ratio and no3 (nitrate) variables.
    
    Parameters
    ----------
    x : array-like
        Input values (e.g., temperature)
    t0 : float, optional
        Inflection point (alternative name for x0)
    x0 : float, optional
        Inflection point (alternative name for t0)
    b : float
        Lower asymptote (left asymptote)
    k : float
        Slope parameter
    v : float
        Shape parameter (nu)
    Q : float
        Exponent parameter
    beta0_gdgt23ratio : float, optional
        Coefficient for gdgt23ratio correction
    gdgt23ratio : array-like, optional
        GDGT-2/3 ratio values (same length as x)
    beta0_no3 : float, optional
        Coefficient for nitrate (log10) correction
    no3 : array-like, optional
        Nitrate concentration values (same length as x)
    no3_cutoff : float, default 50.0
        Upper cutoff for nitrate values (as in Stan model)
        
    Returns
    -------
    array-like
        Model predictions with multivariate corrections applied
        
    Notes
    -----
    This function replicates the Stan model logic:
    - Base scaled RI from generalized logistic function
    - Optional gdgt23ratio correction: + beta0_gdgt23ratio * gdgt23ratio
    - Optional no3 correction: + beta0_no3 * log10(no3) where 0 < no3 < no3_cutoff
    """
    # Handle both t0 and x0 parameter names for inflection point
    inflection_point = t0 if t0 is not None else x0
    if inflection_point is None:
        raise ValueError("Either 't0' or 'x0' must be provided for the inflection point")
    
    # Base generalized logistic model
    base_scaledRI = b + ((1 - b) / np.power(1 + Q * np.exp(-k * (x - inflection_point)), 1/v))
    
    # Start with base prediction
    mu_scaledRI = base_scaledRI.copy() if hasattr(base_scaledRI, 'copy') else np.array(base_scaledRI)
    
    # Apply gdgt23ratio correction if provided
    if beta0_gdgt23ratio is not None and gdgt23ratio is not None:
        gdgt23ratio = np.array(gdgt23ratio)
        if gdgt23ratio.shape != mu_scaledRI.shape:
            raise ValueError(f"gdgt23ratio shape {gdgt23ratio.shape} doesn't match x shape {mu_scaledRI.shape}")
        mu_scaledRI += beta0_gdgt23ratio * gdgt23ratio
    
    # Apply no3 correction if provided
    if beta0_no3 is not None and no3 is not None:
        no3 = np.array(no3)
        if no3.shape != mu_scaledRI.shape:
            raise ValueError(f"no3 shape {no3.shape} doesn't match x shape {mu_scaledRI.shape}")
        
        # Apply no3 correction where 0 < no3 < no3_cutoff (following Stan model logic)
        valid_no3_mask = (no3 > 0) & (no3 < no3_cutoff)
        mu_scaledRI[valid_no3_mask] += beta0_no3 * np.log10(no3[valid_no3_mask])
    
    return mu_scaledRI


def generalized_logistic_model_fixed_upper(x, t0=None, x0=None, b=None, k=None, v=None, Q=None):
    """
    Generalized logistic model with fixed upper asymptote at 1 (univariate version).
    
    Parameters
    ----------
    x : array-like
        Input values (e.g., temperature)
    t0 : float, optional
        Inflection point (alternative name for x0)
    x0 : float, optional
        Inflection point (alternative name for t0)
    b : float
        Lower asymptote (left asymptote)
    k : float
        Slope parameter
    v : float
        Shape parameter (nu)
    Q : float
        Exponent parameter
        
    Returns
    -------
    array-like
        Model predictions
    """
    # Handle both t0 and x0 parameter names for inflection point
    inflection_point = t0 if t0 is not None else x0
    if inflection_point is None:
        raise ValueError("Either 't0' or 'x0' must be provided for the inflection point")
    
    return b + ((1 - b) / np.power(1 + Q * np.exp(-k * (x - inflection_point)), 1/v))


def simple_logistic_model_fixed_upper(x, t0=None, x0=None, b=None, k=None):
    """
    Simple logistic model with fixed upper asymptote at 1 (univariate version).
    
    This is the 3-parameter logistic model used in jnt_ and hier_ Stan models.
    Formula: y = b + (1 - b) / (1 + exp(-k * (x - t0)))
    
    Parameters
    ----------
    x : array-like
        Input values (e.g., temperature)
    t0 : float, optional
        Inflection point (alternative name for x0)
    x0 : float, optional
        Inflection point (alternative name for t0)
    b : float
        Lower asymptote (left asymptote)
    k : float
        Slope parameter
        
    Returns
    -------
    array-like
        Model predictions
    """
    # Handle both t0 and x0 parameter names for inflection point
    inflection_point = t0 if t0 is not None else x0
    if inflection_point is None:
        raise ValueError("Either 't0' or 'x0' must be provided for the inflection point")
    
    return b + ((1 - b) / (1 + np.exp(-k * (x - inflection_point))))


def simple_logistic_model_fixed_upper_multivariate(
    x, t0=None, x0=None, b=None, k=None,
    beta0_gdgt23ratio=None, gdgt23ratio=None,
    beta0_no3=None, no3=None, no3_cutoff=50.0
):
    """
    Simple logistic model with fixed upper asymptote at 1, including multivariate corrections.
    
    This function implements the same model as in the jnt_/hier_ Stan code, including optional
    gdgt23ratio and no3 corrections applied to the base simple logistic curve.
    
    Parameters
    ----------
    x : array-like
        Input values (e.g., temperature)
    t0 : float, optional
        Inflection point (alternative name for x0)
    x0 : float, optional
        Inflection point (alternative name for t0)
    b : float
        Lower asymptote (left asymptote)
    k : float
        Slope parameter
    beta0_gdgt23ratio : float, optional
        Coefficient for gdgt23ratio correction
    gdgt23ratio : array-like, optional
        GDGT-2/3 ratio values (same length as x)
    beta0_no3 : float, optional
        Coefficient for nitrate (log10) correction
    no3 : array-like, optional
        Nitrate concentration values (same length as x)
    no3_cutoff : float, default 50.0
        Upper cutoff for nitrate values (as in Stan model)
        
    Returns
    -------
    array-like
        Model predictions with multivariate corrections applied
        
    Notes
    -----
    This function replicates the Stan model logic:
    - Base scaled RI from simple logistic function
    - Optional gdgt23ratio correction: + beta0_gdgt23ratio * gdgt23ratio
    - Optional no3 correction: + beta0_no3 * log10(no3) where 0 < no3 < no3_cutoff
    """
    # Handle both t0 and x0 parameter names for inflection point
    inflection_point = t0 if t0 is not None else x0
    if inflection_point is None:
        raise ValueError("Either 't0' or 'x0' must be provided for the inflection point")
    
    # Base simple logistic model
    base_scaledRI = b + ((1 - b) / (1 + np.exp(-k * (x - inflection_point))))
    
    # Start with base prediction
    mu_scaledRI = base_scaledRI.copy() if hasattr(base_scaledRI, 'copy') else np.array(base_scaledRI)
    
    # Apply gdgt23ratio correction if provided
    if beta0_gdgt23ratio is not None and gdgt23ratio is not None:
        gdgt23ratio = np.array(gdgt23ratio)
        if gdgt23ratio.shape != mu_scaledRI.shape:
            raise ValueError(f"gdgt23ratio shape {gdgt23ratio.shape} doesn't match x shape {mu_scaledRI.shape}")
        mu_scaledRI += beta0_gdgt23ratio * gdgt23ratio
    
    # Apply no3 correction if provided
    if beta0_no3 is not None and no3 is not None:
        no3 = np.array(no3)
        if no3.shape != mu_scaledRI.shape:
            raise ValueError(f"no3 shape {no3.shape} doesn't match x shape {mu_scaledRI.shape}")
        
        # Apply no3 correction where 0 < no3 < no3_cutoff (following Stan model logic)
        valid_no3_mask = (no3 > 0) & (no3 < no3_cutoff)
        mu_scaledRI[valid_no3_mask] += beta0_no3 * np.log10(no3[valid_no3_mask])
    
    return mu_scaledRI


def generate_ensemble_auto(
    posterior_ds: xr.Dataset,
    x_vals: np.ndarray,
    model_type: str = "auto",
    gdgt23ratio: Optional[np.ndarray] = None,
    no3: Optional[np.ndarray] = None,
    no3_cutoff: float = 50.0,
    **kwargs
) -> Dict[str, np.ndarray]:
    """
    Automatically generate ensemble with auto-detected model types.
    Now supports both forward and inverse models.
    
    Parameters
    ----------
    posterior_ds : xr.Dataset
        Posterior dataset from Stan model
    x_vals : np.ndarray
        For forward models: temperature values
        For inverse models: scaledRI values
    model_type : str, default "auto"
        Model type detection mode:
        - "auto": Auto-detect forward vs inverse
        - "forward": Force forward model detection
        - "inverse": Force inverse model detection
    gdgt23ratio : np.ndarray, optional
        GDGT-2/3 ratio values
    no3 : np.ndarray, optional  
        Nitrate concentration values
    no3_cutoff : float, default 50.0
        Nitrate cutoff value
    **kwargs
        Additional arguments
        
    Returns
    -------
    Dict[str, np.ndarray]
        Ensemble results
        
    Examples
    --------
    >>> # Forward model (temperature -> scaledRI)
    >>> temp_range = np.linspace(15, 45, 100)
    >>> results = generate_ensemble_auto(
    ...     posterior_ds=forward_posterior,
    ...     x_vals=temp_range
    ... )
    >>> scaledRI_predictions = results['p50']
    
    >>> # Inverse model (scaledRI -> temperature)  
    >>> scaledRI_obs = np.array([0.4, 0.5, 0.6])
    >>> results = generate_ensemble_auto(
    ...     posterior_ds=inverse_posterior,
    ...     x_vals=scaledRI_obs
    ... )
    >>> temp_estimates = results['p50']
    """
    
    # Check if this is an inverse T model
    model_name = posterior_ds.attrs.get('stan_model_name', '')
    is_inverse_model = 'invT_' in model_name or 't_est' in posterior_ds.data_vars
    
    if model_type == "auto":
        if is_inverse_model:
            print(f"🔬 Auto-detected inverse temperature model: {model_name}")
            return generate_invT_ensemble(posterior_ds, x_vals, **kwargs)
        else:
            print(f"📈 Auto-detected forward model: {model_name}")
            return _process_forward_model(posterior_ds, x_vals, gdgt23ratio, no3, no3_cutoff, **kwargs)
    
    elif model_type == "inverse":
        if is_inverse_model:
            return generate_invT_ensemble(posterior_ds, x_vals, **kwargs)
        else:
            raise ValueError(f"Model type forced to 'inverse' but dataset appears to be forward model: {model_name}")
    
    elif model_type == "forward":
        if is_inverse_model:
            raise ValueError(f"Model type forced to 'forward' but dataset appears to be inverse model: {model_name}")
        else:
            return _process_forward_model(posterior_ds, x_vals, gdgt23ratio, no3, no3_cutoff, **kwargs)
    
    else:
        raise ValueError(f"Unknown model_type: {model_type}. Use 'auto', 'forward', or 'inverse'")


def _process_forward_model(
    posterior_ds: xr.Dataset,
    x_vals: np.ndarray,
    gdgt23ratio: Optional[np.ndarray],
    no3: Optional[np.ndarray],
    no3_cutoff: float,
    **kwargs
) -> Dict[str, np.ndarray]:
    """
    Process forward models (existing functionality).
    """
    # Auto-detect suffix
    used_suffix, suffix_map = infer_posterior_suffixes(posterior_ds.data_vars)
    if used_suffix is None:
        raise ValueError("Could not determine consistent parameter suffix")
    
    # Auto-detect model type
    model_detection = _detect_model_and_params(posterior_ds, used_suffix)
    
    return generate_ensemble(
        posterior_ds=posterior_ds,
        model_function=model_detection['model_function'],
        x_vals=x_vals,
        param_names=model_detection['param_names'],
        suffix=used_suffix,
        gdgt23ratio=gdgt23ratio,
        no3=no3,
        no3_cutoff=no3_cutoff,
        **kwargs
    )


def _process_generalized_logistic_model(
    posterior_ds: xr.Dataset,
    x_vals: np.ndarray,
    gdgt23ratio: Optional[np.ndarray],
    no3: Optional[np.ndarray],
    no3_cutoff: float,
    **kwargs
) -> Dict[str, np.ndarray]:
    """Process generalized logistic models (with v and Q parameters)."""
    available_vars = list(posterior_ds.data_vars)
    
    # Check dataset attributes to see which corrections were actually used in Stan model
    use_gdgt23ratio = posterior_ds.attrs.get('use_gdgt23ratio', 0) == 1
    use_no3 = posterior_ds.attrs.get('use_no3', 0) == 1
    
    # Fallback: if no use_* attributes, check for parameter existence (old behavior)
    if 'use_gdgt23ratio' not in posterior_ds.attrs and 'use_no3' not in posterior_ds.attrs:
        print("   ⚠️  Warning: No use_* attributes found, falling back to parameter detection")
        use_gdgt23ratio = any('beta0_gdgt23ratio' in var for var in available_vars)
        use_no3 = any('beta0_no3' in var for var in available_vars)
    
    is_multivariate = use_gdgt23ratio or use_no3
    
    if is_multivariate:
        print(f"🔬 Detected multivariate generalized logistic model:")
        print(f"   • GDGT-2/3 ratio correction: {'✓' if use_gdgt23ratio else '✗'}")
        print(f"   • NO3 correction: {'✓' if use_no3 else '✗'}")
        
        # Use multivariate model function and include additional parameters
        param_names = ['t0', 'b', 'k', 'v', 'Q']
        if use_gdgt23ratio:
            param_names.append('beta0_gdgt23ratio')
        if use_no3:
            param_names.append('beta0_no3')
            
        # Validate multivariate data if corrections are available
        if use_gdgt23ratio and gdgt23ratio is None:
            print("   ⚠️  Warning: GDGT-2/3 ratio correction available but no gdgt23ratio data provided")
        if use_no3 and no3 is None:
            print("   ⚠️  Warning: NO3 correction available but no no3 data provided")
        
        return generate_ensemble(
            posterior_ds=posterior_ds,
            model_function=generalized_logistic_model_fixed_upper_multivariate,
            x_vals=x_vals,
            param_names=param_names,
            gdgt23ratio=gdgt23ratio,
            no3=no3,
            no3_cutoff=no3_cutoff,
            **kwargs
        )
    else:
        print("🔬 Detected univariate generalized logistic model")
        return generate_ensemble(
            posterior_ds=posterior_ds,
            model_function=generalized_logistic_model_fixed_upper,
            x_vals=x_vals,
            param_names=['t0', 'b', 'k', 'v', 'Q'],
            **kwargs
        )


def _process_simple_logistic_model(
    posterior_ds: xr.Dataset,
    x_vals: np.ndarray,
    gdgt23ratio: Optional[np.ndarray],
    no3: Optional[np.ndarray],
    no3_cutoff: float,
    **kwargs
) -> Dict[str, np.ndarray]:
    """Process simple logistic models (without v and Q parameters)."""
    available_vars = list(posterior_ds.data_vars)
    
    # Check dataset attributes to see which corrections were actually used in Stan model
    use_gdgt23ratio = posterior_ds.attrs.get('use_gdgt23ratio', 0) == 1
    use_no3 = posterior_ds.attrs.get('use_no3', 0) == 1
    
    # Fallback: if no use_* attributes, check for parameter existence (old behavior)
    if 'use_gdgt23ratio' not in posterior_ds.attrs and 'use_no3' not in posterior_ds.attrs:
        print("   ⚠️  Warning: No use_* attributes found, falling back to parameter detection")
        use_gdgt23ratio = any('beta0_gdgt23ratio' in var for var in available_vars)
        use_no3 = any('beta0_no3' in var for var in available_vars)
    
    is_multivariate = use_gdgt23ratio or use_no3
    
    if is_multivariate:
        print(f"🔬 Detected multivariate simple logistic model:")
        print(f"   • GDGT-2/3 ratio correction: {'✓' if use_gdgt23ratio else '✗'}")
        print(f"   • NO3 correction: {'✓' if use_no3 else '✗'}")
        
        # Use multivariate model function and include additional parameters
        param_names = ['t0', 'b', 'k']  # Simple logistic only has 3 base parameters
        if use_gdgt23ratio:
            param_names.append('beta0_gdgt23ratio')
        if use_no3:
            param_names.append('beta0_no3')
            
        # Validate multivariate data if corrections are available
        if use_gdgt23ratio and gdgt23ratio is None:
            print("   ⚠️  Warning: GDGT-2/3 ratio correction available but no gdgt23ratio data provided")
        if use_no3 and no3 is None:
            print("   ⚠️  Warning: NO3 correction available but no no3 data provided")
        
        return generate_ensemble(
            posterior_ds=posterior_ds,
            model_function=simple_logistic_model_fixed_upper_multivariate,
            x_vals=x_vals,
            param_names=param_names,
            gdgt23ratio=gdgt23ratio,
            no3=no3,
            no3_cutoff=no3_cutoff,
            **kwargs
        )
    else:
        print("🔬 Detected univariate simple logistic model")
        return generate_ensemble(
            posterior_ds=posterior_ds,
            model_function=simple_logistic_model_fixed_upper,
            x_vals=x_vals,
            param_names=['t0', 'b', 'k'],  # Simple logistic only has 3 parameters
            **kwargs
        )


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
    verbose: bool = True,
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
    ## add filename to posterior attributes
    ds.attrs['filename'] = str(f"{stan_filename}_{temptype}")

    prior_settings = extract_priors_from_stan(model_path, data)
    if prior_settings:
        ds.attrs["priors"] = [f"{k}: {v}" for k, v in prior_settings.items()]  # ← safe for NetCDF


    return ds, diagnostics

def get_invT_posterior(
    data: dict,
    stan_filename: str,
    stan_models_dir: Union[Path, str] = None,
    site_name: Optional[str] = None,
    temptype: str = None,
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
    
    if temptype is None:
        print("Please specify the temptype (e.g., 'thermoT', 'sst', 'cultureT') to store as an attribute.")
    
    ds.attrs["temptype"] = temptype    
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
    
    ### check dims
    if "draw" not in posterior.dims:
        raise ValueError("Posterior dataset must contain a 'draw' dimension.")
    if len(posterior.dims) > 2:
        dims = ["draw", "dim_2"]
    else:
        dims = ["draw"]
    
    return posterior.quantile(quantiles, dim=dims, keep_attrs=True)

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
    if use_gdgt23ratio:
        temptype += "_gdgt23ratio"
    else:
        # If gdgt23ratio is not used, drop beta0_gdgt23ratio from variables
        if "beta0_gdgt23ratio_crtp" in posterior:
            posterior = posterior.drop_vars("beta0_gdgt23ratio_crtp")
    
        
    if use_no3:
        if posterior.attrs.get("no3_cutoff", None) is None:
            # If no3 is used, ensure no3_cutoff is set
            raise ValueError("no3_cutoff must be a positive real number if no3 is used.")
        else:
            set_no3 = posterior.attrs.get("no3_cutoff")
            temptype += f"_no3_{set_no3}"
    else:
        # If no3 is not used, drop beta0_no3 from variables
        if "beta0_no3_crtp" in posterior:
            posterior = posterior.drop_vars("beta0_no3_crtp")
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
    site_name = posterior.attrs.get('SiteName', 'unknown_site')
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
    filepath = output_dir / f"{site_name}_{stan_model_name}_{temptype}.nc"

    if filepath.exists() and not overwrite:
        raise FileExistsError(f"{filepath} already exists and overwrite=False.")

    # Save with compression
    encoding = {var: {"zlib": True} for var in posterior.data_vars}
    posterior.to_netcdf(filepath, encoding=encoding)

    print(f"Posterior saved to {filepath}")
    return filepath


# ─── INVERSE TEMPERATURE ENSEMBLE FUNCTIONS ──────────────────────────────

def generate_invT_ensemble(
    posterior_ds: xr.Dataset,
    scaledRI_vals: np.ndarray,
    percentiles: List[float] = [5, 50, 95],
    return_full_ensemble: bool = False,
    **kwargs
) -> Dict[str, np.ndarray]:
    """
    Generate temperature ensemble from inverse T model posteriors.
    
    This function works with inverse temperature models (invT_logistic_*) that
    estimate temperature values (t_est) from given scaledRI observations.
    
    Parameters
    ----------
    posterior_ds : xr.Dataset
        Posterior dataset from invT_logistic_* model
    scaledRI_vals : np.ndarray
        Scaled RI values corresponding to the t_est parameters
    percentiles : List[float], default [5, 50, 95]
        Percentiles to compute from ensemble
    return_full_ensemble : bool, default False
        If True, returns full t_est ensemble
        
    Returns
    -------
    Dict[str, np.ndarray]
        Dictionary containing:
        - 'p{percentile}': Temperature arrays for each percentile
        - 'ensemble': Full t_est ensemble (if requested)
        - 'scaledRI_vals': Input scaledRI values
        - 'metadata': Generation metadata
        
    Examples
    --------
    >>> # Generate temperature estimates from inverse model
    >>> scaledRI_obs = np.array([0.4, 0.5, 0.6, 0.7])
    >>> results = generate_invT_ensemble(
    ...     posterior_ds=invT_posterior,
    ...     scaledRI_vals=scaledRI_obs
    ... )
    >>> temp_median = results['p50']
    >>> temp_lower = results['p5']
    >>> temp_upper = results['p95']
    """
    # Extract t_est from posterior
    if 't_est' not in posterior_ds.data_vars:
        raise ValueError("Posterior dataset must contain 't_est' variable")
    
    t_est_data = posterior_ds['t_est'].values  # Shape: (n_draws, n_observations)
    n_draws, n_obs = t_est_data.shape
    
    if len(scaledRI_vals) != n_obs:
        raise ValueError(f"Length mismatch: scaledRI_vals={len(scaledRI_vals)} vs t_est observations={n_obs}")
    
    # Compute percentiles
    results = {
        'scaledRI_vals': scaledRI_vals,
        'metadata': {
            'n_draws': n_draws,
            'n_observations': n_obs,
            'model_type': 'inverse_temperature',
            'stan_model_name': posterior_ds.attrs.get('stan_model_name', 'unknown'),
            'percentiles': percentiles,
            'return_full_ensemble': return_full_ensemble
        }
    }
    
    for percentile in percentiles:
        key = f'p{int(percentile)}'
        results[key] = np.percentile(t_est_data, percentile, axis=0)
    
    if return_full_ensemble:
        results['ensemble'] = t_est_data
    
    return results


def generate_invT_ensemble_auto(
    posterior_ds: xr.Dataset,
    scaledRI_vals: np.ndarray,
    **kwargs
) -> Dict[str, np.ndarray]:
    """
    Auto-detect and generate inverse temperature ensemble.
    
    This function automatically detects inverse temperature models and
    generates temperature estimates from scaledRI observations.
    
    Parameters
    ----------
    posterior_ds : xr.Dataset
        Posterior dataset
    scaledRI_vals : np.ndarray
        Scaled RI values
    **kwargs
        Additional arguments passed to generate_invT_ensemble
        
    Returns
    -------
    Dict[str, np.ndarray]
        Results from generate_invT_ensemble
        
    Examples
    --------
    >>> # Auto-detect inverse model and generate ensemble
    >>> scaledRI_obs = np.array([0.4, 0.5, 0.6])
    >>> results = generate_invT_ensemble_auto(
    ...     posterior_ds=my_posterior,
    ...     scaledRI_vals=scaledRI_obs
    ... )
    >>> estimated_temps = results['p50']
    """
    # Check if this is an inverse T model
    model_name = posterior_ds.attrs.get('stan_model_name', '')
    
    if 'invT_' in model_name or 't_est' in posterior_ds.data_vars:
        print(f"🔬 Detected inverse temperature model: {model_name}")
        return generate_invT_ensemble(posterior_ds, scaledRI_vals, **kwargs)
    else:
        raise ValueError(f"Dataset does not appear to be from an inverse T model. Model: {model_name}")


def generate_invT_from_forward_model(
    forward_posterior_ds: xr.Dataset,
    scaledRI_targets: np.ndarray,
    param_suffix: str = "crtp",
    n_draws: int = 500,
    percentiles: List[float] = [5, 50, 95],
    return_full_ensemble: bool = False,
    temp_range: tuple = (0, 50),
    **kwargs
) -> Dict[str, np.ndarray]:
    """
    Generate temperature estimates by numerically inverting forward model predictions.
    
    This function takes a forward model posterior and numerically inverts it
    to estimate temperatures that would produce the target scaledRI values.
    
    Parameters
    ----------
    forward_posterior_ds : xr.Dataset
        Posterior dataset from a forward model (e.g., gen_logi_*, hier_*, jnt_*)
    scaledRI_targets : np.ndarray
        Target scaledRI values to invert
    param_suffix : str, default "crtp"
        Parameter suffix to use from posterior
    n_draws : int, default 500
        Number of posterior draws to sample
    percentiles : List[float], default [5, 50, 95]
        Percentiles to compute
    return_full_ensemble : bool, default False
        If True, returns full ensemble
    temp_range : tuple, default (0, 50)
        Temperature search range for numerical inversion
    **kwargs
        Additional arguments (gdgt23ratio, no3, etc.) for multivariate models
        
    Returns
    -------
    Dict[str, np.ndarray]
        Dictionary containing:
        - 'p{percentile}': Temperature arrays for each percentile
        - 'ensemble': Full temperature ensemble (if requested)
        - 'scaledRI_targets': Input scaledRI values
        - 'metadata': Generation metadata
        
    Examples
    --------
    >>> # Invert forward model to estimate temperatures
    >>> target_scaledRI = np.array([0.4, 0.6, 0.8])
    >>> results = generate_invT_from_forward_model(
    ...     forward_posterior_ds=my_forward_posterior,
    ...     scaledRI_targets=target_scaledRI,
    ...     param_suffix="crtp"
    ... )
    >>> estimated_temps = results['p50']
    """
    from scipy.optimize import minimize_scalar
    
    # Auto-detect model function and parameters
    model_detection = _detect_model_and_params(forward_posterior_ds, param_suffix)
    model_function = model_detection['model_function']
    param_names = model_detection['param_names']
    
    # Detect multivariate usage
    use_gdgt23ratio = forward_posterior_ds.attrs.get('use_gdgt23ratio', 0) == 1
    use_no3 = forward_posterior_ds.attrs.get('use_no3', 0) == 1
    
    # Sample from posterior
    full_param_names = [f"{param}_{param_suffix}" for param in param_names]
    if use_gdgt23ratio:
        full_param_names.append(f"beta0_gdgt23ratio_{param_suffix}")
    if use_no3:
        full_param_names.append(f"beta0_no3_{param_suffix}")
    
    posterior_df = forward_posterior_ds[full_param_names].to_dataframe().reset_index()
    total_draws = len(posterior_df)
    
    if n_draws > total_draws:
        print(f"Warning: Requested {n_draws} draws but only {total_draws} available. Using all available draws.")
        n_draws = total_draws
    
    sampled_draws = posterior_df.sample(n=n_draws, replace=False, random_state=42).reset_index(drop=True)
    
    # Initialize ensemble array
    n_targets = len(scaledRI_targets)
    ensemble = np.zeros((n_draws, n_targets))
    
    # Define objective function for inversion
    def objective(temp, target_scaledRI, model_params):
        """Objective function: |predicted_scaledRI - target_scaledRI|"""
        try:
            predicted = model_function(np.array([temp]), **model_params)[0]
            return abs(predicted - target_scaledRI)
        except Exception:
            return float('inf')
    
    # Perform numerical inversion for each draw and target
    print(f"🔄 Inverting forward model for {n_draws} draws and {n_targets} targets...")
    
    for i in range(n_draws):
        row = sampled_draws.iloc[i]
        
        # Extract parameters
        model_params = {}
        for param in param_names:
            model_params[param] = row[f"{param}_{param_suffix}"]
        
        # Add multivariate parameters if present
        if use_gdgt23ratio and 'gdgt23ratio' in kwargs:
            model_params['beta0_gdgt23ratio'] = row[f"beta0_gdgt23ratio_{param_suffix}"]
        if use_no3 and 'no3' in kwargs:
            model_params['beta0_no3'] = row[f"beta0_no3_{param_suffix}"]
            
        # Add multivariate data
        for key in ['gdgt23ratio', 'no3', 'no3_cutoff']:
            if key in kwargs:
                model_params[key] = kwargs[key]
        
        for j, target_scaledRI in enumerate(scaledRI_targets):
            try:
                # Use scalar minimization to find temperature
                result = minimize_scalar(
                    objective,
                    args=(target_scaledRI, model_params),
                    bounds=temp_range,
                    method='bounded'
                )
                
                if result.success:
                    ensemble[i, j] = result.x
                else:
                    ensemble[i, j] = np.nan
            except Exception:
                ensemble[i, j] = np.nan
    
    # Check for failed inversions
    failed_fraction = np.isnan(ensemble).mean()
    if failed_fraction > 0.1:
        warnings.warn(f"Warning: {failed_fraction*100:.1f}% of inversions failed. Consider adjusting temp_range.")
    
    # Compute percentiles
    results = {
        'scaledRI_targets': scaledRI_targets,
        'metadata': {
            'n_draws': n_draws,
            'n_targets': n_targets,
            'model_type': 'forward_model_inversion',
            'forward_model_name': forward_posterior_ds.attrs.get('stan_model_name', 'unknown'),
            'param_suffix': param_suffix,
            'percentiles': percentiles,
            'temp_range': temp_range,
            'failed_fraction': failed_fraction,
            'model_function': model_function.__name__ if hasattr(model_function, '__name__') else str(model_function),
            'is_multivariate': use_gdgt23ratio or use_no3,
            'use_gdgt23ratio': use_gdgt23ratio,
            'use_no3': use_no3
        }
    }
    
    for percentile in percentiles:
        key = f'p{int(percentile)}'
        results[key] = np.nanpercentile(ensemble, percentile, axis=0)
    
    if return_full_ensemble:
        results['ensemble'] = ensemble
    
    return results


def _detect_model_and_params(posterior_ds: xr.Dataset, suffix: str):
    """Helper function to detect model type and parameters."""
    available_vars = list(posterior_ds.data_vars)
    
    # Check for v and Q parameters
    has_v = f'v_{suffix}' in available_vars
    has_Q = f'Q_{suffix}' in available_vars
    
    # Check for multivariate parameters - only include if they exist for this suffix
    use_gdgt23ratio = posterior_ds.attrs.get('use_gdgt23ratio', 0) == 1
    use_no3 = posterior_ds.attrs.get('use_no3', 0) == 1
    
    # Check if multivariate parameters actually exist for this suffix
    has_gdgt23ratio_param = f'beta0_gdgt23ratio_{suffix}' in available_vars
    has_no3_param = f'beta0_no3_{suffix}' in available_vars
    
    # Only use multivariate if both the global flag is set AND the parameter exists for this suffix
    use_gdgt23ratio_for_suffix = use_gdgt23ratio and has_gdgt23ratio_param
    use_no3_for_suffix = use_no3 and has_no3_param
    
    if has_v and has_Q:
        # Generalized logistic
        param_names = ['t0', 'k', 'b', 'v', 'Q']
        if use_gdgt23ratio_for_suffix or use_no3_for_suffix:
            model_function = generalized_logistic_model_fixed_upper_multivariate
            if use_gdgt23ratio_for_suffix:
                param_names.append('beta0_gdgt23ratio')
            if use_no3_for_suffix:
                param_names.append('beta0_no3')
        else:
            model_function = generalized_logistic_model_fixed_upper
    else:
        # Simple logistic
        param_names = ['t0', 'k', 'b']
        if use_gdgt23ratio_for_suffix or use_no3_for_suffix:
            model_function = simple_logistic_model_fixed_upper_multivariate
            if use_gdgt23ratio_for_suffix:
                param_names.append('beta0_gdgt23ratio')
            if use_no3_for_suffix:
                param_names.append('beta0_no3')
        else:
            model_function = simple_logistic_model_fixed_upper
    
    return {
        'model_function': model_function,
        'param_names': param_names,
        'has_v': has_v,
        'has_Q': has_Q,
        'use_gdgt23ratio': use_gdgt23ratio_for_suffix,
        'use_no3': use_no3_for_suffix
    }