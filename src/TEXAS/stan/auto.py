# TEXAS/stan/auto.py
from __future__ import annotations
import os, shutil, logging
from typing import Any, Dict, List, Union
import numpy as np

from TEXAS.utils.hw import detect_opencl_available
from TEXAS.stan.invT import predict_temperature_from_RI as _predict_raw

log = logging.getLogger(__name__)

def _clear_cmdstanpy_cache():
    cache_dir = os.path.expanduser("~/.cmdstanpy")
    # Only clear if switching OpenCL mode to avoid stale binaries.
    try:
        import pathlib, shutil as _shutil
        p = pathlib.Path(cache_dir)
        if p.exists():
            _shutil.rmtree(p)
            log.info("Cleared CmdStanPy cache at %s", p)
    except Exception as e:
        log.warning("Failed to clear CmdStanPy cache: %r", e)

def predict_temperature_from_RI_auto(
    *,
    scaledRI: Union[np.ndarray, List[float]],
    prior_mu_t: Union[np.ndarray, float],
    prior_sigma_t: float,
    fwd_posterior_name: str,
    site_name: str = "site",
    temptype: str = "sst",
    predictors: Dict[str, Any] | None = None,
    config: Dict[str, Any] | None = None,
    chains: int = 4,
    iter_warmup: int = 1000,
    iter_sampling: int = 1000,
    seed: int | None = 42,
    save_results: bool = False,
    filename_tag: str | None = None,
    results_path: str | None = None,
    # optional overrides
    use_opencl: bool | None = None,
    threads_per_chain: int | None = None,
    stan_model_path: str | None = None,
) -> Dict[str, Any]:
    """
    Drop-in replacement that auto-detects OpenCL unless explicitly overridden.

    Set TEXAS_USE_OPENCL=1 or 0 to force behavior without changing code.
    """
    # 1) Decide OpenCL
    want_opencl = detect_opencl_available() if use_opencl is None else bool(use_opencl)
    
    if use_opencl is True and not detect_opencl_available():
        log.warning("OpenCL forced but not available; falling back to CPU.")
        want_opencl = False

    # 2) If switching between CPU<->OpenCL within same container session,
    #    clear cache so the binary is compiled with correct flags.
    #    You can optimize this by persisting the last-used mode in a temp file.
    last_mode_file = "/tmp/texas_last_opencl_mode"
    try:
        last = None
        if os.path.exists(last_mode_file):
            with open(last_mode_file, "r") as f:
                last = f.read().strip()
        if last is None or last != ("opencl" if want_opencl else "cpu"):
            _clear_cmdstanpy_cache()
            with open(last_mode_file, "w") as f:
                f.write("opencl" if want_opencl else "cpu")
    except Exception as e:
        log.debug("Skipping mode tracking cache step: %r", e)

    # 3) Call through to the real implementation
    return _predict_raw(
        scaledRI=scaledRI,
        prior_mu_t=prior_mu_t,
        prior_sigma_t=prior_sigma_t,
        fwd_posterior_name=fwd_posterior_name,
        site_name=site_name,
        temptype=temptype,
        predictors=predictors,
        config=config,
        chains=chains,
        iter_warmup=iter_warmup,
        iter_sampling=iter_sampling,
        seed=seed,
        save_results=save_results,
        filename_tag=filename_tag,
        results_path=results_path,
        use_opencl=want_opencl,
        threads_per_chain=threads_per_chain,
        stan_model_path=stan_model_path,
    )
