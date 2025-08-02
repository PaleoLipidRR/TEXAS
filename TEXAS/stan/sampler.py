# TEXAS/stan/sampler.py

import time
import numpy as np
import xarray as xr
from typing import Tuple, Optional

from .compiler import StanCompiler
from .io import save_posterior, load_posterior, save_invT_posterior
from .metadata import extract_and_update_metadata
from ..diagnostics import summarize_sampler_diagnostics


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
        **sampling_kwargs
    ) -> Tuple[xr.Dataset, str]:
        """
        Sample from a Stan model and return (dataset, diagnostics).
        """
        # 1) compile or fetch cached CmdStanModel
        model = self.compiler.get_model(stan_file)

        # 2) draw samples, timing the call
        t0 = time.time()
        fit = model.sample(data=data, **sampling_kwargs)
        duration = time.time() - t0

        # 3) get the raw diagnostics string
        diag_str = fit.diagnose()

        # 4) convert to xarray
        ds = self._to_xarray(fit)

        # 5) attach run‐time & prior metadata
        ds = extract_and_update_metadata(ds, data, stan_file, site_name, version)
        ds.attrs["run_duration (sec)"] = round(duration, 2)
        if temptype is not None:
            ds.attrs["temptype"] = temptype
            
        ## pull priors directly out of the .stan file and record them
        from .metadata import extract_priors_from_stan
        stan_path = self.compiler.resolve_stan_path(stan_file)
        priors = extract_priors_from_stan(stan_path, data)
        if priors:
            ## store as list of "param_name: dist(...)" strings
            ds.attrs["priors"] = [f"{k}: {v}" for k, v in priors.items()]

        # 6) now summarize and attach detailed Stan diagnostics
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
        **kwargs
    )
