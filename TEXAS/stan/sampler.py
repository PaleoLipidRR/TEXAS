# TEXAS/stan/sampler.py

import time
import numpy as np
import xarray as xr
from typing import Tuple, Optional

from .compiler import StanCompiler
from .io import save_posterior, load_posterior, save_invT_posterior
from .metadata import extract_and_update_metadata
from ..diagnostics import summarize_sampler_diagnostics

# ─── OPTIONAL PREDICTOR PATCH ───────────────────────────────────────────────

def patch_optional_predictors(data: dict) -> dict:
    """
    Auto-infer and fill in optional predictor fields like use_gdgt23ratio and use_no3.
    """
    if "N_crtp" in data:
        N = data["N_crtp"]
        if "gdgt23ratio_crtp" not in data:
            data["gdgt23ratio_crtp"] = np.zeros(N)
        data["use_gdgt23ratio"] = int(np.any(data["gdgt23ratio_crtp"]))

        if "no3_crtp" not in data:
            data["no3_crtp"] = np.zeros(N)
        data["use_no3"] = int(np.any(data["no3_crtp"]))

        if data["use_no3"] and "no3_cutoff" not in data:
            raise ValueError("no3_cutoff must be set when using no3_crtp.")
    else:
        data["use_gdgt23ratio"] = 0
        data["use_no3"] = 0

    return data

# ─── SAMPLER CLASS ─────────────────────────────────────────────────────────

class StanSampler:
    def __init__(self, compiler: StanCompiler):
        self.compiler = compiler

    def sample(
        self,
        data: dict,
        stan_file: str,
        site_name: Optional[str] = None,
        temptype: Optional[str] = None,
        version: str = "1.0.0",
        recompile: bool = False,
        **sampling_kwargs
    ) -> Tuple[xr.Dataset, str]:
        """
        Sample from a Stan model and return (dataset, diagnostics).
        """
        # 🔧 Patch optional predictors
        data = patch_optional_predictors(data)

        # 🧱 Compile model
        model = self.compiler.get_model(stan_file, recompile=recompile)

        # 🚀 Sample
        t0 = time.time()
        fit = model.sample(data=data, **sampling_kwargs)
        duration = time.time() - t0

        # 📊 Diagnostics
        diag_str = fit.diagnose()
        ds = self._to_xarray(fit)
        ds = extract_and_update_metadata(ds, data, stan_file, site_name, version)
        ds.attrs["run_duration (sec)"] = round(duration, 2)
        if temptype:
            ds.attrs["temptype"] = temptype

        from .metadata import extract_priors_from_stan
        stan_path = self.compiler.resolve_stan_path(stan_file)
        priors = extract_priors_from_stan(stan_path, data)
        if priors:
            ds.attrs["priors"] = [f"{k}: {v}" for k, v in priors.items()]

        diag_summary = summarize_sampler_diagnostics(fit)
        for key, val in diag_summary.items():
            ds.attrs[f"stan_diag_{key}"] = val

        return ds, diag_str

    def _to_xarray(self, fit) -> xr.Dataset:
        """
        Convert a CmdStanPy Fit to an xarray.Dataset.
        """
        ds = xr.Dataset()
        for var in fit.stan_variables():
            arr = fit.stan_variable(var)  # numpy ndarray
            dims = ["draw"] + [f"dim_{i}" for i in range(1, arr.ndim)]
            coords = {dim: np.arange(sz) for dim, sz in zip(dims, arr.shape)}
            ds[var] = xr.DataArray(arr, dims=dims, coords=coords, name=var)
        return ds

# ─── Functional API ─────────────────────────────────────────────────────

def get_posterior(
    data: dict,
    stan_file: str,
    temptype: str,
    chains: int = 4,
    iter_warmup: int = 500,
    iter_sampling: int = 1000,
    recompile: bool = False,
    **kwargs
) -> Tuple[xr.Dataset, str]:
    compiler = StanCompiler()
    sampler = StanSampler(compiler)
    return sampler.sample(
        data=data,
        stan_file=stan_file,
        temptype=temptype,
        chains=chains,
        iter_warmup=iter_warmup,
        iter_sampling=iter_sampling,
        recompile=recompile,
        **kwargs
    )

def get_invT_posterior(
    data: dict,
    stan_file: str,
    site_name: Optional[str] = None,
    temptype: Optional[str] = None,
    chains: int = 4,
    iter_warmup: int = 500,
    iter_sampling: int = 1000,
    recompile: bool = False,
    **kwargs
) -> Tuple[xr.Dataset, str]:
    compiler = StanCompiler()
    sampler = StanSampler(compiler)
    return sampler.sample(
        data=data,
        stan_file=stan_file,
        site_name=site_name,
        temptype=temptype,
        chains=chains,
        iter_warmup=iter_warmup,
        iter_sampling=iter_sampling,
        recompile=recompile,
        **kwargs
    )
