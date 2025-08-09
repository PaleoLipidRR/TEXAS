# TEXAS/stan/invT.py

from typing import Union, Optional, Dict, Sequence, List
import numpy as np
import xarray as xr
from pathlib import Path
import json
import re

from .compiler import StanCompiler
from .sampler import StanSampler
from .metadata import extract_priors_from_stan
from .utils import patch_optional_predictors
from ..data.builder import build_invT_inputData, InvTConfig
from TEXAS.utils import get_repo_root 
from TEXAS.stan.io import load_posterior

# Instantiate once
_default_compiler = StanCompiler()
_default_sampler  = StanSampler(_default_compiler)

# -------------------------------------------------------------------------
def _attach_invT_metadata(
    ds: xr.Dataset, 
    data: dict, 
    stan_file: str, 
    predictor_usage = None,
    site_name: Optional[str] = None
) -> xr.Dataset:
    # Model name expected by saver
    ds.attrs["stan_model_name"] = stan_file
    # Temperature type (set something meaningful if you have it elsewhere)
    ds.attrs.setdefault("temptype", "unknown")

    # Optional predictors flags
    ds.attrs["use_gdgt23ratio"] = int(bool(data.get("use_gdgt23ratio", 0)))
    ds.attrs["use_no3"] = int(bool(data.get("use_no3", 0)))

    # Handle no3_cutoff logic
    if ds.attrs["use_no3"] == 1:
        cutoff = float(data.get("no3_cutoff", 0.0))
        if cutoff > 0.0:
            ds.attrs["no3_cutoff"] = cutoff
        else:
            # no3 array was provided but all zeros → disable effect
            ds.attrs["no3_cutoff"] = 0.0
    else:
        # Ensure attribute exists but is zero if no3 not used
        ds.attrs["no3_cutoff"] = 0.0

    # Optional – filename includes site
    if site_name:
        ds.attrs["SiteName"] = site_name
    else:
        ds.attrs.setdefault("SiteName", "unknown_site")

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
    cache_name: Optional[str] = None,  
) -> xr.Dataset:
    """Run inverse-T model and return posterior Dataset with metadata."""
    cfg = config or InvTConfig()
    predictors = predictors or {}

    # Build Stan data and sampler kwargs
    data, sampler_kwargs = build_invT_inputData(
        scaledRI=scaledRI,
        prior_mu_t=prior_mu_t,
        prior_sigma_t=prior_sigma_t,
        fwd_posterior_name=fwd_posterior_name,
        predictors=predictors,
        config=cfg,
    )

    # Extract predictor usage from builder metadata
    meta = sampler_kwargs.pop("_metadata", {})
    predictor_usage = meta.get("predictor_usage", {})

    # Patch predictors if needed (ensures all required keys present)
    data = patch_optional_predictors(data)

    # Select correct Stan file
    stan_file = _select_invT_stan_file(data, predictor_usage)
    print(f"🔍 Stan file: {stan_file} | keys: {list(data.keys())} | M={data.get('M')} N={data.get('N')}")

    # Ensure default sampler settings
    sampler_kwargs.setdefault("chains", 4)
    sampler_kwargs.setdefault("iter_warmup", 500)
    sampler_kwargs.setdefault("iter_sampling", 1000)

    # Run sampling
    ds, _ = _default_sampler.sample(data, stan_file, **sampler_kwargs)

    # Extract priors
    stan_path = _default_compiler.resolve_stan_path(stan_file)
    priors = extract_priors_from_stan(stan_path=stan_path, data=data)
    if priors:
        ds.attrs["priors"] = [f"{k}: {v}" for k, v in priors.items()]

    # Attach metadata
    ds = _attach_invT_metadata(ds, data, stan_file, predictor_usage, site_name=site_name)

    # temptype logic
    if temptype:
        ds.attrs["temptype"] = temptype
    else:
        if 'thermoT' in fwd_posterior_name:
            ds.attrs["temptype"] = "thermoT"
        elif 'sst' in fwd_posterior_name:
            ds.attrs["temptype"] = "sst"
        else:
            ds.attrs["temptype"] = "unknown_temptype"

    # Convert to quantiles
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
def _select_invT_stan_file(data, predictor_usage: Dict[str, bool]):
    """Choose Stan file based on logistic variant and predictor usage."""
    if "M" not in data:
        raise ValueError("Only ensemble mode is supported")
    has_vQ = ("v" in data) or ("Q" in data)
    multiv = any(predictor_usage.values())
    return (
        "invT_gen_logi_fixed_multiv" if has_vQ and multiv else
        "invT_gen_logi_fixed_univ"   if has_vQ else
        "invT_logistic_fixed_multiv" if multiv else
        "invT_logistic_fixed_univ"
    )

