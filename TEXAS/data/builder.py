# TEXAS/data/builder.py

from pathlib import Path
from typing import Dict, Tuple, Optional, List, Union
from dataclasses import dataclass

import numpy as np
import xarray as xr
import warnings  # ensure this is at the top of your module

from TEXAS.constants import DEFAULT_SUFFIXES, OPTIONAL_PREDICTORS
from TEXAS.data.filter import ensure_numpy
from TEXAS.stan.io import load_posterior
from TEXAS.stan.utils import infer_optional_predictor_usage

@dataclass
class InvTConfig:
    mode: str = "meanprior_bayes"
    reduction: str = "mean"
    n_draws: int = 100
    seed: int = 42
    no3_cutoff: Optional[float] = None

_FORWARD_PARAMS = ["t0", "k", "b"]
_EXTRA_PARAMS = ["v", "Q"]

def _infer_suffixes(data_vars: List[str]) -> Tuple[Optional[str], Dict[str, str]]:
    suffix_map = {}
    param_to_suff = {
        p: [v.split(f"{p}_", 1)[1] for v in data_vars if v.startswith(f"{p}_")]
        for p in _FORWARD_PARAMS
    }
    common = set(param_to_suff["t0"])
    for p in ["k", "b"]:
        common &= set(param_to_suff[p])
    if common:
        for s in DEFAULT_SUFFIXES:
            if s in common:
                return s, {p: s for p in _FORWARD_PARAMS}
        sel = sorted(common)[0]
        return sel, {p: sel for p in _FORWARD_PARAMS}
    for p, sufs in param_to_suff.items():
        if sufs:
            suffix_map[p] = sufs[0]
    if len(set(suffix_map.values())) == 1 and len(suffix_map) == 3:
        only = next(iter(suffix_map.values()))
        return only, {p: only for p in _FORWARD_PARAMS}
    return None, suffix_map

def build_invT_inputData(
    scaledRI: Union[np.ndarray, List[float]],
    prior_mu_t: Union[np.ndarray, float],
    prior_sigma_t: float,
    fwd_posterior_name: str,
    predictors: Optional[Dict[str, np.ndarray]] = None,
    config: Optional[InvTConfig] = None,
) -> Tuple[Dict[str, Union[int, float, np.ndarray]], Dict[str, bool]]:
    config = config or InvTConfig()

    np.random.seed(config.seed)
    predictors = predictors or {}

    post: xr.Dataset = load_posterior(fwd_posterior_name)
    vars_ = list(post.data_vars)

    y = np.asarray(scaledRI, float)
    N = y.size

    mu_t = np.full(N, float(prior_mu_t)) if np.isscalar(prior_mu_t) else np.asarray(prior_mu_t, float)
    if mu_t.shape[0] != N:
        raise ValueError("prior_mu_t length must match scaledRI length")

    used_suffix, _ = _infer_suffixes(vars_)
    if used_suffix is None:
        raise ValueError("Could not infer parameter suffix from posterior")

    def _summ(name: str) -> float:
        arr = post[name].values
        return float(np.median(arr)) if config.reduction == "median" else float(np.mean(arr))

    def _std(name: str) -> float:
        sd = float(np.std(post[name].values))
        if sd <= 0 or np.isnan(sd):
            raise ValueError(f"Invalid std for {name}")
        return sd

    data = {
        "N": N,
        "scaledRI": y,
        "prior_mu_t": mu_t,
        "prior_sigma_t": float(prior_sigma_t),
    }
    used_posts = []

    if config.mode == "meanprior_bayes":
        for p in _FORWARD_PARAMS:
            key = f"{p}_{used_suffix}"
            data[f"mu_{p}"] = _summ(key)
            data[f"std_{p}"] = _std(key)
            used_posts.append(key)

        for p in _EXTRA_PARAMS:
            key = f"{p}_{used_suffix}"
            if key in post:
                data[f"mu_{p}"] = _summ(key)
                data[f"std_{p}"] = _std(key)
                used_posts.append(key)

        sig = f"sigma_scaledRI_{used_suffix}"
        if sig in post:
            data["mu_sigma_scaledRI"] = _summ(sig)
            data["std_sigma_scaledRI"] = _std(sig)
            used_posts.append(sig)
        else:
            data["mu_sigma_scaledRI"] = 0.1
            data["std_sigma_scaledRI"] = 0.05

        for pred in OPTIONAL_PREDICTORS:
            use_flag = post.attrs.get(f"use_{pred}", False)

            if use_flag and (pred not in predictors or predictors[pred] is None):
                warnings.warn(
                    f"[WARN] Posterior metadata indicates `use_{pred}=True`, "
                    f"but `{pred}` not found in predictors input or is None. Skipping this predictor."
                )

            if not use_flag:
                continue

            beta = f"beta0_{pred}_{used_suffix}"
            if beta in post:
                arr = ensure_numpy(predictors.get(pred))
                if arr is None or np.allclose(arr, 0):
                    continue  # Skip predictor if all zeros
                data[pred] = arr
                data[f"mu_beta0_{pred}"] = _summ(beta)
                data[f"std_beta0_{pred}"] = _std(beta)
                data[f"use_{pred}"] = 1
                used_posts.append(beta)



    else:
        draws = np.random.choice(post.dims["draw"], config.n_draws, replace=True)
        P = post.isel(draw=draws)

        data.update({
            "M": config.n_draws,
            **{p: P[f"{p}_{used_suffix}"].values for p in _FORWARD_PARAMS if f"{p}_{used_suffix}" in P},
            "sigma_scaledRI": next(
                (P[f"sigma_scaledRI_{s}"].values for s in DEFAULT_SUFFIXES if f"sigma_scaledRI_{s}" in P),
                np.ones(config.n_draws) * 0.1
            )
        })


        for pred in OPTIONAL_PREDICTORS:
            use_flag = post.attrs.get(f"use_{pred}", False)

            if use_flag and (pred not in predictors or predictors[pred] is None):
                warnings.warn(
                    f"[WARN] Posterior metadata indicates `use_{pred}=True`, "
                    f"but `{pred}` not found in predictors input or is None. Skipping this predictor."
                )

            if not use_flag:
                continue

            arr = ensure_numpy(predictors.get(pred))
            if arr is None or np.allclose(arr, 0):
                continue  # Skip predictor if all zeros
            data[pred] = arr
            key = f"beta0_{pred}_{used_suffix}"
            if key in P:
                data[f"beta0_{pred}"] = P[key].values
                data[f"use_{pred}"] = 1
                used_posts.append(key)

    data["no3_cutoff"] = float(config.no3_cutoff) if config.no3_cutoff is not None else 0.0

    data["posteriors_used"] = used_posts
    data["calibration_model_name"] = post.attrs.get("stan_model_name", "")

    use_flags = infer_optional_predictor_usage(data)

    for pred in OPTIONAL_PREDICTORS:
        use_key = f"use_{pred}"
        if use_key in data and not data.get(use_key):
            del data[use_key]

    return data, use_flags
