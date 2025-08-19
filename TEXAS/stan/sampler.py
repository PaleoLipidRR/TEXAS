# TEXAS/stan/sampler.py (Revised 08/18/2025)

import time
import numpy as np
import xarray as xr
from typing import Tuple, Optional, Dict, Tuple, Any
from cmdstanpy import CmdStanModel, CmdStanMCMC 

from .compiler import StanCompiler
from .io import save_posterior, load_posterior, save_invT_posterior
from .metadata import extract_and_update_metadata, extract_priors_from_stan
from .utils import patch_optional_predictors
from ..diagnostics import summarize_sampler_diagnostics



# ─── SAMPLER CLASS ─────────────────────────────────────────────────────────
class StanSampler:
    """A simple wrapper for running the Stan sampler."""
    def __init__(self, compiler: StanCompiler):
        self.compiler = compiler
        
    def sample_from_model(
        self,
        model: CmdStanModel,
        data: Dict,
        **kwargs,
    ) -> xr.Dataset:
        """Runs the sampler from a pre-compiled CmdStanModel object."""
        fit = model.sample(data=data, **kwargs)
        return fit.draws_xr()

    def sample(
        self,
        data: Dict[str, Any],
        stan_file: str,
        cpp_options: Dict = None,
        **kwargs,
    ) -> Tuple[xr.Dataset, str]:
        """
        Compiles, runs the sampler, and processes the output.
        """
        # Pop application-specific arguments that aren't for cmdstanpy
        temptype = kwargs.pop('temptype', None)
        site_name = kwargs.pop('site_name', None)
        version = kwargs.pop('version', '1.0.0') # Set a default version
        kwargs.pop('recompile', None) # Not used by the new compiler logic

        t0 = time.time()
        
        # Compile and sample
        model = self.compiler.get_model(stan_file, cpp_options=cpp_options)
        fit = model.sample(data=data, **kwargs)
        
        duration = time.time() - t0

        # 📊 Diagnostics
        diag_str = fit.diagnose()
        diag_summary = summarize_sampler_diagnostics(fit)

        # Convert to xarray and attach all metadata
        ds = self._to_xarray(fit)
        ds = extract_and_update_metadata(ds, data, stan_file, site_name, version)
        ds.attrs["run_duration (sec)"] = round(duration, 2)
        if temptype:
            ds.attrs["temptype"] = temptype

        # Attach priors
        stan_path = self.compiler.resolve_stan_path(stan_file)
        priors = extract_priors_from_stan(stan_path, data)
        if priors:
            ds.attrs["priors"] = [f"{k}: {v}" for k, v in priors.items()]

        # Attach sampler diagnostics
        for key, val in diag_summary.items():
            ds.attrs[key] = val

        return ds, diag_str

    def _to_xarray(self, fit: CmdStanMCMC) -> xr.Dataset:
        """Converts a CmdStanPy Fit to an xarray.Dataset."""
        return fit.draws_xr()

# ─── Functional API (wrappers around the class) ─────────────────────────────────

def get_posterior(
    data: dict,
    stan_file: str,
    temptype: str,
    **kwargs
) -> Tuple[xr.Dataset, str]:
    
    rng_seed = kwargs.setdefault("seed", 42)
    np.random.seed(rng_seed)
    
    compiler = StanCompiler()
    sampler = StanSampler(compiler)
    
    # This function now correctly passes all arguments to the comprehensive .sample() method
    return sampler.sample(
        data=data,
        stan_file=stan_file,
        temptype=temptype,
        **kwargs
    )

def sampler_invT_posterior(
    data: dict,
    stan_file: str,
    site_name: Optional[str] = None,
    temptype: Optional[str] = None,
    **kwargs
) -> Tuple[xr.Dataset, str]:
    
    rng_seed = kwargs.setdefault("seed", 42)
    np.random.seed(rng_seed)
    
    compiler = StanCompiler()
    sampler = StanSampler(compiler)
    
    return sampler.sample(
        data=data,
        stan_file=stan_file,
        site_name=site_name,
        temptype=temptype,
        **kwargs
    )