# -------------------------------------------------------------------------
def get_invT_post_quantiles(
    posterior: xr.Dataset,
    quantiles: Sequence[float] = (0.01, 0.05, 0.1, 0.16, 0.25, 0.4, 0.5, 
                                  0.6, 0.75, 0.84, 0.9, 0.95, 0.99),
) -> xr.Dataset:
    """Extract quantiles from posterior."""
    if not isinstance(posterior, xr.Dataset):
        raise TypeError("posterior must be an xarray.Dataset")
    if not all(0.0 <= q <= 1.0 for q in quantiles):
        raise ValueError("All quantiles must be between 0 and 1.")
    if "draw" not in posterior.dims:
        raise ValueError("Posterior dataset must contain a 'draw' dimension.")
    dims = ["draw"] if len(posterior.dims) <= 2 else ["draw", "dim_2"]
    return posterior.quantile(quantiles, dim=dims, keep_attrs=True)

# -------------------------------------------------------------------------
def predict_temperature_from_RI(
    scaledRI: Union[np.ndarray, List[float]],
    prior_mu_t: Union[np.ndarray, float],
    prior_sigma_t: float,
    fwd_posterior_name: str,
    site_name: Optional[str] = None,
    temptype: Optional[str] = None,
    predictors: Optional[Dict[str, np.ndarray]] = None,
    no3_cutoff: Optional[float] = 0,
    suffix: Optional[str] = None, 
    chains: int = 4,
    iter_warmup: int = 500,
    iter_sampling: int = 1000,
    seed: Optional[int] = 42,
    save_results: bool = False,  
    filename_tag: Optional[Union[str, Sequence[str]]] = None,     
    results_path: Optional[Union[str, Path]] = None, 
) -> Dict[str, np.ndarray]:
    """Convenience wrapper: scaledRI → posterior t_est percentiles."""
    config = InvTConfig(
        seed=seed,
        mode="ensemble",
        no3_cutoff=no3_cutoff,
        suffix=suffix
    )

    # Run posterior sampling
    post_ds = get_invT_posterior(
        scaledRI=scaledRI,
        prior_mu_t=prior_mu_t,
        prior_sigma_t=prior_sigma_t,
        fwd_posterior_name=fwd_posterior_name,
        predictors=predictors,
        config=config,
        site_name=site_name,
        temptype=temptype,
        filename_tag=filename_tag
    )

    results = {
        "scaledRI": scaledRI,
        "metadata": {
            "stan_model": post_ds.attrs.get("stan_model_name", "unknown"),
            "n_draws": post_ds["t_est"].shape[0],
            "site_name": post_ds.attrs.get("SiteName", "unknown_site"),
            "temptype": post_ds.attrs.get("temptype", "unknown_temptype"),
            "fwd_posterior_name": fwd_posterior_name,
            "filename_tag": filename_tag,
            **{k: post_ds.attrs.get(k) for k in post_ds.attrs if k.startswith("use_")},
            "no3_cutoff": post_ds.attrs.get("no3_cutoff"),
        }
    }
    
    results['p5'] = post_ds['t_est'].sel(quantile=0.05).values
    results['p50'] = post_ds['t_est'].sel(quantile=0.5).values
    results['p95'] = post_ds['t_est'].sel(quantile=0.95).values
        
    if save_results:
        _save_invT_results(results, results_path)
        
    return results

