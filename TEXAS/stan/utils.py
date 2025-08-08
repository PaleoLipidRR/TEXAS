# stan/utils.py
import os
import warnings
import numpy as np
import re
from typing import Dict, Any
from TEXAS.constants import OPTIONAL_PREDICTORS
from pathlib import Path

def check_tbb_env():
    if "TBB_CXX_TYPE" not in os.environ:
        warnings.warn(
            "TBB_CXX_TYPE not set. Stan model compilation may fail. "
            "Run `export TBB_CXX_TYPE=gcc` before launching."
        )

def infer_use_flags_from_attrs(attrs: Dict[str, Any]) -> Dict[str, bool]:
    """
    Infer which optional predictors (e.g. gdgt23ratio, no3) were used,
    based on dataset.attrs. Returns a dict like:
    {'gdgt23ratio': True, 'no3': False}
    """
    return {
        key: bool(attrs.get(f"use_{key}", 0))
        for key in OPTIONAL_PREDICTORS
    }


def infer_optional_predictor_usage(data: dict) -> dict:
    """
    Inspect keys in a Stan data dict and infer which optional predictors
    are present AND actively used (e.g., gdgt23ratio, no3). 
    Returns a dict of use_* flags.
    """
    flags = {}
    # Only set flags to True if the use_* key exists and is truthy
    for pred in OPTIONAL_PREDICTORS:
        use_key = f"use_{pred}"
        if use_key in data and data[use_key]:
            flags[use_key] = True
        else:
            flags[use_key] = False
    return flags

# ─── OPTIONAL PREDICTOR PATCH ───────────────────────────────────────────────

def patch_optional_predictors(data: dict) -> dict:
    """
    Ensure gdgt23ratio and no3 exist with shape (N,) and corresponding use_* flags,
    and (for ensemble mode) ensure beta arrays exist with shape (M,).
    """
    N = int(data["N"])
    M = int(data["M"]) if "M" in data else None

    for name in ("gdgt23ratio", "no3"):
        use_key = f"use_{name}"
        beta_name = f"beta0_{name}"

        # ---- values (always 1D length N) ----
        v = data.get(name, None)
        if v is None or (np.isscalar(v) or np.asarray(v).ndim == 0):
            data[name] = np.zeros(N, dtype=float)
        else:
            arr = np.asarray(v, dtype=float)
            if arr.shape != (N,):
                raise ValueError(f"{name} must have shape ({N},), got {arr.shape}")
            data[name] = arr

        # ---- flags ----
        # If caller explicitly set a flag, respect it; otherwise infer from non‑zero input.
        if use_key not in data:
            data[use_key] = int(np.any(data[name] != 0))

        # ---- betas ----
        if M is not None:
            # Ensemble mode: sampler expects a draw-by-draw vector for beta if used
            if beta_name not in data:
                data[beta_name] = np.zeros(M, dtype=float)

        else:
            # Mean‑prior mode: sampler expects mu_* and std_* if used
            mu_key, sd_key = f"mu_{beta_name}", f"std_{beta_name}"
            data.setdefault(mu_key, 0.0)
            data.setdefault(sd_key, 0.1)

    # If NO3 is used, ensure a positive cutoff is present
    if int(data.get("use_no3", 0)) == 1:
        cutoff = data.get("no3_cutoff", None)
        if cutoff is None or float(cutoff) <= 0:
            data["no3_cutoff"] = 0  # sensible default

    return data

def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]

