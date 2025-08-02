# TEXAS/data/builder.py

from pathlib import Path
from typing import (
    Dict, Tuple, Optional, List, Union
)
from dataclasses import dataclass

import numpy as np
import xarray as xr

from TEXAS.data.filter import ensure_numpy
from TEXAS.stan.io import load_posterior

# ─── Configuration ───────────────────────────────────────────────────────

@dataclass
class InvTConfig:
    mode: str = "meanprior_bayes"     # "meanprior_bayes" or "ensemble"
    reduction: str = "mean"           # "mean" or "median"
    n_draws: int = 100
    seed: int = 42
    no3_cutoff: float = 0.0

# ─── Internals ───────────────────────────────────────────────────────────

_PRIORITY_SUFFIXES = ["crtp", "culmesocore", "culmeso", "meso", "cul"]
_OPTIONAL_PREDICTORS = ["gdgt23ratio", "no3"]
_FORWARD_PARAMS = ["t0", "k", "b"]
_EXTRA_PARAMS = ["v", "Q"]

def _infer_suffixes(data_vars: List[str]) -> Tuple[Optional[str], Dict[str,str]]:
    """
    Find the common suffix for t0, k, b in a posterior dataset.
    """
    suffix_map: Dict[str,str] = {}
    param_to_suff = {
        p: [v.split(f"{p}_",1)[1] for v in data_vars if v.startswith(f"{p}_")]
        for p in _FORWARD_PARAMS
    }
    common = set(param_to_suff["t0"])
    for p in ["k","b"]:
        common &= set(param_to_suff[p])
    if common:
        for s in _PRIORITY_SUFFIXES:
            if s in common:
                return s, {p: s for p in _FORWARD_PARAMS}
        sel = sorted(common)[0]
        return sel, {p: sel for p in _FORWARD_PARAMS}
    # fallback per‐param first candidate
    for p, sufs in param_to_suff.items():
        if sufs:
            suffix_map[p] = sufs[0]
    if len(set(suffix_map.values())) == 1 and len(suffix_map)==3:
        only = next(iter(suffix_map.values()))
        return only, {p: only for p in _FORWARD_PARAMS}
    return None, suffix_map

# ─── Public Builder ──────────────────────────────────────────────────────

def build_invT_inputData(
    scaledRI: Union[np.ndarray, List[float]],
    prior_mu_t: Union[np.ndarray, float],
    prior_sigma_t: float,
    fwd_posterior_name: str,
    predictors: Optional[Dict[str, np.ndarray]] = None,
    use_flags:    Optional[Dict[str, bool]] = None,
    config:       InvTConfig = InvTConfig(),
) -> Tuple[Dict[str, Union[int,float,np.ndarray]], Dict[str,bool]]:
    """
    Build the `data` dict for an inverse-T Stan model.

    Returns
    -------
    data_dict : dict
      Ready to pass to `CmdStanModel.sample(...)`
    use_flags : dict
      Echo of which predictors got switched on (same shape as predictors)
    """
    # 1) seed & defaults
    np.random.seed(config.seed)
    predictors = predictors or {}
    use_flags  = use_flags  or {}

    # 2) load forward posterior
    post: xr.Dataset = load_posterior(fwd_posterior_name)
    vars_ = list(post.data_vars)

    # 3) prepare obs arrays
    y = np.asarray(scaledRI, float)
    N = y.size

    # 3a) expand scalar prior_mu_t
    if np.isscalar(prior_mu_t):
        mu_t = np.full(N, float(prior_mu_t))
    else:
        mu_t = np.asarray(prior_mu_t, float)
        if mu_t.shape[0] != N:
            raise ValueError("prior_mu_t length must match scaledRI length")

    # 4) infer suffix for t0,k,b
    used_suffix, _ = _infer_suffixes(vars_)
    if used_suffix is None:
        raise ValueError("Could not infer parameter suffix from posterior")

    # 5) summarizers
    def _summ(name: str) -> float:
        arr = post[name].values
        return float(np.median(arr)) if config.reduction=="median" else float(np.mean(arr))
    def _std(name: str) -> float:
        sd = float(np.std(post[name].values))
        if sd <= 0 or np.isnan(sd):
            raise ValueError(f"Invalid std for {name}")
        return sd

    # 6) base data dict
    data: Dict[str,Union[int,float,np.ndarray]] = {
        "N": N,
        "scaledRI": y,
        "prior_mu_t": mu_t,
        "prior_sigma_t": float(prior_sigma_t),
    }
    used_posts: List[str] = []

    # 7) populate depending on mode
    if config.mode == "meanprior_bayes":
        # ➤ mu_/std_ for t0,k,b
        for p in _FORWARD_PARAMS:
            key = f"{p}_{used_suffix}"
            data[f"mu_{p}"]  = _summ(key)
            data[f"std_{p}"] = _std(key)
            used_posts.append(key)
        # ➤ v,Q if present
        for p in _EXTRA_PARAMS:
            key = f"{p}_{used_suffix}"
            if key in post:
                data[f"mu_{p}"]  = _summ(key)
                data[f"std_{p}"] = _std(key)
                used_posts.append(key)
        # ➤ sigma_scaledRI
        sig = f"sigma_scaledRI_{used_suffix}"
        if sig in post:
            data["mu_sigma_scaledRI"]  = _summ(sig)
            data["std_sigma_scaledRI"] = _std(sig)
            used_posts.append(sig)
        else:
            data["mu_sigma_scaledRI"]  = 0.1
            data["std_sigma_scaledRI"] = 0.05

        # ➤ optional predictors
        for pred in _OPTIONAL_PREDICTORS:
            flag = False
            for suf in _PRIORITY_SUFFIXES:
                beta = f"beta0_{pred}_{suf}"
                if beta in post and pred in predictors:
                    arr = ensure_numpy(predictors[pred])
                    data[pred]               = arr
                    data[f"mu_beta0_{pred}"] = _summ(beta)
                    data[f"std_beta0_{pred}"]= _std(beta)
                    data[f"use_{pred}"]      = True
                    used_posts.append(beta)
                    flag = True
                    break
            if not flag:
                data[pred]               = np.zeros(N)
                data[f"mu_beta0_{pred}"]= 0.0
                data[f"std_beta0_{pred}"]= 0.1
                data[f"use_{pred}"]      = False

        data["no3_cutoff"] = float(config.no3_cutoff)

    else:  # ensemble mode
        draws = np.random.choice(post.dims["draw"], config.n_draws, replace=True)
        P = post.isel(draw=draws)
        data.update({
            "M": config.n_draws,
            **{p: P[f"{p}_{used_suffix}"].values
               for p in _FORWARD_PARAMS
               if f"{p}_{used_suffix}" in P},
            "sigma_scaledRI": next(
                (P[f"sigma_scaledRI_{s}"].values for s in _PRIORITY_SUFFIXES
                 if f"sigma_scaledRI_{s}" in P),
                np.ones(config.n_draws)*0.1
            )
        })
        # predictors in ensemble
        for pred in _OPTIONAL_PREDICTORS:
            arr = ensure_numpy(predictors.get(pred, np.zeros(N)))
            data[pred] = arr
            key = f"beta0_{pred}_{used_suffix}"
            if key in P:
                data[f"beta0_{pred}"] = P[key].values
                data[f"use_{pred}"]   = True
                used_posts.append(key)
            else:
                data[f"use_{pred}"]   = False

        data["no3_cutoff"] = float(config.no3_cutoff)

    # 8) record provenance
    data["posteriors_used"]        = used_posts
    data["calibration_model_name"] = post.attrs.get("stan_model_name", "")

    return data, use_flags
