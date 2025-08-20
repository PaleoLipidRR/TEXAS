# TEXAS/stan/invT.py (Revised 08/18/2025)

from typing import Union, Optional, Dict, Sequence, List, Any
import numpy as np
import xarray as xr
from pathlib import Path
import json
import re
import os

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
    site_name: Optional[str] = None
) -> xr.Dataset:
    """Attaches essential metadata to the posterior dataset."""
    ds.attrs["stan_model_name"] = stan_file
    ds.attrs.setdefault("temptype", "unknown")
    ds.attrs["use_gdgt23ratio"] = int(bool(data.get("use_gdgt23ratio", 0)))
    ds.attrs["use_no3"] = int(bool(data.get("use_no3", 0)))
    if ds.attrs["use_no3"] == 1:
        ds.attrs["no3_cutoff"] = float(data.get("no3_cutoff", 0.0))
    else:
        ds.attrs["no3_cutoff"] = 0.0
    ds.attrs["SiteName"] = site_name or "unknown_site"
    ds.attrs["use_marginal"] = 1 if "marginal" in stan_file else 0
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
    use_marginal: bool = False
) -> xr.Dataset:
    """
    Run the inverse-T model and return the posterior Dataset with metadata.
    """
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

    meta = sampler_kwargs.pop("_metadata", {})

    if stan_model_path:
        stan_file = Path(stan_model_path).name
        print(f"✅ Using specified Stan file: {stan_file}")
    else:
        data = patch_optional_predictors(data)
        predictor_usage = meta.get("predictor_usage", {})
        stan_file = _select_invT_stan_file(
            data, predictor_usage, 
            use_threading=bool(threads_per_chain),
            use_marginal=use_marginal)
        print(f"🔍 Automatically selected Stan file: {stan_file}")
    
    print(f"| M={data.get('M')} N={data.get('N')}")

    model = _default_compiler.get_model(stan_file, cpp_options=cpp_options)
    ds = _default_sampler.sample_from_model(model, data, **sampler_kwargs)

    priors = extract_priors_from_stan(stan_path=model.stan_file, data=data)
    if priors:
        ds.attrs["priors"] = [f"{k}: {v}" for k, v in priors.items()]

    ds = _attach_invT_metadata(ds, data, stan_file, site_name=site_name)

    if temptype:
        ds.attrs["temptype"] = temptype
    elif 'thermoT' in fwd_posterior_name:
        ds.attrs["temptype"] = "thermoT"
    elif 'sst' in fwd_posterior_name:
        ds.attrs["temptype"] = "sst"
    else:
        ds.attrs["temptype"] = "unknown_temptype"

    post_ds = get_invT_post_quantiles(ds)

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
    use_threading: bool = False,
    use_marginal: bool = False) -> str:
    """Choose the correct Stan model file based on data structure."""
    if "M" not in data:
        raise ValueError("Only ensemble mode is supported.")
    has_vQ = ("v" in data) or ("Q" in data)
    multiv = any(predictor_usage.values())
    
    base = "invT_gen_logi_fixed" if has_vQ else "invT_logistic_fixed"
    suffix = "_multiv" if multiv else "_univ"
    
    if use_marginal:
        return f"{base}{suffix}_marginal.stan"
    else:
        # fallback to the older replicate models
        fname = f"{base}{suffix}.stan"
        if use_threading:
            fname = fname.replace(".stan", "_reduce_sum.stan")
        return fname

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
    use_marginal: bool = False,
    
) -> Dict[str, Any]:
    """High-level wrapper to run the inverse model and get temperature percentiles."""
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
    )

    metadata = {
        "stan_model": post_ds.attrs.get("stan_model_name", "unknown"),
        "site_name": post_ds.attrs.get("SiteName", "unknown_site"),
        "temptype": post_ds.attrs.get("temptype", "unknown_temptype"),
        "fwd_posterior_name": fwd_posterior_name,
        "filename_tag": filename_tag,
        **{k: post_ds.attrs.get(k) for k in post_ds.attrs if k.startswith("use_")},
        "no3_cutoff": post_ds.attrs.get("no3_cutoff"),
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
    site_name = meta.get("SiteName", meta.get("site_name", "unknown_site"))
    stan_model = meta.get("stan_model_name", meta.get("stan_model", "unknown_model"))
    temptype = meta.get("temptype", "unknown_temptype")
    temp_parts = [temptype]
    if int(meta.get("use_gdgt23ratio", 0)) == 1:
        temp_parts.append("gdgt23ratio")
    if int(meta.get("use_no3", 0)) == 1:
        no3_cutoff = meta.get("no3_cutoff")
        if no3_cutoff is None: raise ValueError("no3_cutoff missing but use_no3=1.")
        temp_parts.append(f"no3_{no3_cutoff}")
    temptype_str = "_".join(temp_parts)
    tag_segment = ""
    if filename_tag:
        tags = [filename_tag] if isinstance(filename_tag, str) else filename_tag
        tag_segment = "__" + "+".join(_slug(t) for t in tags if t)
    return f"{site_name}_{stan_model}_{temptype_str}{tag_segment}"

def _save_invT_posterior(posterior: xr.Dataset, cache_dir: Optional[Union[str, Path]] = None, overwrite: bool = True, filename_tag: Optional[Union[str, Sequence[str]]] = None) -> Path:
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
    clean_attrs = {}
    for k, v in ds.attrs.items():
        if v is None:
            continue
        if isinstance(v, (str, bytes, int, float, np.number)):
            clean_attrs[k] = v
        elif isinstance(v, (list, tuple, np.ndarray)):
            clean_attrs[k] = np.asarray(v).tolist()
        else:
            try:
                clean_attrs[k] = json.dumps(v)
            except TypeError:
                clean_attrs[k] = str(v)
    ds.attrs = clean_attrs
    return ds