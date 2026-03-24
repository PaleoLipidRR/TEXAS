# TEXAS/stan/io.py

from pathlib import Path
from typing import Union, Optional, Literal, Sequence, Any, Dict
from ..utils.paths import POSTERIOR_CACHE_DIR, INVT_CACHE_DIR
import json
import re
import numpy as np
import xarray as xr

__all__ = [
    "save_posterior",
    "load_posterior",
    "save_invT_posterior",
]

# By default, write into your repo under TEXAS/posterior_cache
DEFAULT_FORWARD_DIR = POSTERIOR_CACHE_DIR
DEFAULT_INVT_DIR = INVT_CACHE_DIR
DEFAULT_FORWARD_DIR.mkdir(exist_ok=True, parents=True)
DEFAULT_INVT_DIR.mkdir(exist_ok=True, parents=True)


def save_posterior(
    posterior: xr.Dataset,
    cache_dir: Optional[Union[str, Path]] = None,
    overwrite: bool = True,
    filename_suffix: str = "",
) -> Path:
    """
    Save a forward-model posterior to disk as compressed NetCDF.

    Default location: repo/.../TEXAS/posterior_cache/
    """
    if not isinstance(posterior, xr.Dataset):
        raise TypeError("posterior must be an xarray.Dataset")

    outdir = Path(cache_dir) if cache_dir else DEFAULT_FORWARD_DIR
    outdir.mkdir(exist_ok=True, parents=True)

    name  = posterior.attrs.get("stan_model_name", "unknown_model")
    ttype = posterior.attrs.get("temptype", "unknown")
    if posterior.attrs.get("use_gdgt23ratio", 0):
        ttype += "_gdgt23ratio"
    if posterior.attrs.get("use_no3", 0):
        cutoff = posterior.attrs.get("no3_cutoff")
        if cutoff is None:
            raise ValueError("no3_cutoff must be set when use_no3=1")
        ttype += f"_no3_{cutoff}"

    proxy_name = posterior.attrs.get("proxy_name", "") or ""
    proxy_tag = f"_{proxy_name}" if proxy_name and proxy_name != "unknown" else ""

    # sanitize suffix
    if filename_suffix:
        filename_suffix = f"_{filename_suffix.strip('_')}"

    outpath = outdir / f"{name}_{ttype}{proxy_tag}{filename_suffix}.nc"
    if outpath.exists() and not overwrite:
        raise FileExistsError(f"{outpath} exists and overwrite=False")

    posterior.attrs["filename"] = outpath.name
    if not posterior.attrs.get("proxy_name"):
        import warnings
        warnings.warn(
            "proxy_name is not set on this posterior. "
            "Pass proxy_name= to get_posterior() (e.g. proxy_name='scaledRI'). "
            "It is stored in the .nc file and used downstream to validate that "
            "the correct proxy type is passed to predict_T_from_proxyObs().",
            UserWarning, stacklevel=2,
        )
        posterior.attrs["proxy_name"] = "unknown"
    encoding = {var: {"zlib": True} for var in posterior.data_vars}
    sanitized = _sanitize_attrs_for_netcdf(posterior)
    sanitized.to_netcdf(outpath, encoding=encoding)
    print(f"Saved forward posterior to {outpath}  [proxy_name='{posterior.attrs['proxy_name']}']")
    return outpath


def load_posterior(
    model_name: str,
    model_type: Literal["forward", "invT"] = "forward",
    cache_dir: Optional[Union[str, Path]] = None,
) -> xr.Dataset:
    """
    Load a posterior from disk: `{model_name}.nc` in the appropriate cache directory.
    
    Args:
        model_name: Name of the model file (without .nc extension)
        model_type: Type of posterior ("forward" or "invT")
        cache_dir: Custom cache directory (overrides default locations)
    
    Returns:
        xarray.Dataset containing the posterior
        
    Raises:
        FileNotFoundError: If the posterior file doesn't exist
    """
    # Determine cache directory
    if cache_dir:
        indir = Path(cache_dir)
    elif model_type == "forward":
        indir = DEFAULT_FORWARD_DIR
    elif model_type == "invT":
        indir = DEFAULT_INVT_DIR
    else:
        # This shouldn't happen due to type hints, but just in case
        raise ValueError(f"Invalid model_type: {model_type}. Must be 'forward' or 'invT'")
    
    # Ensure directory exists
    indir.mkdir(exist_ok=True, parents=True)
    
    # Construct file path
    fpath = indir / f"{model_name}.nc"
    
    # Check if file exists; if not, attempt auto-download from Zenodo (Option 1)
    if not fpath.exists():
        if model_type == "forward":
            try:
                from ..utils.download import download_posterior
                download_posterior(model_name, cache_dir=indir)
            except (KeyError, RuntimeError) as e:
                raise FileNotFoundError(
                    f"No forward posterior found at {fpath}.\n"
                    f"Available local files: {list(indir.glob('*.nc'))}\n"
                    f"Auto-download: {e}"
                ) from None
        else:
            raise FileNotFoundError(
                f"No {model_type} posterior found at {fpath}. "
                f"Available files: {list(indir.glob('*.nc'))}"
            )

    return xr.load_dataset(fpath)


