# TEXAS/stan/invT.py

from typing import Union, Optional, Dict, Sequence, List, Any, Literal
import numpy as np
import xarray as xr
from pathlib import Path
import json
import time
import tracemalloc

from .compiler import StanCompiler
from .sampler import StanSampler
from .metadata import extract_priors_from_stan
from .utils import patch_optional_predictors
from ..data.builder import build_invT_inputData, InvTConfig
from TEXAS.stan.io import (
    load_posterior,
    _save_invT_posterior,
    _save_invT_draws,
    _save_invT_results,
)
from TEXAS.utils.system_info import simple_memory_check, get_system_info, suggest_stan_sampling_kwargs
from TEXAS.utils.paths import STAN_MODELS_DIR


# Instantiate once
_default_compiler = StanCompiler()
_default_sampler = StanSampler(_default_compiler)

def _attach_invT_metadata(
    ds: xr.Dataset,
    data: dict,
    stan_file: str,
    site_name: Optional[str] = None,
    model_type: Optional[str] = None
) -> xr.Dataset:
    """Attaches essential metadata to the posterior dataset."""
    stan_model_name = stan_file.replace('.stan', '') if stan_file.endswith('.stan') else stan_file
    ds.attrs["stan_model_name"] = stan_model_name
    ds.attrs.setdefault("temptype", "unknown")
    ds.attrs["use_gdgt23ratio"] = int(bool(data.get("use_gdgt23ratio", 0)))
    ds.attrs["use_no3"] = int(bool(data.get("use_no3", 0)))
    if ds.attrs["use_no3"] == 1:
        ds.attrs["no3_cutoff"] = float(data.get("no3_cutoff", 0.0))
    else:
        ds.attrs["no3_cutoff"] = 0.0
    ds.attrs["SiteName"] = site_name or "unknown_site"

    if model_type:
        ds.attrs["model_type"] = model_type
    else:
        ds.attrs["model_type"] = "direct" if "marginal" in stan_file else "ensemble"

    ds.attrs["use_marginal"] = 1 if ds.attrs["model_type"] == "direct" else 0

    return ds

