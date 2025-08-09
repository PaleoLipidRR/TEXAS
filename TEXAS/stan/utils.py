# TEXAS/stan/utils.py
from __future__ import annotations

import os
import warnings
import numpy as np
from typing import Dict, Any
from TEXAS.constants import OPTIONAL_PREDICTORS

def check_tbb_env():
    if "TBB_CXX_TYPE" not in os.environ:
        warnings.warn(
            "TBB_CXX_TYPE not set. Stan model compilation may fail. "
            "Run `export TBB_CXX_TYPE=gcc` before launching."
        )

def infer_use_flags_from_attrs(attrs: Dict[str, Any]) -> Dict[str, bool]:
    """Infer which optional predictors were used from dataset.attrs."""
    return {k: bool(attrs.get(f"use_{k}", 0)) for k in OPTIONAL_PREDICTORS}

def infer_optional_predictor_usage(data: dict) -> dict:
    """Infer 'use_*' flags from a Stan data dict."""
    return {f"use_{k}": bool(data.get(f"use_{k}", 0)) for k in OPTIONAL_PREDICTORS}

def patch_optional_predictors(data: dict) -> dict:
    """
    Ensure gdgt23ratio and no3 arrays/flags/betas exist with correct shapes.
    NaNs → 0. If use_no3*=1 and no cutoff provided, default to 0.0.
    """
    out = dict(data)
    N_keys = [k for k in out if k == "N" or k.startswith("N_")]
    M = int(out["M"]) if "M" in out else None

    for N_key in N_keys:
        N = int(out[N_key])
        suffix = "" if N_key == "N" else N_key[1:]  # "", "_cul", "_meso", ...

        for name in ("gdgt23ratio", "no3"):
            arr_key = f"{name}{suffix}"
            use_key = f"use_{name}{suffix}"
            beta_key = f"beta0_{name}{suffix}"

            v = out.get(arr_key, None)
            if v is None or (np.isscalar(v) or np.asarray(v).ndim == 0):
                arr = np.zeros(N, dtype=float)
            else:
                arr = np.asarray(v, dtype=float)
                if arr.shape != (N,):
                    raise ValueError(f"{arr_key} must have shape ({N},), got {arr.shape}")
                if np.isnan(arr).any():
                    arr = np.nan_to_num(arr, nan=0.0)
            out[arr_key] = arr

            if use_key not in out:
                out[use_key] = int(np.any(arr != 0.0))
            else:
                out[use_key] = int(bool(out[use_key]))

            if M is not None:
                out.setdefault(beta_key, np.zeros(M, dtype=float))
            else:
                out.setdefault(f"mu_{beta_key}", 0.0)
                out.setdefault(f"std_{beta_key}", 0.1)

        use_no3_key = f"use_no3{suffix}"
        cutoff_key = f"no3_cutoff{suffix}"
        if int(out.get(use_no3_key, 0)) == 1:
            out[cuttoff_key] = float(out.get(cutoff_key, 0.0))

    return out
