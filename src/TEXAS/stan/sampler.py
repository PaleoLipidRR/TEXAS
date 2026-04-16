# TEXAS/stan/sampler.py (Revised 08/18/2025)

import time
import importlib.util
import numpy as np
import xarray as xr
from typing import Tuple, Optional, Dict, Any, Literal
from cmdstanpy import CmdStanModel, CmdStanMCMC
import cmdstanpy as _cmdstanpy

from .compiler import StanCompiler
from .io import save_posterior, load_posterior, save_invT_posterior
from .metadata import extract_and_update_metadata, extract_priors_from_stan
from .utils import patch_optional_predictors
from ..diagnostics import summarize_sampler_diagnostics
from ..utils.system_info import suggest_stan_sampling_kwargs



# ─── SAMPLER CLASS ─────────────────────────────────────────────────────────
class StanSampler:
    """A simple wrapper for running the Stan sampler."""
    def __init__(self, compiler: StanCompiler):
        self.compiler = compiler
        
    def sample_from_model(
        self,
        model: CmdStanModel,
        data: Dict,
        **kwargs,
    ) -> xr.Dataset:
        """Runs the sampler from a pre-compiled CmdStanModel object."""
        n_generic = (data.get("N") or
                    data.get("N_crtp") or
                    data.get("N_meso") or
                    data.get("N_cul") or "?")
        print(f"Starting Stan sampling with {n_generic} observations...")
        try:
            fit = model.sample(data=data, **kwargs)
            print("✅ Stan sampling completed successfully")
            return fit.draws_xr()
        except RuntimeError as e:
            # Exit code 127 means the compiled binary is incompatible with the
            # current runtime (e.g. TBB version mismatch between Docker image and
            # host/conda env). Recompile from source and retry once.
            if "retcodes=[127" in str(e):
                print(
                    "⚠️  Stan binary incompatible with current environment (exit 127 — "
                    "likely a shared-library version mismatch, e.g. TBB).\n"
                    "    Recompiling Stan model from source and retrying..."
                )
                _cmdstanpy.compile_stan_file(model.stan_file, force=True)
                # Evict stale entry from the compiler's in-memory cache
                model_path = str(model.stan_file)
                for key in list(self.compiler.cache.keys()):
                    if model_path in key:
                        del self.compiler.cache[key]
                fit = model.sample(data=data, **kwargs)
                print("✅ Stan sampling completed after recompilation")
                return fit.draws_xr()
            print(f"❌ Stan sampling failed: {e}")
            raise

    def sample(
        self,
        data: Dict[str, Any],
        stan_file: str,
        cpp_options: Dict = None,
        **kwargs,
    ) -> Tuple[xr.Dataset, str]:
        """
        Compiles, runs the sampler, and processes the output.
        """
        # Pop application-specific arguments that aren't for cmdstanpy
        temptype = kwargs.pop('temptype', None)
        proxy_name = kwargs.pop('proxy_name', None)
        site_name = kwargs.pop('site_name', None)
        version = kwargs.pop('version', '1.0.0')
        recompile = kwargs.pop('recompile', False)

        t0 = time.time()
        
        # Compile and sample
        model = self.compiler.get_model(
            stan_file, 
            cpp_options=cpp_options,
            force=recompile  # ← CHANGE: pass to compiler
        )
        fit = model.sample(data=data, **kwargs)
        
        duration = time.time() - t0

        # 📊 Diagnostics
        diag_str = fit.diagnose()
        diag_summary = summarize_sampler_diagnostics(fit)

        # Convert to xarray and attach all metadata
        ds = self._to_xarray(fit)
        ds = extract_and_update_metadata(ds, data, stan_file, site_name, version)
        ds.attrs["run_duration (sec)"] = round(duration, 2)
        if temptype:
            ds.attrs["temptype"] = temptype
        ds.attrs["proxy_name"] = proxy_name if proxy_name is not None else ""

        # Attach priors
        stan_path = self.compiler.resolve_stan_path(stan_file)
        priors = extract_priors_from_stan(stan_path, data)
        if priors:
            ds.attrs["priors"] = [f"{k}: {v}" for k, v in priors.items()]

        # Attach sampler diagnostics
        for key, val in diag_summary.items():
            ds.attrs[key] = val

        return ds, diag_str

    def _to_xarray(self, fit: CmdStanMCMC) -> xr.Dataset:
        """Converts a CmdStanPy Fit to an xarray.Dataset."""
        return fit.draws_xr()

