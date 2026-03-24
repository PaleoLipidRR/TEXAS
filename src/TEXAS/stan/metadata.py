# TEXAS/stan/metadata.py

import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

import numpy as np
import xarray as xr
from TEXAS.constants import OPTIONAL_PREDICTORS, DEFAULT_SUFFIXES, DIRECT_KEYS

# ——— module‐level defaults —————————————————————————————————————————

_PRIOR_REGEX = re.compile(
    r"(\w+)\s*~\s*([A-Za-z_]\w*)\s*\(([^)]*)\)(\s*T\[[^\]]+\])?"
)

# ——— metadata extractor ———————————————————————————————————————————————

def extract_and_update_metadata(
    ds: xr.Dataset,
    data: Dict[str, Any],
    stan_filename: str,
    site_name: Optional[str]    = None,
    version:   str              = "1.0.0",
    suffixes:  List[str]        = None,
    direct_keys: List[str]      = None
) -> xr.Dataset:
    """
    Attach run‐time metadata and summaries to an xarray.Dataset.

    Parameters
    ----------
    ds : xr.Dataset
      The dataset of posterior draws.
    data : dict
      The original dict passed to Stan.
    stan_filename : str
      Base name of the compiled .stan file.
    site_name : str, optional
      A label for this run (e.g. coretop site).
    version : str, optional
      Your package or model version.
    suffixes : list of str, optional
      Which suffixes to scan for proxyObs_* and predictor_* arrays.
    direct_keys : list of str, optional
      Which scalar or array keys to pull directly from `data`.
    """
    suffixes   = suffixes   or DEFAULT_SUFFIXES
    direct_keys = direct_keys or DIRECT_KEYS

    # 1) base metadata
    metadata: Dict[str, Any] = {
        "stan_model_name":      stan_filename,
        "generated_by":         "culRI-Bayesian",
        "version":              version,
        "run_time":             datetime.now().isoformat(),
        "run_duration (sec)":   None,
        "temptype":             None,    # sampler may fill this
    }
    if site_name:
        metadata["SiteName"] = site_name

    # 2) direct keys: scalars or median of arrays
    for key in direct_keys:
        if key not in data:
            continue
        val = data[key]
        if isinstance(val, (np.integer, int)):
            metadata[key] = int(val)
        elif isinstance(val, (np.floating, float)):
            metadata[key] = float(val)
        elif isinstance(val, (list, np.ndarray)):
            metadata[key] = float(np.median(val))
        else:
            metadata[key] = val

    # 3) summarize any proxyObs_<suffix> arrays (also accept legacy scaledRI_<suffix>)
    for suf in suffixes:
        arr_key = f"proxyObs_{suf}"
        if arr_key not in data:
            arr_key = f"scaledRI_{suf}"  # backward compat with old data dicts
        if arr_key not in data:
            continue
        arr = np.asarray(data[arr_key], dtype=float)
        metadata.update(_summarize_array(arr_key, arr))

    # 4) summarize optional predictors if flagged
    for pred in OPTIONAL_PREDICTORS:
        use_flag = f"use_{pred}"
        if not data.get(use_flag, 0):
            continue
        for suf in suffixes:
            arr_key = f"{pred}_{suf}"
            if arr_key not in data:
                continue
            arr = np.asarray(data[arr_key], dtype=float)
            metadata.update(_summarize_array(arr_key, arr))
            metadata[use_flag] = 1
            if pred == "no3":
                cutoff = data.get("no3_cutoff", 0.0)
                if cutoff < 0:
                    raise ValueError("no3_cutoff must be ≥ 0 when using no3")
                metadata["no3_cutoff"] = float(cutoff)

    # 5) any extras
    if "calibration_suffix_used" in data:
        metadata["calibration_suffix_used"] = data["calibration_suffix_used"]
    if "posteriors_used" in data:
        metadata["posteriors_used"] = data["posteriors_used"]

    # 6) attach & return
    ds.attrs.update(metadata)
    return ds

def _summarize_array(name: str, arr: np.ndarray) -> Dict[str, Any]:
    """Return mean/std/min/max/len for an array under a given key."""
    return {
        f"{name}_mean": float(np.mean(arr)),
        f"{name}_std":  float(np.std(arr)),
        f"{name}_min":  float(np.min(arr)),
        f"{name}_max":  float(np.max(arr)),
        f"{name}_len":  int(len(arr)),
    }


# ——— prior extractor —————————————————————————————————————————————————

def extract_priors_from_stan(
    stan_path: Union[str, Path],
    data: Optional[Dict[str, float]] = None
) -> Dict[str, str]:
    """
    Parse priors from a .stan file’s model block.

    If `data` is given, symbolic args found in `data` will be substituted
    with their numeric values when formatting the prior string.
    """
    priors: Dict[str, str] = {}
    in_model = False
    path = Path(stan_path)

    with path.open() as fh:
        for line in fh:
            txt = line.strip()
            if txt.startswith("model"):
                in_model = True
                continue
            if not in_model:
                continue
            if txt.startswith("}"):
                break

            m = _PRIOR_REGEX.match(txt)
            if not m:
                continue
            param, dist, args, trunc = m.groups()
            parts = [p.strip() for p in args.split(",")]

            if data:
                # replace symbol names with numeric values if present
                resolved = [
                    f"{data[p]:.4g}" if p in data and isinstance(data[p], (int, float)) else p
                    for p in parts
                ]
            else:
                resolved = parts

            prior = f"{dist}({', '.join(resolved)})"
            if trunc:
                prior += trunc.strip()
            priors[param] = prior

    return priors

def infer_use_flags_from_attrs(attrs: Dict[str, Any]) -> Dict[str, bool]:
    """
    Infer optional predictor use_flags (like use_gdgt23ratio, use_no3)
    from the attributes of a posterior xarray.Dataset.

    Returns a dict like:
    {"gdgt23ratio": True, "no3": False}
    """
    return {
        pred: attrs.get(f"use_{pred}", 0) == 1
        for pred in OPTIONAL_PREDICTORS
        if f"use_{pred}" in attrs
    }