# -------------------------------------------------------------------------
def get_invT_posterior(
    proxyObs: Union[np.ndarray, List[float]] = None,
    prior_mu_t: Union[np.ndarray, float] = None,
    prior_sigma_t: float = None,
    *,
    proxy_name: Optional[str] = None,
    scaledRI: Union[np.ndarray, List[float]] = None,  # deprecated alias
    fwd_posterior_name: Optional[str] = None,
    site_name: Optional[str] = None,
    temptype: Optional[str] = None,
    predictors: Optional[Dict[str, np.ndarray]] = None,
    config: Optional[InvTConfig] = None,
    save: bool = True,
    save_draws: bool = False,
    filename_tag: Optional[Union[str, Sequence[str]]] = None,
    cache_dir: Optional[Union[str, Path]] = None,
    chains: Optional[int] = None,
    iter_warmup: Optional[int] = None,
    iter_sampling: Optional[int] = None,
    seed: Optional[int] = None,
    use_opencl: bool = False,
    threads_per_chain: Optional[int] = None,
    stan_model_path: Optional[Union[str, Path]] = None,
    model_type: Literal["direct", "ensemble"] = "direct",
    constraint_type: Literal["unconstrained", "hard_constraint", "truncated_prior", "reparameterized", "soft"] = "unconstrained",
    min_temp: Optional[float] = None,
    fwd_posterior: Optional[xr.Dataset] = None,
    fwd_cache_dir: Optional[Union[str, Path]] = None,
) -> xr.Dataset:
    """
    Run the inverse-T model and return the posterior Dataset with metadata.

    Args:
        model_type:
            - "direct": Use direct sampling models (more efficient, supports threading)
            - "ensemble": Use traditional ensemble models
        cache_dir: Where invT RESULTS are written.
        fwd_cache_dir: Where fwd_posterior_name is READ from. Defaults to the
            standard forward posterior cache. The two are separate directories —
            passing cache_dir does not change where the forward posterior is
            looked up.
    """
    # Backward-compat: accept deprecated scaledRI kwarg
    if scaledRI is not None and proxyObs is None:
        import warnings
        warnings.warn(
            "The 'scaledRI' parameter is deprecated; use 'proxyObs' instead.",
            DeprecationWarning, stacklevel=2,
        )
        proxyObs = scaledRI
    if proxyObs is None:
        raise TypeError("get_invT_posterior() missing required argument: 'proxyObs'")

    tracemalloc.start()
    start_time = time.perf_counter()
    system_info = get_system_info()

    # config may be an InvTConfig, a plain dict of InvTConfig fields, or a mixed
    # dict that also contains cmdstanpy sampler keys (e.g. show_console=True).
    # Separate sampler-level keys out so they reach model.sample(), not InvTConfig.
    _SAMPLER_KEYS = {"show_console", "show_progress", "refresh", "sig_figs", "timeout"}
    _sampler_overrides: dict = {}
    if isinstance(config, dict):
        config = dict(config)  # don't mutate caller's dict
        _sampler_overrides = {k: config.pop(k) for k in _SAMPLER_KEYS if k in config}
        cfg = InvTConfig(**config) if config else InvTConfig()
    else:
        cfg = config or InvTConfig()
    predictors = predictors or {}

    # Resolve forward posterior for proxy_name validation (avoid double I/O)
    if fwd_posterior is None and fwd_posterior_name is not None:
        fwd_posterior = load_posterior(fwd_posterior_name, cache_dir=fwd_cache_dir)

    # proxy_name: inherit from forward posterior attrs, validate if both are known
    fwd_proxy_name = fwd_posterior.attrs.get("proxy_name") if fwd_posterior is not None else None
    if proxy_name is None:
        if fwd_proxy_name is not None:
            proxy_name = fwd_proxy_name  # auto-inherit
        else:
            import warnings
            warnings.warn(
                "The forward posterior has no 'proxy_name' attribute (older posterior). "
                "Regenerate the forward posterior with proxy_name= to enable proxy-type "
                "validation. Proceeding without validation.",
                UserWarning, stacklevel=2,
            )
    elif fwd_proxy_name is not None and proxy_name != fwd_proxy_name:
        raise ValueError(
            f"proxy_name mismatch: the forward posterior was built with "
            f"'{fwd_proxy_name}' but you passed '{proxy_name}'. "
            f"Make sure you are using the correct proxy observations with this calibration."
        )

    # Guard: if the forward posterior requires NO₃ but none was supplied, fail
    # fast with actionable guidance rather than silently passing zeros.
    if fwd_posterior is not None and fwd_posterior.attrs.get("use_no3", 0) == 1:
        if "no3" not in predictors:
            no3_cutoff = fwd_posterior.attrs.get("no3_cutoff", 1.0)
            raise ValueError(
                "The forward posterior uses a NO\u2083 correction (use_no3=1) "
                "but no NO\u2083 values were supplied.\n\n"
                "  Option 1 \u2014 modern WOA23 values (recommended for most sites):\n"
                "    pass  site_lat=<lat>, site_lon=<lon>, no3_dataset=ocean_prop_ds\n"
                "    \u2192 NO\u2083 is looked up from ocean_prop_ds['no3_sf2tc_avg']\n\n"
                "  Option 2 \u2014 your own per-observation values:\n"
                "    pass  no3=<array of length N>  (e.g. from ocean_prop_ds['no3_sf2tc_avg'])\n\n"
                f"  Option 3 \u2014 disable the NO\u2083 correction entirely:\n"
                f"    pass  no3={no3_cutoff * 10:.0f}  "
                f"(any value above the cutoff of {no3_cutoff} \u00b5mol/L sets the correction to zero)"
            )

    data, sampler_kwargs = build_invT_inputData(
        proxyObs=proxyObs, prior_mu_t=prior_mu_t, prior_sigma_t=prior_sigma_t,
        fwd_posterior_name=fwd_posterior_name, predictors=predictors, config=cfg,
        fwd_posterior=fwd_posterior, fwd_cache_dir=fwd_cache_dir,
    )

    if chains is not None: sampler_kwargs["chains"] = chains
    if iter_warmup is not None: sampler_kwargs["iter_warmup"] = iter_warmup
    if iter_sampling is not None: sampler_kwargs["iter_sampling"] = iter_sampling
    if seed is not None: sampler_kwargs["seed"] = seed
    sampler_kwargs.setdefault("chains", 4)
    sampler_kwargs.setdefault("iter_warmup", 500)
    sampler_kwargs.setdefault("iter_sampling", 1000)
    sampler_kwargs.update(_sampler_overrides)  # e.g. show_console, show_progress

    meta = sampler_kwargs.pop("_metadata", {})

    # Auto-select truncated_prior when min_temp is given and the user hasn't
    # explicitly chosen a different constraint type.
    if min_temp is not None and constraint_type == "unconstrained":
        constraint_type = "truncated_prior"
        print(f"🔧 Auto-selected constraint_type='truncated_prior' (min_temp={min_temp})")

    if constraint_type in ("hard_constraint", "truncated_prior"):
        if min_temp is None:
            raise ValueError(
                f"min_temp must be provided when constraint_type='{constraint_type}'. "
                "Example: min_temp=-1.8 for seawater freezing point."
            )
        data["min_temp"] = float(min_temp)
    elif min_temp is not None:
        print(f"⚠️  min_temp={min_temp} provided but constraint_type='{constraint_type}' — "
              f"min_temp will be ignored.")

    # Select the Stan file first — threading is only useful for multiv models
    # that contain reduce_sum. Applying STAN_THREADS to univ models wastes cores.
    if stan_model_path:
        stan_file = Path(stan_model_path).name
        print(f"✅ Using specified Stan file: {stan_file}")
    else:
        data = patch_optional_predictors(data)
        predictor_usage = meta.get("predictor_usage", {})
        no3ratio = meta.get("no3ratio", False)
        stan_file = _select_invT_stan_file(
            data, predictor_usage,
            threads_per_chain=threads_per_chain,
            model_type=model_type,
            constraint_type=constraint_type,
            no3ratio=no3ratio,
            bounded=meta.get("is_bounded", False))
        if not (STAN_MODELS_DIR / stan_file).exists():
            available = sorted(p.name for p in STAN_MODELS_DIR.glob("invT_*t0shift*.stan"))
            raise FileNotFoundError(
                f"Selected invT model '{stan_file}' is not available in {STAN_MODELS_DIR}.\n"
                f"The T0-shift arm currently ships only the multiv/unconstrained variant "
                f"(use predictors + constraint_type='unconstrained').\n"
                f"Available t0shift models: {available or 'none'}")
        print(f"🔧 Automatically selected Stan file: {stan_file}")

    _stan_path = STAN_MODELS_DIR / stan_file
    _uses_reduce_sum = _stan_path.exists() and "reduce_sum" in _stan_path.read_text(encoding="utf-8")

    # Auto-detect CPU settings now that we know whether the model can use threads.
    _auto = suggest_stan_sampling_kwargs()
    sampler_kwargs.setdefault("parallel_chains", _auto["parallel_chains"])
    if threads_per_chain is None and "threads_per_chain" in _auto and _uses_reduce_sum:
        threads_per_chain = _auto["threads_per_chain"]
        print(
            f"⚙️  Auto CPU config: {_auto['parallel_chains']} parallel chains, "
            f"{threads_per_chain} threads/chain (reduce_sum model)"
        )
    elif threads_per_chain is None:
        print(
            f"⚙️  Auto CPU config: {_auto['parallel_chains']} parallel chains, "
            f"1 thread/chain ({'univ model — threading skipped' if not _uses_reduce_sum else 'single-threaded per chain'})"
        )

    cpp_options = {}
    if use_opencl and threads_per_chain:
        raise ValueError("Cannot use both OpenCL and threading simultaneously.")
    if use_opencl:
        cpp_options["STAN_OPENCL"] = True
        sampler_kwargs["opencl_ids"] = [0, 0]
    if threads_per_chain and _uses_reduce_sum:
        cpp_options["STAN_THREADS"] = True
        sampler_kwargs["threads_per_chain"] = threads_per_chain

    if model_type == "direct":
        N = data["N"]
        if threads_per_chain and _uses_reduce_sum:
            data["grainsize"] = 1
        else:
            data["grainsize"] = max(1, min(10, N // 4))

    print(f"| M={data.get('M')} N={data.get('N')}")

    # Stan sampling
    model = _default_compiler.get_model(stan_file, cpp_options=cpp_options)
    ds = _default_sampler.sample_from_model(model, data, **sampler_kwargs)

    # Get memory info
    memory_info = simple_memory_check()
    tracemalloc.stop()

    priors = extract_priors_from_stan(stan_path=model.stan_file, data=data)
    if priors:
        ds.attrs["priors"] = [f"{k}: {v}" for k, v in priors.items()]

    ds = _attach_invT_metadata(ds, data, stan_file, site_name=site_name)

    ds.attrs["threads_per_chain"] = threads_per_chain if threads_per_chain else 0
    ds.attrs["threading_enabled"] = bool(threads_per_chain)
    ds.attrs["opencl_enabled"] = use_opencl
    ds.attrs["model_type"] = model_type

    ds.attrs["memory_peak_mb"] = round(memory_info['peak_mb'], 2)
    ds.attrs["memory_final_mb"] = round(memory_info['current_mb'], 2)

    ds.attrs["system_os"] = system_info['system']
    ds.attrs["cpu_count_logical"] = system_info['cpu_count_logical']
    ds.attrs["cpu_count_physical"] = system_info['cpu_count_physical'] or 0
    ds.attrs["total_memory_gb"] = system_info['total_memory_gb'] or 0.0
    ds.attrs["python_version"] = system_info['python_version']
    ds.attrs["run_timestamp"] = system_info['run_timestamp']

    ds.attrs["system_info_json"] = json.dumps({
        k: v for k, v in system_info.items()
        if k not in ['system', 'cpu_count_logical', 'cpu_count_physical',
                     'total_memory_gb', 'python_version', 'run_timestamp']
    })

    if model_type == "direct" and threads_per_chain:
        ds.attrs["grainsize"] = data.get("grainsize", 0)

    # Forward-calibration provenance, carried through from build_invT_inputData.
    # The invT model name alone cannot identify the calibration (it records the
    # curve and the constraint, but not the training set or the estimator), so
    # these attrs are what let a saved reconstruction be traced to its parent.
    if meta.get("fwd_posterior_name"):
        ds.attrs["fwd_posterior_name"] = meta["fwd_posterior_name"]
    if meta.get("fwd_case"):
        ds.attrs["fwd_case"] = meta["fwd_case"]

    _name_hint = fwd_posterior_name or (fwd_posterior.attrs.get("stan_model_name", "") if fwd_posterior is not None else "")
    if temptype:
        ds.attrs["temptype"] = temptype
    elif 'thermoT' in _name_hint:
        ds.attrs["temptype"] = "thermoT"
    elif 'sst' in _name_hint.lower():
        ds.attrs["temptype"] = "SST"
    else:
        ds.attrs["temptype"] = "unknown_temptype"

    if proxy_name is not None:
        ds.attrs["proxy_name"] = proxy_name

    if save_draws:
        _save_invT_draws(ds, cache_dir=cache_dir, filename_tag=filename_tag)

    post_ds = get_invT_post_quantiles(ds)

    runtime = time.perf_counter() - start_time
    post_ds.attrs["runtime_seconds"] = runtime
    post_ds.attrs["runtime_minutes"] = runtime / 60.0

    if save:
        _save_invT_posterior(
            posterior=post_ds,
            cache_dir=cache_dir,
            overwrite=True,
            filename_tag=filename_tag,
        )
    return post_ds

# -------------------------------------------------------------------------
def _select_invT_stan_file(
    data: Dict,
    predictor_usage: Dict[str, bool],
    threads_per_chain: Optional[int] = None,
    model_type: Literal["direct", "ensemble"] = "direct",
    constraint_type: Literal["unconstrained", "hard_constraint", "truncated_prior", "reparameterized", "soft"] = "unconstrained",
    no3ratio: bool = False,
    bounded: bool = False,
) -> str:
    """
    Choose the correct Stan model file based on data structure.

    Args:
        model_type:
            - "direct": Use direct sampling models (more efficient, supports threading)
            - "ensemble": Use traditional ensemble models
        constraint_type:
            - "unconstrained": No temperature constraints
            - "hard_constraint": Hard lower bound (Jacobian-biased near boundary)
            - "truncated_prior": Truncated Normal prior via inverse-CDF; P50 unbiased
            - "reparameterized": Exponential transformation approach
            - "soft": Soft penalty for temperatures below min_temp
    """
    if "M" not in data:
        raise ValueError("Only ensemble mode is supported.")
    multiv = any(predictor_usage.values())

    base = "invT_gen_logi_fixed"
    suffix = "_multiv" if multiv else "_univ"

    if model_type == "direct":
        model_name = f"{base}{suffix}_marginal"
    elif model_type == "ensemble":
        if threads_per_chain:
            print("⚠️  Threading requires model_type='direct'. Switching to direct sampling model.")
            model_name = f"{base}{suffix}_marginal"
        else:
            model_name = f"{base}{suffix}"
    else:
        raise ValueError(f"Unknown model_type: {model_type}. Use 'direct' or 'ensemble'.")

    model_name += f"_{constraint_type}"

    if bounded:
        model_name += "_t0shift"

    if no3ratio:
        model_name += "_no3ratio"

    return f"{model_name}.stan"

# -------------------------------------------------------------------------
def get_invT_post_quantiles(
    posterior: xr.Dataset,
    quantiles: Sequence[float] = (0.01, 0.05, 0.1, 0.16, 0.25, 0.4, 0.5,
                                  0.6, 0.75, 0.84, 0.9, 0.95, 0.99),
) -> xr.Dataset:
    """
    Calculate quantiles for the posterior draws.

    Special handling for `t_est`:
    - Ensemble models: shape (chain, draw, N, M) → reduce over chain, draw, and M.
    - Marginal models: shape (chain, draw, N) → reduce over chain and draw.

    Other variables: reduce over available MCMC dims (chain, draw).
    """
    processed_vars = {}
    for var_name, data_array in posterior.data_vars.items():
        if var_name == "t_est":
            if "t_est_dim_1" in data_array.dims:   # Ensemble case
                dims_to_reduce = ["chain", "draw", "t_est_dim_1"]
            else:  # Marginal case
                dims_to_reduce = ["chain", "draw"]
            processed_vars[var_name] = data_array.quantile(quantiles, dim=dims_to_reduce)
        else:
            dims_to_reduce = [d for d in ["chain", "draw"] if d in data_array.dims]
            if dims_to_reduce:
                processed_vars[var_name] = data_array.quantile(quantiles, dim=dims_to_reduce)
            else:
                processed_vars[var_name] = data_array  # leave unchanged if no MCMC dims

    return xr.Dataset(processed_vars, attrs=posterior.attrs)

# -------------------------------------------------------------------------
def predict_temperature_from_proxyObs(
    proxyObs: Union[np.ndarray, List[float]] = None,
    prior_mu_t: Union[np.ndarray, float] = None,
    prior_sigma_t: float = None,
    fwd_posterior_name: Optional[str] = None,
    site_name: Optional[str] = None,
    temptype: Optional[str] = None,
    predictors: Optional[Dict[str, np.ndarray]] = None,
    config: Optional[InvTConfig] = None,
    chains: int = 4,
    iter_warmup: int = 500,
    iter_sampling: int = 1000,
    seed: Optional[int] = 42,
    save_results: bool = False,
    save_draws: bool = False,
    filename_tag: Optional[Union[str, Sequence[str]]] = None,
    results_path: Optional[Union[str, Path]] = None,
    cache_dir: Optional[Union[str, Path]] = None,
    use_opencl: bool = False,
    threads_per_chain: Optional[int] = None,
    stan_model_path: Optional[Union[str, Path]] = None,
    model_type: Literal["direct", "ensemble"] = "direct",
    constraint_type: Literal["unconstrained", "hard_constraint", "truncated_prior", "reparameterized", "soft"] = "unconstrained",
    min_temp: Optional[float] = None,
    fwd_posterior: Optional[xr.Dataset] = None,
    proxy_name: Optional[str] = None,
    fwd_cache_dir: Optional[Union[str, Path]] = None,
    *,
    scaledRI: Union[np.ndarray, List[float]] = None,  # deprecated alias
) -> Dict[str, Any]:
    """
    High-level wrapper to run the inverse model and get temperature percentiles.

    Args:
        model_type:
            - "direct": Use direct sampling models (more efficient, supports threading)
            - "ensemble": Use traditional ensemble models
    """
    # Backward-compat: accept deprecated scaledRI kwarg
    if scaledRI is not None and proxyObs is None:
        import warnings
        warnings.warn(
            "The 'scaledRI' parameter is deprecated; use 'proxyObs' instead.",
            DeprecationWarning, stacklevel=2,
        )
        proxyObs = scaledRI

    post_ds = get_invT_posterior(
        proxyObs=proxyObs,
        prior_mu_t=prior_mu_t,
        prior_sigma_t=prior_sigma_t,
        fwd_posterior_name=fwd_posterior_name,
        predictors=predictors,
        config=config,
        site_name=site_name,
        temptype=temptype,
        filename_tag=filename_tag,
        chains=chains,
        iter_warmup=iter_warmup,
        iter_sampling=iter_sampling,
        seed=seed,
        save=save_results,
        save_draws=save_draws,
        cache_dir=cache_dir,
        use_opencl=use_opencl,
        threads_per_chain=threads_per_chain,
        stan_model_path=stan_model_path,
        model_type=model_type,
        constraint_type=constraint_type,
        min_temp=min_temp,
        fwd_posterior=fwd_posterior,
        proxy_name=proxy_name,
        fwd_cache_dir=fwd_cache_dir,
    )

    metadata = {
        "fwd_posterior_name": fwd_posterior_name,
        "filename_tag": filename_tag,
        **post_ds.attrs,
    }

    results = {
        "proxyObs": np.asarray(proxyObs),
        "proxy_name": post_ds.attrs.get("proxy_name"),
        "metadata": metadata,
        'p1': post_ds['t_est'].sel(quantile=0.01, drop=True).values,
        'p5': post_ds['t_est'].sel(quantile=0.05, drop=True).values,
        'p10': post_ds['t_est'].sel(quantile=0.1, drop=True).values,
        'p16': post_ds['t_est'].sel(quantile=0.16, drop=True).values,
        'p25': post_ds['t_est'].sel(quantile=0.25, drop=True).values,
        'p50': post_ds['t_est'].sel(quantile=0.50, drop=True).values,
        'p75': post_ds['t_est'].sel(quantile=0.75, drop=True).values,
        'p84': post_ds['t_est'].sel(quantile=0.84, drop=True).values,
        'p90': post_ds['t_est'].sel(quantile=0.90, drop=True).values,
        'p95': post_ds['t_est'].sel(quantile=0.95, drop=True).values,
        'p99': post_ds['t_est'].sel(quantile=0.99, drop=True).values,
    }

    if save_results:
        if results_path is None and cache_dir is not None:
            from pathlib import Path as _Path
            from ..stan.io import _generate_filename_base
            _out = _Path(cache_dir)
            _out.mkdir(parents=True, exist_ok=True)
            _base = _generate_filename_base(metadata, filename_tag)
            results_path = _out / f"{_base}.npz"
        _save_invT_results(results, results_path)

    return results