# ─── Functional API (wrappers around the class) ─────────────────────────────────

def get_posterior(
    data: dict,
    stan_file: str,
    temptype: str,
    proxy_name: str,
    *,
    iter_warmup: Optional[int] = None,
    iter_sampling: Optional[int] = None,
    threads_per_chain: Optional[int] = None,
    chains: Optional[int] = None,
    parallel_chains: Optional[int] = None,
    adapt_delta: Optional[float] = None,
    max_treedepth: Optional[int] = None,
    **kwargs
) -> Tuple[xr.Dataset, str]:
    """
    Get posterior with auto-detection of predictors.
    """
    rng_seed = kwargs.setdefault("seed", 42)
    np.random.seed(rng_seed)

    # Normalize/auto-complete predictors & flags
    data = auto_detect_predictors(data)

    # Guard: reject univ model when active predictors are present
    _use_g23 = data.get("use_gdgt23ratio", 0)
    _use_no3 = data.get("use_no3", 0)
    _is_univ = "univ" in str(stan_file) and "multiv" not in str(stan_file)
    if (_use_g23 or _use_no3) and _is_univ:
        _active = []
        if _use_g23:
            _active.append("gdgt23ratio")
        if _use_no3:
            _active.append("no3")
        raise ValueError(
            f"Active predictor(s) {_active} detected in data but stan_file='{stan_file}' "
            f"is a univariate model. Use a multivariate model (e.g. replace 'univ' with "
            f"'multiv', such as 'gen_logi_fixed_hier_crtp_multiv_priorApprox') or "
            f"omit the predictor arrays from the data dict."
        )

    # Guard: ODR models require per-site SE arrays when the corresponding predictor is active
    _is_odr = "_odr" in str(stan_file) or "_werr" in str(stan_file)
    if _is_odr:
        _missing_sd = []
        if _use_g23 and "sd_gdgt23ratio_crtp" not in data:
            _missing_sd.append(
                "sd_gdgt23ratio_crtp  (SE of G₂/₃ per site — pass to build_fwd_data())"
            )
        if _use_no3 and "sd_no3_crtp" not in data:
            _missing_sd.append(
                "sd_no3_crtp  (SE of NO₃ per site in µmol/L — pass to build_fwd_data())"
            )
        if _missing_sd:
            raise ValueError(
                f"ODR model '{stan_file}' requires per-site SE arrays for active predictors, "
                f"but the following are missing from the data dict:\n"
                + "\n".join(f"  • {s}" for s in _missing_sd)
                + "\n\nProvide them via build_fwd_data(..., sd_gdgt23ratio_crtp=..., sd_no3_crtp=...)."
            )

    # Auto-detect optimal CPU settings for this machine.
    # parallel_chains: always apply (CmdStanPy already does min(chains, cpu_count)
    #   but being explicit avoids surprises).
    # threads_per_chain: only beneficial for reduce_sum model variants; the
    #   standard forward models are single-threaded per chain.
    _auto = suggest_stan_sampling_kwargs()
    _uses_reduce_sum = "reduce_sum" in str(stan_file)

    # Push explicit sampling args to CmdStanPy via kwargs
    if iter_warmup is not None:
        kwargs["iter_warmup"] = iter_warmup
    if iter_sampling is not None:
        kwargs["iter_sampling"] = iter_sampling
    if chains is not None:
        kwargs["chains"] = chains
    if parallel_chains is not None:
        kwargs["parallel_chains"] = parallel_chains
    else:
        kwargs.setdefault("parallel_chains", _auto["parallel_chains"])

    # threads_per_chain requires STAN_THREADS compilation; only auto-enable for
    # reduce_sum variants where it actually helps.
    cpp_options: Dict = {}
    if threads_per_chain is not None:
        kwargs["threads_per_chain"] = threads_per_chain
        cpp_options["STAN_THREADS"] = True
    elif _uses_reduce_sum and "threads_per_chain" in _auto:
        threads_per_chain = _auto["threads_per_chain"]
        kwargs["threads_per_chain"] = threads_per_chain
        cpp_options["STAN_THREADS"] = True
        print(
            f"⚙️  Auto CPU config: {_auto['parallel_chains']} parallel chains, "
            f"{threads_per_chain} threads/chain (reduce_sum model detected)"
        )
    else:
        print(
            f"⚙️  Auto CPU config: {_auto['parallel_chains']} parallel chains "
            f"(single-threaded per chain)"
        )

    if adapt_delta is not None:
        kwargs["adapt_delta"] = adapt_delta
    if max_treedepth is not None:
        kwargs["max_treedepth"] = max_treedepth

    _has_tqdm = importlib.util.find_spec("tqdm") is not None
    kwargs.setdefault("show_progress", _has_tqdm)
    kwargs.setdefault("show_console", not _has_tqdm)

    print(f"   proxy_name: {proxy_name}")

    compiler = StanCompiler()
    sampler = StanSampler(compiler)

    ds, diag = sampler.sample(
        data=data,
        stan_file=stan_file,
        temptype=temptype,
        proxy_name=proxy_name,
        cpp_options=cpp_options or None,
        **kwargs
    )

    return ds, diag

