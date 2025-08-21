# TEXAS/stan/invT.py (Revised 08/18/2025)

from typing import Union, Optional, Dict, Sequence, List, Any, Literal
import numpy as np
import xarray as xr
from pathlib import Path
import json
import re
import os
import time
import tracemalloc
import gc
import platform
import multiprocessing
import psutil
import sys
from datetime import datetime

from .compiler import StanCompiler
from .sampler import StanSampler
from .metadata import extract_priors_from_stan
from .utils import patch_optional_predictors
from ..data.builder import build_invT_inputData, InvTConfig
from TEXAS.utils import get_repo_root
from TEXAS.stan.io import load_posterior


# Instantiate once
_default_compiler = StanCompiler()
_default_sampler = StanSampler(_default_compiler)

def _attach_invT_metadata(
    ds: xr.Dataset,
    data: dict,
    stan_file: str,
    site_name: Optional[str] = None,
    model_type: Optional[str] = None
) -> xr.Dataset:
    """Attaches essential metadata to the posterior dataset."""
    stan_model_name = stan_file.replace('.stan', '') if stan_file.endswith('.stan') else stan_file
    ds.attrs["stan_model_name"] = stan_model_name
    ds.attrs.setdefault("temptype", "unknown")
    ds.attrs["use_gdgt23ratio"] = int(bool(data.get("use_gdgt23ratio", 0)))
    ds.attrs["use_no3"] = int(bool(data.get("use_no3", 0)))
    if ds.attrs["use_no3"] == 1:
        ds.attrs["no3_cutoff"] = float(data.get("no3_cutoff", 0.0))
    else:
        ds.attrs["no3_cutoff"] = 0.0
    ds.attrs["SiteName"] = site_name or "unknown_site"
    
    # Use passed model_type if available, otherwise infer from filename
    if model_type:
        ds.attrs["model_type"] = model_type
    else:
        # Fallback: infer from filename
        ds.attrs["model_type"] = "direct" if "marginal" in stan_file else "ensemble"
    
    # OPTIONAL: Keep the old attribute for backwards compatibility
    ds.attrs["use_marginal"] = 1 if ds.attrs["model_type"] == "direct" else 0
    
    return ds

