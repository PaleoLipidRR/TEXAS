# TEXAS/stan/utils.py
from __future__ import annotations

import numpy as np

# Removed 2026-08-12, all four unreferenced by any caller in the package, the
# SI notebooks, the scripts or the app:
#
#   check_tbb_env                   warned when TBB_CXX_TYPE was unset. The
#                                   failure it guarded is handled properly now
#                                   -- _windows_compile_path() fixes the
#                                   toolchain up front and sample_from_model()
#                                   recovers from the exit-127 mismatch.
#   infer_optional_predictor_usage  superseded by auto_detect_predictors() in
#                                   stan/sampler.py, which infers the same
#                                   flags plus validation and legacy-key
#                                   translation.
#   infer_use_flags_from_attrs      existed HERE and in stan/metadata.py under
#                                   one name with different behaviour: this
#                                   copy returned False for an absent use_*
#                                   key, the other omitted the key entirely.
#                                   Both were dead, so the divergence was a
#                                   trap for whoever wired one up next rather
#                                   than a live bug. Live code reads the attrs
#                                   directly (ensemble/detection.py).

def patch_optional_predictors(data: dict) -> dict:
    """
    Ensure gdgt23ratio and no3 arrays/flags/betas exist with correct shapes.
    - Handles both single-group ("N") and multi-group keys ("N_crtp", etc.)
    - NaNs → 0.0
    - Creates group-level use_* flags and also UNSUFFIXED use_* flags expected by some Stan models
    - If any use_no3*=1 and no cutoff given, defaults to 0.0 (change to raise if you prefer strict)
    """
    out = dict(data)
    N_keys = [k for k in out if k == "N" or k.startswith("N_")]
    # Track whether ANY group uses each predictor to set unsuffixed flags later
    any_used = {"gdgt23ratio": False, "no3": False}

    for N_key in N_keys:
        N = int(out[N_key])
        suffix = "" if N_key == "N" else N_key[1:]  # "", "_crtp", "_cul", ...

        for name in ("gdgt23ratio", "no3"):
            arr_key = f"{name}{suffix}"
            use_key = f"use_{name}{suffix}"

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

            # Group-level use flag
            if use_key not in out:
                out[use_key] = int(np.any(arr != 0.0))
            else:
                out[use_key] = int(bool(out[use_key]))

            # Remember if ANY group uses this predictor
            any_used[name] = any_used[name] or bool(out[use_key])

            # NOTE: this used to also seed "beta0_<name><suffix>" containers
            # (or mu_/std_ variants). Nothing consumed them: no .stan file in
            # stan_models/ mentions beta0 at all, and the coefficient vectors
            # the invT models actually declare are named beta_G23 / beta_NO3
            # (gamma_G23 / gamma_NO3 under bounded-T) and are supplied by
            # build_invT_inputData, not here. The names also predate the
            # beta0_* -> beta_G23 rename. Dropped 2026-08-12: seeding a
            # differently-named zero vector could only ever mask a real missing
            # coefficient by looking like it had been handled.

        # Group-level NO3 cutoff handling (only if that group uses no3)
        use_no3_key = f"use_no3{suffix}"
        cutoff_key = f"no3_cutoff{suffix}"
        if int(out.get(use_no3_key, 0)) == 1:
            if cutoff_key not in out:
                out[cutoff_key] = 0.0  # switch to raise if you need positive cutoffs

    # ── UNSUFFIXED flags for models that expect them ──────────────────────
    for base in ("gdgt23ratio", "no3"):
        top_flag = f"use_{base}"
        if top_flag not in out:
            out[top_flag] = int(any_used[base])

    # Unsuffixed NO3 cutoff if any group (or top flag) uses no3
    if int(out.get("use_no3", 0)) == 1 and "no3_cutoff" not in out:
        out["no3_cutoff"] = 0.0  # or raise if you need explicit positive threshold

    return out
