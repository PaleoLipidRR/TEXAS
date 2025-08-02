# TEXAS/stan/invT.py

from typing import Union, Optional, Dict
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
        use_flags=use_flags,
        n_draws=cfg.n_draws,
        seed=cfg.seed,
        reduction=cfg.reduction,
        mode=cfg.mode,
        no3_cutoff=cfg.no3_cutoff,
    )

    # 2) pick Stan file name based on data + config
    stan_file = _select_invT_stan_file(data, cfg)

    # 3) sample
    ds = _default_sampler.sample(data, stan_file, **sampler_kwargs)

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
    .stan filename.
    """
    is_ensemble = "M" in data
    has_vQ      = any(k in data for k in ("v", "Q"))
    multiv      = bool(data.get("use_gdgt23ratio", 0) or data.get("use_no3", 0))

    if is_ensemble:
        if multiv:
            return "invT_logistic_fixed_multiv_ensemble"
        else:
            return "invT_logistic_fixed_univ_ensemble"
    else:
        # meanprior_bayes
        if multiv:
            return "invT_logistic_fixed_multiv_meanprior_bayes"
        else:
            if has_vQ:
                return "invT_gen_logi_fixed_univ_meanprior_bayes"
            else:
                return "invT_logistic_fixed_univ_meanprior_bayes"


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