# -------------------------------------------------------------------------
def get_invT_posterior(
    scaledRI: Union[np.ndarray, List[float]],
    prior_mu_t: Union[np.ndarray, float],
    prior_sigma_t: float,
    fwd_posterior_name: str,
    site_name: Optional[str] = None,
    temptype: Optional[str] = None,
    predictors: Optional[Dict[str, np.ndarray]] = None,
    config: Optional[InvTConfig] = None,
    save: bool = True,
    filename_tag: Optional[Union[str, Sequence[str]]] = None,
    cache_dir: Optional[Union[str, Path]] = None,
    chains: Optional[int] = None,
    iter_warmup: Optional[int] = None,
    iter_sampling: Optional[int] = None,
    seed: Optional[int] = None,
    use_opencl: bool = False,
    threads_per_chain: Optional[int] = None,
    stan_model_path: Optional[Union[str, Path]] = None, 
    model_type: Literal["direct", "ensemble"] = "direct",
    constraint_type: Literal["unconstrained", "hard_constraint", "reparameterized", "soft"] = "unconstrained",
) -> xr.Dataset:
    """
    Run the inverse-T model and return the posterior Dataset with metadata.
    
    Args:
        model_type: 
            - "direct": Use direct sampling models (more efficient, supports threading)
            - "ensemble": Use traditional ensemble models
    """
    tracemalloc.start()
    start_time = time.perf_counter()
    system_info = get_system_info()
    
    cfg = config or InvTConfig()
    predictors = predictors or {}

    data, sampler_kwargs = build_invT_inputData(
        scaledRI=scaledRI, prior_mu_t=prior_mu_t, prior_sigma_t=prior_sigma_t,
        fwd_posterior_name=fwd_posterior_name, predictors=predictors, config=cfg,
    )

    if chains is not None: sampler_kwargs["chains"] = chains
    if iter_warmup is not None: sampler_kwargs["iter_warmup"] = iter_warmup
    if iter_sampling is not None: sampler_kwargs["iter_sampling"] = iter_sampling
    if seed is not None: sampler_kwargs["seed"] = seed
    sampler_kwargs.setdefault("chains", 4)
    sampler_kwargs.setdefault("iter_warmup", 500)
    sampler_kwargs.setdefault("iter_sampling", 1000)

    cpp_options = {}
    if use_opencl and threads_per_chain:
        raise ValueError("Cannot use both OpenCL and threading simultaneously.")
    if use_opencl:
        cpp_options["STAN_OPENCL"] = True
        sampler_kwargs["opencl_ids"] = [0, 0]
    if threads_per_chain:
        cpp_options["STAN_THREADS"] = True
        sampler_kwargs["threads_per_chain"] = threads_per_chain
        data["grainsize"] = 1
        
    # CHANGED: Updated logic for model_type
    if model_type == "direct":
        N = data["N"]
        if threads_per_chain:
            # When using threading, use grainsize=1 for maximum parallelization
            data["grainsize"] = 1
        else:
            # When not using threading, use a reasonable chunk size
            data["grainsize"] = max(1, min(10, N // 4))

    meta = sampler_kwargs.pop("_metadata", {})

    if stan_model_path:
        stan_file = Path(stan_model_path).name
        print(f"✅ Using specified Stan file: {stan_file}")
    else:
        data = patch_optional_predictors(data)
        predictor_usage = meta.get("predictor_usage", {})
        # CHANGED: Updated function call
        stan_file = _select_invT_stan_file(
            data, predictor_usage, 
            threads_per_chain=threads_per_chain,
            model_type=model_type,
            constraint_type=constraint_type)
        print(f"🔧 Automatically selected Stan file: {stan_file}")
    
    print(f"| M={data.get('M')} N={data.get('N')}")

    # Stan sampling
    model = _default_compiler.get_model(stan_file, cpp_options=cpp_options)
    ds = _default_sampler.sample_from_model(model, data, **sampler_kwargs)
    
    # Get memory info
    memory_info = simple_memory_check()
    tracemalloc.stop()
    
    priors = extract_priors_from_stan(stan_path=model.stan_file, data=data)
    if priors:
        ds.attrs["priors"] = [f"{k}: {v}" for k, v in priors.items()]

    ds = _attach_invT_metadata(ds, data, stan_file, site_name=site_name)
    
    ds.attrs["threads_per_chain"] = threads_per_chain if threads_per_chain else 0
    ds.attrs["threading_enabled"] = bool(threads_per_chain)
    ds.attrs["opencl_enabled"] = use_opencl
    ds.attrs["model_type"] = model_type
    
    ### memory usage
    ds.attrs["memory_peak_mb"] = round(memory_info['peak_mb'], 2)
    ds.attrs["memory_final_mb"] = round(memory_info['current_mb'], 2)

    # System information
    ds.attrs["system_os"] = system_info['system']
    ds.attrs["cpu_count_logical"] = system_info['cpu_count_logical']
    ds.attrs["cpu_count_physical"] = system_info['cpu_count_physical'] or 0
    ds.attrs["total_memory_gb"] = system_info['total_memory_gb'] or 0.0
    ds.attrs["python_version"] = system_info['python_version']
    ds.attrs["run_timestamp"] = system_info['run_timestamp']

    ds.attrs["system_info_json"] = json.dumps({
        k: v for k, v in system_info.items() 
        if k not in ['system', 'cpu_count_logical', 'cpu_count_physical', 'total_memory_gb', 'python_version', 'run_timestamp']
    })
    
    if model_type == "direct" and threads_per_chain:
        ds.attrs["grainsize"] = data.get("grainsize", 0)

    if temptype:
        ds.attrs["temptype"] = temptype
    elif 'thermoT' in fwd_posterior_name:
        ds.attrs["temptype"] = "thermoT"
    elif 'sst' in fwd_posterior_name:
        ds.attrs["temptype"] = "sst"
    else:
        ds.attrs["temptype"] = "unknown_temptype"

    post_ds = get_invT_post_quantiles(ds)
    
    # Performance
    runtime = time.perf_counter() - start_time
    post_ds.attrs["runtime_seconds"] = runtime
    post_ds.attrs["runtime_minutes"] = runtime / 60.0

    if save:
        _save_invT_posterior(
            posterior=post_ds,
            cache_dir=cache_dir,
            overwrite=True,
            filename_tag=filename_tag
        )
    return post_ds

# -------------------------------------------------------------------------
def _select_invT_stan_file(
    data: Dict, 
    predictor_usage: Dict[str, bool], 
    threads_per_chain: Optional[int] = None,
    model_type: Literal["direct", "ensemble"] = "direct",
    constraint_type: Literal["unconstrained", "hard_constraint", "reparameterized", "soft"] = "unconstrained"
) -> str:
    """
    Choose the correct Stan model file based on data structure.
    
    Args:
        model_type: 
            - "direct": Use direct sampling models (more efficient, supports threading)
            - "ensemble": Use traditional ensemble models
        constraint_type:
            - "unconstrained": No temperature constraints
            - "hard_constraint": Hard lower bound at -1.8°C
            - "reparameterized": Exponential transformation approach
            - "soft": Soft penalty for temperatures below -1.8°C
    """
    if "M" not in data:
        raise ValueError("Only ensemble mode is supported.")
    has_vQ = ("v" in data) or ("Q" in data)
    multiv = any(predictor_usage.values())
    
    base = "invT_gen_logi_fixed" if has_vQ else "invT_logistic_fixed"
    suffix = "_multiv" if multiv else "_univ"
    
    # Build model name based on model_type
    if model_type == "direct":
        model_name = f"{base}{suffix}_marginal"
    elif model_type == "ensemble":
        # Fallback to regular (ensemble) models
        if threads_per_chain:
            print("⚠️  Threading requires model_type='direct'. Switching to direct sampling model.")
            model_name = f"{base}{suffix}_marginal"
        else:
            model_name = f"{base}{suffix}"
    else:
        raise ValueError(f"Unknown model_type: {model_type}. Use 'direct' or 'ensemble'.")
    
    # ALWAYS add constraint suffix (including unconstrained)
    model_name += f"_{constraint_type}"
    
    return f"{model_name}.stan"
# -------------------------------------------------------------------------
def get_invT_post_quantiles(
    posterior: xr.Dataset,
    quantiles: Sequence[float] = (0.01, 0.05, 0.1, 0.16, 0.25, 0.4, 0.5,
                                  0.6, 0.75, 0.84, 0.9, 0.95, 0.99),
) -> xr.Dataset:
    """
    Calculate quantiles for the posterior draws. 
    
    Special handling for `t_est`:
    - Ensemble models: shape (chain, draw, N, M) → reduce over chain, draw, and M.
    - Marginal models: shape (chain, draw, N) → reduce over chain and draw.
    
    Other variables: reduce over available MCMC dims (chain, draw).
    """
    processed_vars = {}
    for var_name, data_array in posterior.data_vars.items():
        if var_name == "t_est":
            if "t_est_dim_1" in data_array.dims:   # Ensemble case
                dims_to_reduce = ["chain", "draw", "t_est_dim_1"]
            else:  # Marginal case
                dims_to_reduce = ["chain", "draw"]
            processed_vars[var_name] = data_array.quantile(quantiles, dim=dims_to_reduce)
        else:
            dims_to_reduce = [d for d in ["chain", "draw"] if d in data_array.dims]
            if dims_to_reduce:
                processed_vars[var_name] = data_array.quantile(quantiles, dim=dims_to_reduce)
            else:
                processed_vars[var_name] = data_array  # leave unchanged if no MCMC dims

    return xr.Dataset(processed_vars, attrs=posterior.attrs)

# -------------------------------------------------------------------------
def predict_temperature_from_RI(
    scaledRI: Union[np.ndarray, List[float]],
    prior_mu_t: Union[np.ndarray, float],
    prior_sigma_t: float,
    fwd_posterior_name: str,
    site_name: Optional[str] = None,
    temptype: Optional[str] = None,
    predictors: Optional[Dict[str, np.ndarray]] = None,
    config: Optional[InvTConfig] = None,
    chains: int = 4,
    iter_warmup: int = 500,
    iter_sampling: int = 1000,
    seed: Optional[int] = 42,
    save_results: bool = False,
    filename_tag: Optional[Union[str, Sequence[str]]] = None,
    results_path: Optional[Union[str, Path]] = None,
    use_opencl: bool = False,
    threads_per_chain: Optional[int] = None,
    stan_model_path: Optional[Union[str, Path]] = None,
    model_type: Literal["direct", "ensemble"] = "direct",
    constraint_type: Literal["unconstrained", "hard_constraint", "reparameterized", "soft"] = "unconstrained",
) -> Dict[str, Any]:
    """
    High-level wrapper to run the inverse model and get temperature percentiles.
    
    Args:
        model_type: 
            - "direct": Use direct sampling models (more efficient, supports threading)
            - "ensemble": Use traditional ensemble models
    """
    post_ds = get_invT_posterior(
        scaledRI=scaledRI,
        prior_mu_t=prior_mu_t,
        prior_sigma_t=prior_sigma_t,
        fwd_posterior_name=fwd_posterior_name,
        predictors=predictors,
        config=config,
        site_name=site_name,
        temptype=temptype,
        filename_tag=filename_tag,
        chains=chains,
        iter_warmup=iter_warmup,
        iter_sampling=iter_sampling,
        seed=seed,
        save=save_results,
        use_opencl=use_opencl,
        threads_per_chain=threads_per_chain,
        stan_model_path=stan_model_path,
        model_type=model_type,
        constraint_type=constraint_type,
    )

    metadata = {
        "fwd_posterior_name": fwd_posterior_name,
        "filename_tag": filename_tag,
        **post_ds.attrs
    }
    
    results = {
        "scaledRI": np.asarray(scaledRI),
        "metadata": metadata,
        'p5': post_ds['t_est'].sel(quantile=0.05, drop=True).values,
        'p50': post_ds['t_est'].sel(quantile=0.50, drop=True).values,
        'p95': post_ds['t_est'].sel(quantile=0.95, drop=True).values,
    }
        
    if save_results:
        _save_invT_results(results, results_path)
        
    return results

# -------------------------------------------------------------------------
# Helper functions for saving and file naming
# -------------------------------------------------------------------------

def _slug(x: str) -> str:
    s = str(x).strip().lower().replace(" ", "-")
    return re.sub(r"[^a-z0-9._-]+", "", s)

def _generate_filename_base(meta: Dict[str, Any], filename_tag: Optional[Union[str, Sequence[str]]]) -> str:
    """
    Generate the base filename for saving invT results.
    
    Format: {site}_{model}_{temptype}_{tags}_{model_type}
    Model type (direct/ensemble) goes at the end for easy identification.
    """
    site_name = meta.get("SiteName", meta.get("site_name", "unknown_site"))
    stan_model = meta.get("stan_model_name", meta.get("stan_model", "unknown_model"))
    temptype = meta.get("temptype", "unknown_temptype")
    
    # Clean up stan_model name (remove technical "marginal" suffix)
    if "marginal" in stan_model:
        model_type = "direct"
        clean_stan_model = stan_model.replace("_marginal", "")
    else:
        model_type = "ensemble"
        clean_stan_model = stan_model
    
    # Build temptype string with optional predictors
    temp_parts = [temptype]
    if int(meta.get("use_gdgt23ratio", 0)) == 1:
        temp_parts.append("gdgt23ratio")
    if int(meta.get("use_no3", 0)) == 1:
        no3_cutoff = meta.get("no3_cutoff")
        if no3_cutoff is None: 
            raise ValueError("no3_cutoff missing but use_no3=1.")
        temp_parts.append(f"no3_{no3_cutoff}")
    temptype_str = "_".join(temp_parts)
    
    # Build tag segment
    tag_segment = ""
    if filename_tag:
        tags = [filename_tag] if isinstance(filename_tag, str) else filename_tag
        tag_segment = "_" + "+".join(_slug(t) for t in tags if t)
    
    # NEW: Put model_type at the END
    return f"{site_name}_{clean_stan_model}_{temptype_str}{tag_segment}_{model_type}"

def _save_invT_posterior(
    posterior: xr.Dataset, 
    cache_dir: Optional[Union[str, Path]] = None, 
    overwrite: bool = True, 
    filename_tag: Optional[Union[str, Sequence[str]]] = None
    ) -> Path:
    
    output_dir = Path(cache_dir) if cache_dir else get_repo_root() / "TEXAS" / "invT_posterior_cache"
    output_dir.mkdir(parents=True, exist_ok=True)
    base = _generate_filename_base(posterior.attrs, filename_tag)
    filepath = output_dir / f"{base}.nc"
    if filepath.exists() and not overwrite:
        raise FileExistsError(f"{filepath} already exists and overwrite=False.")
    encoding = {var: {"zlib": True} for var in posterior.data_vars}
    sanitized_posterior = _sanitize_attrs_for_netcdf(posterior)
    sanitized_posterior.to_netcdf(filepath, encoding=encoding)
    print(f"✅ Posterior saved to {filepath}")
    return filepath

def _save_invT_results(results: Dict[str, Any], path: Optional[Union[str, Path]] = None, overwrite: bool = True) -> Path:
    meta = results.get("metadata", {})
    if path is None:
        output_dir = get_repo_root() / "TEXAS" / "invT_posterior_cache"
        output_dir.mkdir(parents=True, exist_ok=True)
        filename_tag = meta.get("filename_tag")
        base = _generate_filename_base(meta, filename_tag)
        path = output_dir / f"{base}.npz"
    else:
        path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists and overwrite=False.")
    savez_dict = {k: np.asarray(v) for k, v in results.items() if k != "metadata"}
    savez_dict["__metadata__"] = np.array([json.dumps(meta)])
    np.savez(path, **savez_dict)
    print(f"✅ invT results saved: {path}")
    return path

def _sanitize_attrs_for_netcdf(ds: xr.Dataset) -> xr.Dataset:
    """
    Sanitize dataset attributes for NetCDF compatibility.
    
    NetCDF only supports specific data types for attributes.
    Convert problematic types to compatible ones.
    """
    clean_attrs = {}
    for k, v in ds.attrs.items():
        if v is None:
            continue
        elif isinstance(v, bool):
            # Convert boolean to integer (0 or 1)
            clean_attrs[k] = int(v)
        elif isinstance(v, (str, bytes, int, float, np.number)):
            clean_attrs[k] = v
        elif isinstance(v, (list, tuple, np.ndarray)):
            # Convert to list, handling nested booleans
            arr = np.asarray(v)
            if arr.dtype == bool:
                clean_attrs[k] = arr.astype(int).tolist()
            else:
                clean_attrs[k] = arr.tolist()
        else:
            try:
                clean_attrs[k] = json.dumps(v)
            except TypeError:
                clean_attrs[k] = str(v)
    
    # Create a copy of the dataset with cleaned attributes
    ds_copy = ds.copy()
    ds_copy.attrs = clean_attrs
    return ds_copy

def simple_memory_check():
    """Simple memory tracking using built-in Python tools."""
    # Force garbage collection for accurate measurement
    gc.collect()
    
    # Get current memory usage
    if tracemalloc.is_tracing():
        current, peak = tracemalloc.get_traced_memory()
        return {
            'current_mb': current / 1024 / 1024,
            'peak_mb': peak / 1024 / 1024
        }
    else:
        return {'current_mb': 0, 'peak_mb': 0}
    
def get_system_info():
    """Collect comprehensive system information for reproducibility."""
    try:
        cpu_freq = psutil.cpu_freq()
        cpu_freq_current = cpu_freq.current if cpu_freq else None
        cpu_freq_max = cpu_freq.max if cpu_freq else None
    except (AttributeError, OSError):
        cpu_freq_current = None
        cpu_freq_max = None
    
    try:
        memory = psutil.virtual_memory()
        total_memory_gb = memory.total / (1024**3)
        available_memory_gb = memory.available / (1024**3)
    except:
        total_memory_gb = None
        available_memory_gb = None
    
    return {
        # System basics
        'system': platform.system(),                    # Linux, Darwin, Windows
        'platform': platform.platform(),               # Detailed platform info
        'architecture': platform.architecture()[0],    # x86_64, arm64, etc.
        'processor': platform.processor(),              # CPU model info
        'hostname': platform.node(),                   # Computer name
        
        # CPU information
        'cpu_count_logical': multiprocessing.cpu_count(),     # Logical cores (with hyperthreading)
        'cpu_count_physical': psutil.cpu_count(logical=False) if hasattr(psutil, 'cpu_count') else None,
        'cpu_freq_current_mhz': round(cpu_freq_current) if cpu_freq_current else None,
        'cpu_freq_max_mhz': round(cpu_freq_max) if cpu_freq_max else None,
        
        # Memory information
        'total_memory_gb': round(total_memory_gb, 1) if total_memory_gb else None,
        'available_memory_gb': round(available_memory_gb, 1) if available_memory_gb else None,
        
        # Python environment
        'python_version': platform.python_version(),
        'python_implementation': platform.python_implementation(),
        
        # Timestamp
        'run_timestamp': datetime.now().isoformat(),
    }