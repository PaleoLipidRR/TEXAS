# TEXAS/stan/invT.py

from typing import Union, Optional, Dict, Sequence
import numpy as np
import xarray as xr

from .compiler import StanCompiler
from .sampler import StanSampler
from .metadata import extract_priors_from_stan

from ..data.builder import build_invT_inputData, InvTConfig

# instantiate once (you can override in tests or higher‐level code)
_default_compiler = StanCompiler()
_default_sampler  = StanSampler(_default_compiler)

def get_invT_posterior(
    scaledRI: np.ndarray,
    prior_mu_t: Union[np.ndarray, float],
    prior_sigma_t: float,
    fwd_posterior_name: str,
    predictors: Optional[Dict[str, np.ndarray]] = None,
    use_flags:    Optional[Dict[str, bool]]    = None,
    config:       Optional[InvTConfig]          = None,
) -> xr.Dataset:
    """
    Build the Stan data for an inverse‐T model, sample it, and return
    the raw posterior as an xarray.Dataset (with metadata attached).
    """
    cfg = config or InvTConfig()
    predictors = predictors or {}
    use_flags  = use_flags  or {}

    # 1) build the `data` dict and any extra sampler‐flags (e.g. chains, seed)
    data, sampler_kwargs = build_invT_inputData(
        scaledRI=scaledRI,
        prior_mu_t=prior_mu_t,
        prior_sigma_t=prior_sigma_t,
        fwd_posterior_name=fwd_posterior_name,
        predictors=predictors,
        config=cfg,
    )

    # 2) pick Stan file name based on data + config
    stan_file = _select_invT_stan_file(data, cfg)
    
    # 🔍 Debug: print which Stan file will be used and what data keys it sees
    print("🔍 Stan file selected:", stan_file)
    print("📦 Data keys:", list(data.keys()))

    # 3) sample
    ds, _ = _default_sampler.sample(data, stan_file, **sampler_kwargs,
                                    show_console=True)

    # 4) parse/attach priors
    #    (optional, but often handy)
    priors = extract_priors_from_stan(
        stan_path=_default_compiler.get_model_path(stan_file),
        data=data
    )
    if priors:
        ds.attrs["priors"] = priors

    return ds


def _select_invT_stan_file(data: dict, cfg: InvTConfig) -> str:
    """
    Given the built data dict and your InvTConfig, choose the appropriate
    .stan filename. Uses both data structure and forward model metadata.
    """
    is_ensemble = "M" in data
    has_vQ      = any(k in data for k in ("v", "Q", "mu_v", "mu_Q"))
    multiv      = bool(data.get("use_gdgt23ratio", 0) or data.get("use_no3", 0))
    
    # Try to infer gen_logi structure from metadata
    model_name = data.get("calibration_model_name", "").lower()

    if "gen_logi" in model_name or has_vQ:
        if is_ensemble:
            return "invT_gen_logi_fixed_multiv_ensemble" if multiv else "invT_gen_logi_fixed_univ_ensemble"
        else:
            return "invT_gen_logi_fixed_multiv_meanprior_bayes" if multiv else "invT_gen_logi_fixed_univ_meanprior_bayes"
    
    # Fallback to original logic if no gen_logi in name or structure
    if is_ensemble:
        return "invT_logistic_fixed_multiv_ensemble" if multiv else "invT_logistic_fixed_univ_ensemble"
    else:
        return "invT_logistic_fixed_multiv_meanprior_bayes" if multiv else "invT_logistic_fixed_univ_meanprior_bayes"



def get_invT_post_quantiles(
    posterior: xr.Dataset,
    quantiles: Union[float, list] = (0.05, 0.50, 0.95),
) -> xr.Dataset:
    """
    Given the full invT posterior `Dataset`, extract t_est quantiles.
    """
    # ensure it's a list of floats between 0 and 1
    qs = np.atleast_1d(quantiles).tolist()
    if any(q < 0 or q > 1 for q in qs):
        raise ValueError("quantiles must be between 0 and 1")

    # `t_est` should be of shape (draw, obs)
    if "t_est" not in posterior:
        raise KeyError("Dataset does not contain 't_est'")

    return posterior["t_est"].quantile(qs, dim="draw", keep_attrs=True)

def predict_temperature_from_RI(
    scaledRI: np.ndarray,
    prior_mu_t: Union[np.ndarray, float],
    prior_sigma_t: float,
    fwd_posterior_name: str,
    predictors: Optional[Dict[str, np.ndarray]] = None,
    use_flags: Optional[Dict[str, bool]] = None,
    mode: str = "meanprior_bayes",
    no3_cutoff: Optional[float] = None,
    percentiles: Sequence[float] = (5, 50, 95),
    chains: int = 4,
    iter_warmup: int = 500,
    iter_sampling: int = 1000,
    seed: Optional[int] = 42,
) -> Dict[str, np.ndarray]:
    """
    One‐call wrapper: from scaledRI → posterior t_est quantiles.
    """
    config = InvTConfig(
        n_draws=chains * iter_sampling,
        seed=seed,
        reduction="none",
        mode=mode,
        no3_cutoff=no3_cutoff
    )


    # 1) Run posterior sampling
    post_ds = get_invT_posterior(
        scaledRI=scaledRI,
        prior_mu_t=prior_mu_t,
        prior_sigma_t=prior_sigma_t,
        fwd_posterior_name=fwd_posterior_name,
        predictors=predictors,
        use_flags=use_flags,
        config=config
    )

    # 2) Extract posterior draws of temperature
    temps = post_ds["t_est"].values   # shape (draws, N_obs)
    results = {
        "scaledRI": scaledRI,
        "metadata": {
            "stan_model": post_ds.attrs.get("model", "unknown"),
            "mode": mode,
            "use_vQ": "v" in post_ds or "Q" in post_ds,
            "n_draws": temps.shape[0],
            "percentiles": percentiles,
        }
    }

    for p in percentiles:
        results[f"p{int(p)}"] = np.percentile(temps, p, axis=0)

    return results
