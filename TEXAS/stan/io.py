# TEXAS/stan/io.py

from pathlib import Path
from typing import Union, Optional
import xarray as xr

__all__ = [
    "save_posterior",
    "load_posterior",
    "save_invT_posterior",
]

# By default, write into your repo under TEXAS/posterior_cache
DEFAULT_FORWARD_DIR = Path(__file__).parent.parent / "posterior_cache"
DEFAULT_INVT_DIR    = Path(__file__).parent.parent / "invT_posterior_cache"
DEFAULT_FORWARD_DIR.mkdir(exist_ok=True, parents=True)
DEFAULT_INVT_DIR.mkdir(exist_ok=True, parents=True)


def save_posterior(
    posterior: xr.Dataset,
    cache_dir: Optional[Union[str, Path]] = None,
    overwrite: bool = True,
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

    outpath = outdir / f"{name}_{ttype}.nc"
    if outpath.exists() and not overwrite:
        raise FileExistsError(f"{outpath} exists and overwrite=False")

    # record the filename in attrs
    posterior.attrs["filename"] = outpath.name

    encoding = {var: {"zlib": True} for var in posterior.data_vars}
    posterior.to_netcdf(outpath, encoding=encoding)
    print(f"Saved forward posterior to {outpath}")
    return outpath


def load_posterior(
    model_name: str,
    cache_dir: Optional[Union[str, Path]] = None,
) -> xr.Dataset:
    """
    Load a forward-model posterior from disk: `{model_name}.nc` in the default repo folder.
    """
    indir = Path(cache_dir) if cache_dir else DEFAULT_FORWARD_DIR
    indir.mkdir(exist_ok=True, parents=True)

    fpath = indir / f"{model_name}.nc"
    if not fpath.exists():
        raise FileNotFoundError(f"No forward posterior at {fpath}")
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