# -------------------------------------------------------------------------
def _save_invT_posterior(
    posterior: xr.Dataset,
    cache_dir: Union[str, Path] = None,
    overwrite: bool = True,
    filename_tag: Optional[Union[str, Sequence[str]]] = None,
) -> Path:
    """Save full posterior to NetCDF."""
    if not isinstance(posterior, xr.Dataset):
        raise TypeError("posterior must be an xarray.Dataset")
    output_dir = (get_repo_root() / "TEXAS" / "invT_posterior_cache") if cache_dir is None else Path(cache_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    site_name = posterior.attrs.get("SiteName", "unknown_site")
    stan_model_name = posterior.attrs.get("stan_model_name", "unknown_model")
    temptype = posterior.attrs.get("temptype", "unknown_temptype")

    # Append predictor flags to filename
    for k, v in posterior.attrs.items():
        if k.startswith("use_") and int(v) == 1:
            if k == "use_no3":
                no3_cutoff = posterior.attrs.get("no3_cutoff")
                if no3_cutoff is None:
                    raise ValueError("no3_cutoff must be set if use_no3=1.")
                temptype += f"_no3_{no3_cutoff}"
            else:
                temptype += f"_{k.replace('use_','')}"

    tag_segment = ""
    if filename_tag:
        if isinstance(filename_tag, (list, tuple)):
            tag_segment = "__" + "+".join(_slug(t) for t in filename_tag if t)
        else:
            tag_segment = "__" + _slug(filename_tag)

    base = f"{site_name}_{stan_model_name}_{temptype}{tag_segment}"
    filepath = output_dir / f"{base}.nc"
    
    if filepath.exists() and not overwrite:
        raise FileExistsError(f"{filepath} already exists and overwrite=False.")

    encoding = {var: {"zlib": True} for var in posterior.data_vars}
    posterior = _sanitize_attrs_for_netcdf(posterior)
    posterior.to_netcdf(filepath, encoding=encoding)
    print(f"✅ Posterior saved to {filepath}")
    return filepath

# -------------------------------------------------------------------------
def _save_invT_results(
    results: Dict[str, object],
    path: Optional[Union[str, Path]] = None,
    overwrite: bool = True,
) -> Path:
    """Save compact prediction summaries to NPZ."""
    if not isinstance(results, dict):
        raise TypeError("results must be a dict")
    meta = results.get("metadata", {}) or {}

    if path is None:
        cache_dir = get_repo_root() / "TEXAS" / "invT_posterior_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        site_name = meta.get("site_name", "unknown_site")
        stan_model_name = meta.get("stan_model", "unknown_model")
        temptype = meta.get("temptype", "unknown_temptype")

        for k, v in meta.items():
            if k.startswith("use_") and int(v) == 1:
                if k == "use_no3":
                    no3_cutoff = meta.get("no3_cutoff")
                    if no3_cutoff is None:
                        raise ValueError("no3_cutoff must be set if use_no3=1.")
                    temptype += f"_no3_{no3_cutoff}"
                else:
                    temptype += f"_{k.replace('use_','')}"

        tag = meta.get("filename_tag")
        tag_segment = ""
        if tag:
            if isinstance(tag, (list, tuple)):
                tag_segment = "__" + "+".join(_slug(t) for t in tag if t)
            else:
                tag_segment = "__" + _slug(tag)

        filename = f"{site_name}_{stan_model_name}_{temptype}{tag_segment}.npz"
        path = cache_dir / filename
    else:
        path = Path(path)

    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists and overwrite=False.")

    savez_dict = {
        k: np.asarray(v) if isinstance(v, (list, np.ndarray)) else v
        for k, v in results.items()
        if k != "metadata"
    }
    savez_dict["__metadata__"] = np.array([json.dumps(meta)])
    np.savez(path, **savez_dict)
    print(f"✅ invT results saved: {path}")
    return path

# -------------------------------------------------------------------------
def _sanitize_attrs_for_netcdf(ds: xr.Dataset) -> xr.Dataset:
    clean = {}
    for k, v in ds.attrs.items():
        if v is None:
            continue
        if isinstance(v, (str, bytes, int, float, np.number)):
            clean[k] = v
        elif isinstance(v, (list, tuple, np.ndarray)):
            clean[k] = np.asarray(v).tolist()
        else:
            clean[k] = json.dumps(v)
    ds.attrs = clean
    return ds

def _slug(x: str) -> str:
    s = str(x).strip().lower().replace(" ", "-")
    return re.sub(r"[^a-z0-9._-]+", "", s)
