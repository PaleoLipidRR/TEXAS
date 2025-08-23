# TEXAS/stan/io.py

from pathlib import Path
from typing import Union, Optional, Literal
from ..utils.paths import POSTERIOR_CACHE_DIR, INVT_CACHE_DIR
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

    # sanitize suffix
    if filename_suffix:
        filename_suffix = f"_{filename_suffix.strip('_')}"

    outpath = outdir / f"{name}_{ttype}{filename_suffix}.nc"
    if outpath.exists() and not overwrite:
        raise FileExistsError(f"{outpath} exists and overwrite=False")

    posterior.attrs["filename"] = outpath.name
    encoding = {var: {"zlib": True} for var in posterior.data_vars}
    posterior.to_netcdf(outpath, encoding=encoding)
    print(f"Saved forward posterior to {outpath}")
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
    
    # Check if file exists and load
    if not fpath.exists():
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
    encoding = {var: {"zlib": True} for var in posterior.data_vars}
    posterior.to_netcdf(outpath, encoding=encoding)
    print(f"Saved inverse-T posterior to {outpath}")
    return outpath
