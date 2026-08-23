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

# Declaration in the parameters block, e.g.
#   real<lower=0, upper=5>  gamma_G23_crtp;
#   vector<lower=0, upper=no3_cutoff>[N_crtp] true_no3_crtp;
_PARAM_DECL_REGEX = re.compile(
    r"^(?:real|vector|row_vector|matrix|simplex|ordered)"
    r"\s*(?:<([^>]*)>)?"        # optional <lower=…, upper=…>
    r"\s*(?:\[[^\]]*\])?"       # optional dimensions
    r"\s*(\w+)\s*;"
)
_BOUND_REGEX = re.compile(r"\b(lower|upper)\s*=\s*([^,>]+)")

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
      Deprecated and no longer written. Accepted so existing callers keep
      working; read ``texas_version`` instead, which records the installed
      package version rather than a literal passed at the call site.
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
        # What produced the file, named as a reader would install it. It said
        # "culRI-Bayesian" until 2026-08-23 -- the project's name years before
        # it was TEXAS, carried forward on every posterior since.
        "generated_by":         "texas-psm",
        # The `version` attr is gone. It was this function's default argument,
        # "1.0.0", in all 35 cached posteriors: nothing ever set it and nothing
        # read it, so it recorded only that a default existed. `texas_version`
        # below is the real package version and the one to read.
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

    # 6) when the run happened
    #
    # This is the only record of it. Forward filenames used to carry a date
    # stamp ("..._050126_eiv.nc") and nothing else wrote the date down, so
    # dropping the stamp from the name would have lost it entirely. The attr
    # is the right home for it regardless: a date belongs to the run, not to
    # the path, and it survives a rename. Matches the ``run_timestamp`` the
    # inverse path already records, so both halves agree on the key.
    metadata.setdefault("run_timestamp", datetime.now().isoformat(timespec="seconds"))
    # The package version, recorded rather than encoded in the path. It used to
    # be the "v026" position of the case id, where a docs-only release orphaned
    # every existing name while a prior change without a release left two
    # incompatible posteriors sharing one. As an attr it is simply the truth
    # about what produced this file.
    try:
        from .. import __version__ as _texas_version
        metadata.setdefault("texas_version", str(_texas_version))
    except Exception:  # pragma: no cover - metadata unavailable
        pass

    # 7) attach & return
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

def extract_param_bounds_from_stan(
    stan_path: Union[str, Path],
    data: Optional[Dict[str, float]] = None,
) -> Dict[str, str]:
    """
    Parse ``<lower=…, upper=…>`` bounds from a .stan file's *parameters* block.

    Stan supports two ways of truncating a prior, and they are not
    interchangeable when the prior is drawn:

    * an explicit ``T[a, b]`` on the sampling statement, and
    * a bound on the declaration, which truncates *implicitly* — e.g.
      ``real<lower=0> gamma;`` with ``gamma ~ normal(0, 1);`` is a HALF-normal.

    Only the first is visible in the model block, so a prior read from there
    alone can show mass where the sampler is unable to go.  This returns the
    second, formatted as the inside of a ``T[…]`` so it can be merged in.

    If `data` is given, symbolic bounds found in `data` (e.g. ``no3_cutoff``)
    are substituted with their numeric values.

    Returns
    -------
    dict
        ``{param_name: "lo, hi"}`` — either side may be empty for a one-sided
        bound.  Unbounded parameters are omitted entirely.
    """
    bounds: Dict[str, str] = {}
    in_params = False
    path = Path(stan_path)

    with path.open(encoding="utf-8") as fh:
        for line in fh:
            txt = line.strip()
            if not in_params:
                # "parameters {" but not "transformed parameters {"
                if re.match(r"^parameters\s*\{?\s*$", txt):
                    in_params = True
                continue
            if txt.startswith("}"):
                break

            m = _PARAM_DECL_REGEX.match(txt)
            if not m:
                continue
            constraints, param = m.groups()
            if not constraints:
                continue

            found = {k: v.strip() for k, v in _BOUND_REGEX.findall(constraints)}
            if not found:
                continue

            def _resolve(v: Optional[str]) -> str:
                if v is None:
                    return ""
                if data and v in data and isinstance(data[v], (int, float)):
                    return f"{data[v]:.4g}"
                return v

            lo, hi = _resolve(found.get("lower")), _resolve(found.get("upper"))
            # A bound that stays symbolic (unresolvable) is dropped rather than
            # emitted as text no downstream parser can turn into a number.
            try:
                if lo:
                    float(lo)
                if hi:
                    float(hi)
            except ValueError:
                continue
            if lo or hi:
                bounds[param] = f"{lo}, {hi}"

    return bounds


def extract_priors_from_stan(
    stan_path: Union[str, Path],
    data: Optional[Dict[str, float]] = None,
    include_param_bounds: bool = True,
) -> Dict[str, str]:
    """
    Parse priors from a .stan file’s model block.

    If `data` is given, symbolic args found in `data` will be substituted
    with their numeric values when formatting the prior string.

    When `include_param_bounds` is True (default), declaration bounds from the
    parameters block are folded into the prior string as ``T[lo, hi]`` for any
    parameter whose sampling statement carries no explicit truncation.  Without
    this, an implicitly truncated prior — ``real<lower=0> g;`` with
    ``g ~ normal(0, 1);`` — reads back as a full normal rather than a
    half-normal.  See :func:`extract_param_bounds_from_stan`.
    """
    priors: Dict[str, str] = {}
    in_model = False
    path = Path(stan_path)
    param_bounds = (
        extract_param_bounds_from_stan(path, data) if include_param_bounds else {}
    )

    with path.open(encoding="utf-8") as fh:
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
            elif param in param_bounds:
                # Implicit truncation from the declaration — an explicit T[…]
                # on the statement always wins over it.
                prior += f" T[{param_bounds[param]}]"
            priors[param] = prior

    return priors

# infer_use_flags_from_attrs was removed here on 2026-08-12 together with the
# same-named function in stan/utils.py. Neither had a caller, and the two were
# not equivalent -- this one omitted predictors whose use_* key was absent,
# the other returned False for them -- so keeping both invited a future caller
# to import whichever came to hand and get a different answer. Live code reads
# the attrs directly; see ensemble/detection.py, which keys off attr presence
# deliberately.