def find_index_with_priority(items, priorities):
    """Return the index of the first item whose string contains any priority (in order)."""
    low_items = [str(x).lower() for x in items]
    for p in priorities:
        for i, x in enumerate(low_items):
            if p in x:
                return i
    return None  # nothing matched


def _ensure_lenN_vector(enh: dict, key: str, N: int, fill: float = 0.0):
    """Guarantee enh[key] is a 1D float list of length N (coerce scalar/wrong shape to zeros)."""
    val = enh.get(key, None)
    if val is None or np.isscalar(val):
        enh[key] = [fill] * N
        return
    arr = np.asarray(val, dtype=float).ravel()
    if arr.ndim != 1 or arr.size != N:
        enh[key] = [fill] * N
    else:
        enh[key] = arr.tolist()


def auto_detect_predictors(data: dict) -> dict:
    """Smart predictor detection with data validation (suffix-prioritized)."""
    enhanced = data.copy()

    # 0) Translate legacy scaledRI_* keys → proxyObs_* for backward compatibility
    _key_map = {
        "scaledRI_":    "proxyObs_",
        "mu_scaledRI_": "mu_proxyObs_",
        "sigma_scaledRI_": "sigma_proxyObs_",
    }
    _renames = {}
    for key in list(enhanced.keys()):
        for old_prefix, new_prefix in _key_map.items():
            if key.startswith(old_prefix):
                _renames[key] = new_prefix + key[len(old_prefix):]
                break
    if _renames:
        import warnings
        warnings.warn(
            f"Data dict contains legacy key(s) {list(_renames)}. "
            "Rename scaledRI_* → proxyObs_* (e.g. scaledRI_cul → proxyObs_cul). "
            "Auto-translating for now.",
            DeprecationWarning, stacklevel=3,
        )
        for old, new in _renames.items():
            enhanced[new] = enhanced.pop(old)

    # 1) pick the N_* key using priority order
    N_keys = [k for k in enhanced.keys() if k.startswith("N_")]
    if not N_keys:
        # nothing to do
        return enhanced

    priorities = ["crtp", "culmesocore", "meso", "cul"]
    idx = find_index_with_priority(N_keys, priorities)
    chosen_key = N_keys[idx] if idx is not None else N_keys[0]

    # suffix and length
    # e.g., "N_crtp" -> "crtp"
    suffix = chosen_key.split("_", 1)[1]
    data_len = int(enhanced[chosen_key])

    # 2) if flags already set manually, respect them (but still coerce arrays if present)
    manual_use_gd = "use_gdgt23ratio" in enhanced
    manual_use_no3 = "use_no3" in enhanced

    # 3) Detect presence (case-insensitive) of any gdgt23 / no3 keys
    #    NOTE: this detects across the whole dict, not just current suffix
    gdgt23_keys = [k for k in enhanced.keys() if "gdgt23" in k.lower()]
    no3_keys    = [k for k in enhanced.keys() if "no3" in k.lower()]

    gdgt23_detected = any(
        isinstance(enhanced[k], (list, tuple, np.ndarray))
        and np.asarray(enhanced[k]).size > 0
        and not np.all(np.isnan(np.asarray(enhanced[k])))
        for k in gdgt23_keys
    )
    no3_detected = any(
        isinstance(enhanced[k], (list, tuple, np.ndarray))
        and np.asarray(enhanced[k]).size > 0
        and not np.all(np.isnan(np.asarray(enhanced[k])))
        for k in no3_keys
    )

    # 4) Ensure the *suffix-specific* arrays exist and have correct length
    gd_key = f"gdgt23ratio_{suffix}"
    no3_key = f"no3_{suffix}"

    if gd_key not in enhanced and not gdgt23_detected:
        print("No gdgt23ratio data passing for multivariate model; injecting zeros.")
    _ensure_lenN_vector(enhanced, gd_key, data_len, 0.0)

    if no3_key not in enhanced and not no3_detected:
        print("No no3 data passing for multivariate model; injecting zeros.")
    _ensure_lenN_vector(enhanced, no3_key, data_len, 0.0)

    # 5) Set flags only if not provided manually
    if not manual_use_gd:
        arr = np.asarray(enhanced.get(gd_key, []), float)
        enhanced["use_gdgt23ratio"] = int(arr.size > 0 and not (np.all(np.isnan(arr)) or np.all(arr == 0.0)))

    if not manual_use_no3:
        arr = np.asarray(enhanced.get(no3_key, []), float)
        enhanced["use_no3"] = int(arr.size > 0 and not (np.all(np.isnan(arr)) or np.all(arr == 0.0)))

    # 6) Provide a harmless default for no3_cutoff if missing
    enhanced.setdefault("no3_cutoff", 1.0)

    # 7) Logging
    sd_g23_key = f"sd_gdgt23ratio_{suffix}"
    sd_no3_key = f"sd_no3_{suffix}"
    _has_sd_g23 = sd_g23_key in enhanced
    _has_sd_no3 = sd_no3_key in enhanced

    print("🔍 Predictor auto-detection:")
    print(f"   Chosen group: {suffix} (from {chosen_key}, N={data_len})")
    print(f"   GDGT23 keys in data: {gdgt23_keys} → use_gdgt23ratio = {enhanced['use_gdgt23ratio']}"
          + (f"  [ODR: {sd_g23_key} present]" if _has_sd_g23 else ""))
    print(f"   NO3 keys in data:    {no3_keys} → use_no3 = {enhanced['use_no3']}"
          + (f"  [ODR: {sd_no3_key} present]" if _has_sd_no3 else ""))

    return enhanced

######################

def sampler_invT_posterior(
    data: dict,
    stan_file: str,
    site_name: Optional[str] = None,
    temptype: Optional[str] = None,
    model_type: Literal["direct", "ensemble"] = "direct",  # ADD: if this function uses model selection
    **kwargs
) -> Tuple[xr.Dataset, str]:
    """
    Sample from invT posterior with updated model_type parameter.
    
    Args:
        model_type: 
            - "direct": Use direct sampling models (more efficient, supports threading)
            - "ensemble": Use traditional ensemble models
    """
    rng_seed = kwargs.setdefault("seed", 42)
    np.random.seed(rng_seed)
    
    compiler = StanCompiler()
    sampler = StanSampler(compiler)
    
    return sampler.sample(
        data=data,
        stan_file=stan_file,
        site_name=site_name,
        temptype=temptype,
        model_type=model_type,  # PASS: if needed
        **kwargs
    )