def save_invT_posterior(
    posterior: xr.Dataset,
    cache_dir: Optional[Union[str, Path]] = None,
    overwrite: bool = True,
) -> Path:
    """
    Save an inverse-T posterior to disk as compressed NetCDF.

    Default location: repo/.../TEXAS/invT_posterior_cache/
    """
    if not isinstance(posterior, xr.Dataset):
        raise TypeError("posterior must be an xarray.Dataset")

    outdir = Path(cache_dir) if cache_dir else DEFAULT_INVT_DIR
    outdir.mkdir(exist_ok=True, parents=True)

    site  = posterior.attrs.get("SiteName", "unknown_site")
    name  = posterior.attrs.get("stan_model_name", "unknown_model")
    ttype = posterior.attrs.get("temptype", "unknown")
    if posterior.attrs.get("use_gdgt23ratio", 0):
        ttype += "_gdgt23ratio"
    if posterior.attrs.get("use_no3", 0):
        cutoff = posterior.attrs.get("no3_cutoff")
        if cutoff is None:
            raise ValueError("no3_cutoff must be set when use_no3=1")
        ttype += f"_no3_{cutoff}"

    outpath = outdir / f"{site}_{name}_{ttype}.nc"
    if outpath.exists() and not overwrite:
        raise FileExistsError(f"{outpath} exists and overwrite=False")

    posterior.attrs["filename"] = outpath.name
    posterior.attrs.setdefault("proxy_name", "")
    encoding = {var: {"zlib": True} for var in posterior.data_vars}
    sanitized = _sanitize_attrs_for_netcdf(posterior)
    sanitized.to_netcdf(outpath, encoding=encoding)
    print(f"Saved inverse-T posterior to {outpath}")
    return outpath


# ─── Private helpers for invT I/O ──────────────────────────────────────────

def _slug(x: str) -> str:
    s = str(x).strip().replace(" ", "-")
    return re.sub(r"[^a-zA-Z0-9._-]+", "", s)


def _generate_filename_base(
    meta: Dict[str, Any],
    filename_tag: Optional[Union[str, Sequence[str]]],
) -> str:
    """
    Generate the base filename for saving invT results.

    Format: {site}_{model}_{temptype}_{tags}_{model_type}
    Model type (direct/ensemble) goes at the end for easy identification.
    """
    site_name = meta.get("SiteName", meta.get("site_name", "unknown_site"))
    stan_model = meta.get("stan_model_name", meta.get("stan_model", "unknown_model"))
    temptype = meta.get("temptype", "unknown_temptype")

    if "marginal" in stan_model:
        model_type = "direct"
        clean_stan_model = stan_model.replace("_marginal", "")
    else:
        model_type = "ensemble"
        clean_stan_model = stan_model

    temp_parts = [temptype]
    if int(meta.get("use_gdgt23ratio", 0)) == 1:
        temp_parts.append("gdgt23ratio")
    if int(meta.get("use_no3", 0)) == 1:
        no3_cutoff = meta.get("no3_cutoff")
        if no3_cutoff is None:
            raise ValueError("no3_cutoff missing but use_no3=1.")
        temp_parts.append(f"no3_{no3_cutoff}")
    temptype_str = "_".join(temp_parts)

    proxy_name = meta.get("proxy_name", "") or ""
    proxy_segment = f"_{_slug(proxy_name)}" if proxy_name and proxy_name != "unknown" else ""

    tag_segment = ""
    if filename_tag:
        tags = [filename_tag] if isinstance(filename_tag, str) else filename_tag
        tag_segment = "_" + "+".join(_slug(t) for t in tags if t)

    return f"{site_name}_{clean_stan_model}_{temptype_str}{proxy_segment}{tag_segment}_{model_type}"


def _sanitize_attrs_for_netcdf(ds: xr.Dataset) -> xr.Dataset:
    """Convert posterior attrs to NetCDF-compatible types."""
    clean_attrs = {}
    for k, v in ds.attrs.items():
        if v is None:
            continue
        elif isinstance(v, bool):
            clean_attrs[k] = int(v)
        elif isinstance(v, (str, bytes, int, float, np.number)):
            clean_attrs[k] = v
        elif isinstance(v, (list, tuple, np.ndarray)):
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

    ds_copy = ds.copy()
    ds_copy.attrs = clean_attrs
    return ds_copy


def _save_invT_posterior(
    posterior: xr.Dataset,
    cache_dir: Optional[Union[str, Path]] = None,
    overwrite: bool = True,
    filename_tag: Optional[Union[str, Sequence[str]]] = None,
) -> Path:
    """Save an invT posterior with detailed auto-generated filename."""
    output_dir = Path(cache_dir) if cache_dir else DEFAULT_INVT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    base = _generate_filename_base(posterior.attrs, filename_tag)
    filepath = output_dir / f"{base}.nc"
    if filepath.exists() and not overwrite:
        raise FileExistsError(f"{filepath} already exists and overwrite=False.")
    posterior.attrs.setdefault("proxy_name", "")
    encoding = {var: {"zlib": True} for var in posterior.data_vars}
    sanitized = _sanitize_attrs_for_netcdf(posterior)
    sanitized.to_netcdf(filepath, encoding=encoding)
    print(f"✅ Posterior saved to {filepath}")
    return filepath


def _save_invT_results(
    results: Dict[str, Any],
    path: Optional[Union[str, Path]] = None,
    overwrite: bool = True,
) -> Path:
    """Save invT quantile results dict as a compressed .npz file."""
    meta = results.get("metadata", {})
    if path is None:
        output_dir = DEFAULT_INVT_DIR
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
