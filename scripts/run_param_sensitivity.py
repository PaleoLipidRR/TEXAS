#!/usr/bin/env python
"""
Headless runner for the SI_code2a sensitivity tests.

The notebook (``notebooks/manuscripts/SI_code2a_model_param_sensitivity_test.ipynb``)
exists to explain the analysis and draw the figures. This script exists to do
the sampling, unattended, so nobody has to babysit a kernel for an hour. Both
write and read the same files, so whichever runs first, the other picks up the
results and skips the work.

    # everything, in the background, surviving logout
    nohup python scripts/run_param_sensitivity.py all > sensitivity.log 2>&1 &
    tail -f sensitivity.log

    # just one part, or one model
    python scripts/run_param_sensitivity.py part1
    python scripts/run_param_sensitivity.py part1 --models bnd
    python scripts/run_param_sensitivity.py part2 --proxies SRI04 SRI05
    python scripts/run_param_sensitivity.py part3 --invt-m 300 500

Three parts. Part 1 sweeps the forward calibration's warmup/sampling budget,
Part 2 refits it under three crenarchaeol ring conventions, and Part 3 sweeps
the INVERSE model's budget and its number of marginalised calibration draws M.
Part 3 is separate rather than an extension of Part 1 because the two models
have unrelated geometry -- see the INVT_BUDGETS comment -- and because only the
inverse side can be scored against a known temperature.

    # a 12-minute smoke run that exercises every path
    python scripts/run_param_sensitivity.py all --quick

    # what would run, without running it
    python scripts/run_param_sensitivity.py all --dry-run

Resumable: every completed fit is appended to
``data/revision1/groupA/param_sensitivity/mcmc_budget_grid.csv`` immediately, and
anything already there is skipped. Kill it at any point and re-run; you lose at
most the fit that was in flight.

Single-instance: a lockfile prevents two runs at once. Concurrent Stan jobs on
this machine share one compiled-binary directory (``~/.texas/stan_cache``) and
saturate the same cores -- that roughly triples per-iteration cost and has
killed a notebook kernel outright with no Python traceback. Use ``--force-lock``
only if you are certain no other run is live.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


# ── repo location ───────────────────────────────────────────────────────────
def find_repo_root(start: Path | None = None) -> Path:
    if Path("/home/micromamba/app").exists():
        return Path("/home/micromamba/app")
    p = (start or Path(__file__).resolve().parent).resolve()
    for cand in (p, *p.parents):
        if (cand / "pyproject.toml").exists() and (cand / "src" / "TEXAS").exists():
            return cand
    raise FileNotFoundError(f"could not locate the TEXAS repo root above {p}")


REPO = find_repo_root()
RESULTS_DIR = REPO / "data" / "revision1" / "groupA" / "param_sensitivity"
SPREADSHEETS = REPO / "data" / "spreadsheets"
COMPILATION = "ds_gridded_screened_global_compilation_finalized.csv"

GRID_CSV = RESULTS_DIR / "mcmc_budget_grid.csv"
PARAM_CSV = RESULTS_DIR / "mcmc_budget_params.csv"
RECO_JSON = RESULTS_DIR / "recommended_budget.json"
INVT_CSV = RESULTS_DIR / "invt_budget_grid.csv"
INVT_SITES_CSV = RESULTS_DIR / "invt_budget_sites.csv"
INVT_RECO_JSON = RESULTS_DIR / "recommended_invt_budget.json"
LOCKFILE = RESULTS_DIR / ".run.lock"


# ── configuration — keep in step with the notebook's config cell ────────────
CHAINS = 4
SEED = 42

WARMUPS = [100, 200, 300, 400, 500]
MULTIPLIERS = [1.0, 1.5, 2.0, 2.5, 3.0]
REF_WARMUP, REF_SAMPLING = 1000, 4000
DEFAULT_WARMUP, DEFAULT_SAMPLING = 1000, 1000

GRID_MODELS = [
    ("univ", "gen_logi_fixed_hier_crtp_univ_priorApprox"),
    ("eiv",  "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv"),
    ("bnd",  "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT"),
]

PROXIES = {
    "SRI03": dict(column="scaledRI_cren3", cren_rings=3),
    "SRI04": dict(column="scaledRI",       cren_rings=4),
    "SRI05": dict(column="scaledRI_cren5", cren_rings=5),
}
PRODUCTION_PROXY = "SRI03"

TEMPTYPE = "SST"
NO3_CUTOFF = 1.0
SD_PROXYOBS_MODE = "scaled_constant"
SD_PROXYOBS_BASE = 0.03

# Both slope conventions: the parent model names them beta_*, boundedT gamma_*.
# Listing both keeps the accuracy check honest for either model.
CORE_PARAMS = ["t0_crtp", "k_crtp", "b_crtp", "v_crtp", "sigma_proxyObs_crtp",
               "beta_G23_crtp", "beta_NO3_crtp",
               "gamma_G23_crtp", "gamma_NO3_crtp"]

CRITERIA = dict(max_rhat=1.01, min_ess_bulk=400.0, pct_divergent=0.0, max_z_mean=0.1)

# ── Part 3: the inverse model's budget, and M ───────────────────────────────
# Part 1's answer does not transfer here. The forward EIV model is hierarchical
# with ~3000 correlated latent variables, which is why its warmup binds. The
# invT model declares one parameter block -- vector[N] t_est -- and its target
# is a sum of per-sample terms with no coupling between samples, so the
# posterior factorises into N independent 1-D posteriors and a diagonal metric
# is exact rather than approximate. Different question, different answer.
#
# What binds instead is M, the number of calibration draws marginalised in the
# log_sum_exp (~5.8% Monte Carlo error at 300, ~4.5% at 500 per builder.py),
# and saturation -- where RI approaches the upper asymptote the likelihood goes
# flat in T and t_est is prior-dominated. Neither is fixed by more iterations.
#
# The two budgets already in use are both undocumented magic numbers: 500/1000
# (build_invT_inputData's sampler_kwargs default) and 300/1000 (the commented
# coretop cell in SI_code2). Both are swept here so the choice stops being one.
INVT_BUDGETS = [(300, 500), (300, 1000), (500, 1000), (1000, 1000)]
INVT_M_VALUES = [300, 500]
INVT_N_SITES = 200
INVT_N_BINS = 10
INVT_PRIOR_SIGMA_T = 10.0
INVT_CONSTRAINT = "unconstrained"

# Drift is measured against the richest cell (largest budget x largest M) and
# is in degrees, because that is the unit the reader cares about: 0.1 degC is
# far below the reconstruction's own uncertainty, so a cell that lands within
# it is indistinguishable in any figure we publish.
#
# But a fixed threshold alone is not a usable gate, as the first run of this
# sweep showed: worst-site drift came in at 0.24-0.45 degC and did NOT fall as
# the budget rose -- 1000/1000 with M=300 drifted further from the reference
# than 300/1000 with M=500 did. That is not a budget effect. It is Monte Carlo
# jitter in the single reference realisation, and it puts a floor under every
# comparison. A threshold below that floor can never be met at any cost, and
# would read as "the sampler failed" when nothing failed.
#
# So the floor is measured rather than assumed: one extra cell repeats the
# reference configuration at a different seed, and the gate is whichever is
# larger, the threshold or the seed-to-seed drift. Comparing a cell against the
# reference is only meaningful once you know what two identical runs differ by.
INVT_REPLICATE_SEED = 43
INVT_CRITERIA = dict(max_rhat=1.01, min_ess_bulk=400.0, pct_divergent=0.0,
                     max_p50_drift=0.1)

# Measured 2026-08-12, N=1513, 4 parallel chains, uncontended. Used only for
# the ETA; being wrong costs nothing but a misleading progress line.
SEC_PER_ITER = {"univ": 0.013, "eiv": 0.132, "bnd": 0.132}

_KEY = ["model", "iter_warmup", "iter_sampling"]


# ── logging ─────────────────────────────────────────────────────────────────
def log(msg: str = "") -> None:
    if msg:
        print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)
    else:
        print(flush=True)


# ── single-instance lock ────────────────────────────────────────────────────
def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False            # no such process
    except PermissionError:
        return True             # exists, just owned by another user
    except OSError:
        return False
    return True


@contextmanager
def single_instance(force: bool = False):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stolen = None               # a LIVE holder's lock that --force-lock overrode
    if LOCKFILE.exists():
        raw = LOCKFILE.read_text()
        try:
            info = json.loads(raw)
            pid, started = int(info["pid"]), info.get("started", "?")
        except Exception:
            pid, started = -1, "?"
        if pid > 0 and _pid_alive(pid):
            if not force:
                sys.exit(
                    f"Another run appears to be live (pid {pid}, started {started}).\n"
                    f"Two concurrent Stan jobs share ~/.texas/stan_cache and the same\n"
                    f"cores; running both roughly triples per-iteration cost and can\n"
                    f"kill a notebook kernel with no traceback.\n"
                    f"If you are certain it is dead:  rm {LOCKFILE}\n"
                    f"or re-run with --force-lock."
                )
            # --force-lock is for clearing a stale lock. Used against a run that
            # is genuinely alive, it must not leave that run unprotected once we
            # exit, so remember its lock and hand it back.
            stolen = raw
            log(f"--force-lock: overriding a LIVE run (pid {pid}); "
                "its lock is restored when this one exits")
        elif pid > 0:
            log(f"clearing stale lock from dead pid {pid}")
    LOCKFILE.write_text(json.dumps(
        {"pid": os.getpid(), "started": f"{datetime.now():%Y-%m-%d %H:%M:%S}"}))
    try:
        yield
    finally:
        if stolen is not None:
            LOCKFILE.write_text(stolen)
        else:
            # Only clear a lock that is still ours: if someone else forced their
            # way in while we ran, the file now describes them, not us.
            try:
                mine = int(json.loads(LOCKFILE.read_text())["pid"]) == os.getpid()
            except Exception:
                mine = True     # unreadable or gone: nothing worth preserving
            if mine:
                LOCKFILE.unlink(missing_ok=True)


# ── graceful shutdown ───────────────────────────────────────────────────────
class _Stop:
    """Finish the fit in flight, write it, then exit -- never mid-write."""

    def __init__(self):
        self.requested = False

    def install(self):
        # Registered only by the CLI. Importing this module into a notebook must
        # not steal SIGINT from the kernel, or "interrupt" stops working there.
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._handle)

    def _handle(self, signum, frame):
        if self.requested:
            log("second signal — exiting immediately")
            sys.exit(130)
        self.requested = True
        log(f"signal {signum} received — finishing the current fit, then stopping "
            "(signal again to abort now)")


STOP = _Stop()


# ── data ────────────────────────────────────────────────────────────────────
_DATA_CACHE: dict = {}


def load_frames():
    if "frames" in _DATA_CACHE:
        return _DATA_CACHE["frames"]
    df = pd.read_csv(SPREADSHEETS / COMPILATION, low_memory=False)
    coretop = (df[df["datatype"] == "coretop"]
               .dropna(subset=["no3_sf2tc_avg", "SST"])
               .reset_index(drop=True))
    _DATA_CACHE["frames"] = (df, coretop)
    return df, coretop


def sd_proxyobs_for(cren_rings: int, n: int) -> np.ndarray:
    if SD_PROXYOBS_MODE == "scaled_constant":
        val = SD_PROXYOBS_BASE
    elif SD_PROXYOBS_MODE == "ri_constant":
        val = SD_PROXYOBS_BASE * 3.0 / cren_rings
    else:
        raise ValueError(f"unknown SD_PROXYOBS_MODE {SD_PROXYOBS_MODE!r}")
    return np.full(n, val)


def build_part1_data(model_key: str, proxy_col: str | None = None):
    from TEXAS.data import build_fwd_data
    from TEXAS.stan.io import load_posterior

    _, coretop = load_frames()
    proxy_col = proxy_col or PROXIES[PRODUCTION_PROXY]["column"]
    culmeso_post = load_posterior(f"gen_logi_fixed_culmeso_cultureT_{proxy_col}")

    if model_key == "univ":
        reg = coretop[["SST", proxy_col]].dropna()
        return build_fwd_data(t_crtp=reg["SST"].values,
                              proxy_crtp=reg[proxy_col].values,
                              culmeso_posterior=culmeso_post), len(reg)

    # The parent EIV model and boundedT declare byte-identical Stan data
    # blocks (16 keys), so one builder serves both.
    if model_key in ("eiv", "bnd"):
        reg = coretop[["SST", proxy_col, "gdgt23ratio", "gdgt23ratio_se",
                       "no3_sf2tc_avg", "thermoNO3_se"]].dropna()
        thermal = load_posterior(
            f"gen_logi_fixed_hier_crtp_univ_priorApprox_{TEMPTYPE}_{proxy_col}")
        return build_fwd_data(
            t_crtp              = reg["SST"].values,
            proxy_crtp          = reg[proxy_col].values,
            gdgt23ratio_crtp    = reg["gdgt23ratio"].values,
            sd_gdgt23ratio_crtp = reg["gdgt23ratio_se"].values,
            no3_crtp            = reg["no3_sf2tc_avg"].values,
            sd_no3_crtp         = reg["thermoNO3_se"].values,
            R2_thermal          = float(thermal["R2_full"].mean()),
            culmeso_posterior   = culmeso_post,
            no3_cutoff          = NO3_CUTOFF,
        ), len(reg)

    raise ValueError(f"unknown model key {model_key!r}; expected one of "
                     f"{sorted({k for k, _ in GRID_MODELS})}")


# ── Part 1 ──────────────────────────────────────────────────────────────────
_COMPILER = None


def _compiler():
    global _COMPILER
    if _COMPILER is None:
        from TEXAS.stan.compiler import StanCompiler
        _COMPILER = StanCompiler()
    return _COMPILER


def run_budget_case(model_key, stan_file, data, iter_warmup, iter_sampling,
                    seed=SEED, chains=CHAINS):
    """Sample once at a budget; return (metrics row, per-parameter frame)."""
    from TEXAS.diagnostics import summarize_sampler_diagnostics

    model = _compiler().get_model(stan_file)

    t_start = time.time()
    fit = model.sample(data=data, chains=chains, parallel_chains=chains,
                       iter_warmup=iter_warmup, iter_sampling=iter_sampling,
                       seed=seed, show_progress=False, show_console=False)
    wall = time.time() - t_start

    summary = fit.summary()
    diag = summarize_sampler_diagnostics(fit)
    params = summary.drop(index=[i for i in summary.index if i == "lp__"],
                          errors="ignore")

    row = {
        "model": model_key, "stan_file": stan_file,
        "iter_warmup": iter_warmup, "iter_sampling": iter_sampling,
        "multiplier": iter_sampling / iter_warmup, "chains": chains,
        "total_draws": chains * iter_sampling,
        "total_iters": chains * (iter_warmup + iter_sampling),
        "wall_sec": wall,
        "max_rhat": float(params["R_hat"].max()),
        "n_rhat_gt_101": int((params["R_hat"] > 1.01).sum()),
        "n_rhat_gt_105": int((params["R_hat"] > 1.05).sum()),
        "worst_rhat_param": str(params["R_hat"].idxmax()),
        "lp_rhat": float(summary.loc["lp__", "R_hat"]) if "lp__" in summary.index else np.nan,
        "min_ess_bulk": float(params["ESS_bulk"].min()),
        "median_ess_bulk": float(params["ESS_bulk"].median()),
        "min_ess_tail": float(params["ESS_tail"].min()) if "ESS_tail" in params else np.nan,
        "pct_divergent": diag["stan_diag_pct_divergent"],
        "pct_max_treedepth": diag["stan_diag_pct_max_treedepth"],
        "min_ebfmi": diag["stan_diag_min_ebfmi"],
    }
    row["ess_bulk_per_sec"] = row["min_ess_bulk"] / wall
    row["sec_per_1000_draws"] = 1000 * wall / row["total_draws"]

    ds = fit.draws_xr()
    par_rows = []
    for p in CORE_PARAMS:
        if p not in ds:
            continue
        v = np.asarray(ds[p].values, dtype=float).ravel()
        par_rows.append({
            "model": model_key, "iter_warmup": iter_warmup,
            "iter_sampling": iter_sampling, "param": p,
            "mean": float(v.mean()), "sd": float(v.std(ddof=1)),
            "q025": float(np.percentile(v, 2.5)),
            "q500": float(np.percentile(v, 50)),
            "q975": float(np.percentile(v, 97.5)),
            "rhat": float(summary.loc[p, "R_hat"]) if p in summary.index else np.nan,
            "ess_bulk": float(summary.loc[p, "ESS_bulk"]) if p in summary.index else np.nan,
        })
    return row, pd.DataFrame(par_rows)


def _read(path):
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _budgets(quick: bool):
    warmups = [100, 300] if quick else WARMUPS
    mults = [1.0, 2.0] if quick else MULTIPLIERS
    ref = (400, 800) if quick else (REF_WARMUP, REF_SAMPLING)
    grid = [(w, int(round(w * m))) for w in warmups for m in mults]
    extra = [ref, (DEFAULT_WARMUP, DEFAULT_SAMPLING)]
    out, seen = [], set()
    for b in grid + extra:
        if b not in seen:
            seen.add(b)
            out.append(b)
    return out, ref


def run_grid(models=None, quick=False, force=False, dry_run=False):
    models = models or [k for k, _ in GRID_MODELS]
    stan_of = dict(GRID_MODELS)
    grid_df, param_df = (pd.DataFrame(), pd.DataFrame()) if force else (
        _read(GRID_CSV), _read(PARAM_CSV))
    budgets, _ = _budgets(quick)

    todo = []
    for mk in models:
        for w, s in budgets:
            done = (not grid_df.empty and
                    ((grid_df["model"] == mk) & (grid_df["iter_warmup"] == w)
                     & (grid_df["iter_sampling"] == s)).any())
            if not done:
                todo.append((mk, stan_of[mk], w, s))

    if not todo:
        log("Part 1: everything cached, nothing to sample")
        return grid_df, param_df

    est = sum(SEC_PER_ITER.get(mk, 0.13) * (w + s) for mk, _, w, s in todo)
    log(f"Part 1: {len(todo)} fit(s) to run, estimated {timedelta(seconds=int(est))}")
    for mk in models:
        n = sum(1 for t in todo if t[0] == mk)
        if n:
            log(f"    {mk:5s} {n:3d} fit(s)  ({stan_of[mk]})")
    if dry_run:
        return grid_df, param_df

    t0 = time.time()
    for i, (mk, stan_file, w, s) in enumerate(todo, 1):
        if STOP.requested:
            log("stopping as requested; progress is saved")
            break
        if mk not in _DATA_CACHE:
            _DATA_CACHE[mk] = build_part1_data(mk)
        data, n_obs = _DATA_CACHE[mk]
        log(f"[{i}/{len(todo)}] {mk} warmup={w} sampling={s} ...")
        try:
            row, pars = run_budget_case(mk, stan_file, data, w, s)
            row["n_obs"], row["status"] = n_obs, "ok"
            log(f"          {row['wall_sec']:.0f}s  R-hat={row['max_rhat']:.4f}  "
                f"ESS={row['min_ess_bulk']:.0f}  div={row['pct_divergent']:.2f}%")
        except Exception as exc:
            log(f"          FAILED {type(exc).__name__}: {exc}")
            row = {"model": mk, "stan_file": stan_file, "iter_warmup": w,
                   "iter_sampling": s, "multiplier": s / w, "chains": CHAINS,
                   "n_obs": n_obs, "status": f"failed: {type(exc).__name__}"}
            pars = pd.DataFrame()

        grid_df = pd.concat([grid_df, pd.DataFrame([row])], ignore_index=True)
        if not pars.empty:
            param_df = pd.concat([param_df, pars], ignore_index=True)
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        grid_df.to_csv(GRID_CSV, index=False)      # write after every fit
        param_df.to_csv(PARAM_CSV, index=False)

        done_frac = i / len(todo)
        elapsed = time.time() - t0
        if done_frac:
            eta = elapsed / done_frac - elapsed
            log(f"          elapsed {timedelta(seconds=int(elapsed))}, "
                f"eta {timedelta(seconds=int(eta))}")

    return grid_df, param_df


def add_reference_deviation(param_df, quick=False):
    """z-scores and SD ratios against the long reference run, per model."""
    _, ref_budget = _budgets(quick)
    rw, rs = ref_budget
    out = []
    for model_key, sub in param_df.groupby("model"):
        ref = sub[(sub["iter_warmup"] == rw) & (sub["iter_sampling"] == rs)]
        if ref.empty:
            log(f"    no {rw}/{rs} reference for {model_key!r}; skipped")
            continue
        ref = ref.set_index("param")
        s = sub.copy()
        s["ref_mean"] = s["param"].map(ref["mean"])
        s["ref_sd"] = s["param"].map(ref["sd"])
        s["z_mean"] = (s["mean"] - s["ref_mean"]).abs() / s["ref_sd"]
        s["sd_ratio"] = s["sd"] / s["ref_sd"]
        out.append(s)
    if not out:
        raise RuntimeError(
            f"No model has a {rw}/{rs} reference run in {PARAM_CSV}. "
            "Re-run part1 (it samples the reference alongside the grid)."
        )
    return pd.concat(out, ignore_index=True)


def recommend(quick=False):
    """Merge deviations into the grid and pick the fastest adequate budget."""
    grid_df, param_df = _read(GRID_CSV), _read(PARAM_CSV)
    if grid_df.empty:
        log("no grid results yet — run part1 first")
        return {}
    param_df = add_reference_deviation(param_df, quick=quick)

    def worst(s):
        return s.idxmax() if s.notna().any() else np.nan

    dev = (param_df.groupby(_KEY)
           .agg(max_z_mean=("z_mean", "max"),
                worst_z_param=("z_mean", worst),
                max_sd_ratio_dev=("sd_ratio", lambda s: float((s - 1).abs().max())))
           .reset_index())
    dev["worst_z_param"] = dev["worst_z_param"].map(param_df["param"])
    grid_df = grid_df.drop(columns=[c for c in dev.columns if c in grid_df.columns
                                    and c not in _KEY], errors="ignore")
    grid_df = grid_df.merge(dev, on=_KEY, how="left")
    grid_df.to_csv(GRID_CSV, index=False)
    param_df.to_csv(PARAM_CSV, index=False)

    _, (rw, rs) = _budgets(quick)
    out = {}
    log("")
    log("=" * 66)
    log("RECOMMENDED BUDGETS")
    log("=" * 66)
    for mk, stan_file in GRID_MODELS:
        sub = grid_df[(grid_df["model"] == mk)
                      & (grid_df.get("status", "ok") == "ok")].copy()
        if sub.empty:
            continue
        sub = sub[~((sub["iter_warmup"] == rw) & (sub["iter_sampling"] == rs))]
        ok = sub[(sub["max_rhat"] < CRITERIA["max_rhat"])
                 & (sub["min_ess_bulk"] >= CRITERIA["min_ess_bulk"])
                 & (sub["pct_divergent"] <= CRITERIA["pct_divergent"])
                 & (sub["max_z_mean"] <= CRITERIA["max_z_mean"])]
        base = sub[(sub["iter_warmup"] == DEFAULT_WARMUP)
                   & (sub["iter_sampling"] == DEFAULT_SAMPLING)]
        base_sec = float(base["wall_sec"].iloc[0]) if not base.empty else np.nan
        log("")
        log(f"{stan_file}")
        if ok.empty:
            log("  no swept cell meets all four criteria")
            continue
        best = ok.sort_values("wall_sec").iloc[0]
        speed = base_sec / best["wall_sec"] if np.isfinite(base_sec) else np.nan
        out[mk] = {
            "stan_file": stan_file,
            "iter_warmup": int(best["iter_warmup"]),
            "iter_sampling": int(best["iter_sampling"]),
            "wall_sec": float(best["wall_sec"]),
            "baseline_wall_sec": base_sec,
            "speedup_vs_1000_1000": float(speed),
            "max_rhat": float(best["max_rhat"]),
            "min_ess_bulk": float(best["min_ess_bulk"]),
            "pct_divergent": float(best["pct_divergent"]),
            "max_z_mean": float(best["max_z_mean"]),
        }
        log(f"  warmup/sampling : {int(best['iter_warmup'])}/{int(best['iter_sampling'])}")
        log(f"  max R-hat       : {best['max_rhat']:.4f}   "
            f"min ESS: {best['min_ess_bulk']:.0f}")
        log(f"  divergences     : {best['pct_divergent']:.2f}%   "
            f"max |z|: {best['max_z_mean']:.3f}")
        log(f"  wall            : {best['wall_sec']:.0f}s vs {base_sec:.0f}s "
            f"at 1000/1000 ({speed:.2f}x faster)")

    RECO_JSON.write_text(json.dumps(
        {"criteria": CRITERIA, "quick_run": quick, "recommendations": out}, indent=2))
    log("")
    log(f"wrote {RECO_JSON}")
    return out


# ── Part 2 ──────────────────────────────────────────────────────────────────
def fit_proxy_stack(label, cfg, iter_warmup, iter_sampling, force=False):
    """Run (or reuse) the three calibration stages for one ring convention."""
    from TEXAS.data import build_fwd_data
    from TEXAS.stan.io import load_posterior, save_posterior
    from TEXAS.stan.sampler import get_posterior

    full, coretop = load_frames()
    col = cfg["column"]
    kw = dict(iter_warmup=iter_warmup, iter_sampling=iter_sampling,
              chains=CHAINS, seed=SEED)
    out = {}

    name1 = f"gen_logi_fixed_culmeso_cultureT_{col}"
    try:
        if force:
            raise FileNotFoundError
        out["culmeso"] = load_posterior(name1)
        log(f"    [{label}] stage 1 culmeso — cached")
    except Exception:
        log(f"    [{label}] stage 1 culmeso — sampling")
        cul = full[full["datatype"] == "culture"].dropna(subset=[col, "SST"])
        meso = full[full["datatype"] == "mesocosm"].dropna(subset=[col, "SST"])
        data = build_fwd_data(t_cul=cul["SST"].values, proxy_cul=cul[col].values,
                              t_meso=meso["SST"].values, proxy_meso=meso[col].values)
        post, _ = get_posterior(data=data, stan_file="gen_logi_fixed_culmeso",
                                temptype="cultureT", proxy_name=col, **kw)
        save_posterior(post, filename_suffix="")
        out["culmeso"] = post

    name2 = f"gen_logi_fixed_hier_crtp_univ_priorApprox_{TEMPTYPE}_{col}"
    try:
        if force:
            raise FileNotFoundError
        out["univ"] = load_posterior(name2)
        log(f"    [{label}] stage 2 univ — cached")
    except Exception:
        log(f"    [{label}] stage 2 univ — sampling")
        reg = coretop[["SST", col]].dropna()
        data = build_fwd_data(t_crtp=reg["SST"].values, proxy_crtp=reg[col].values,
                              culmeso_posterior=out["culmeso"])
        post, _ = get_posterior(
            data=data, stan_file="gen_logi_fixed_hier_crtp_univ_priorApprox",
            temptype=TEMPTYPE, proxy_name=col, **kw)
        save_posterior(post, filename_suffix="")
        out["univ"] = post

    R2_thermal = float(out["univ"]["R2_full"].mean())

    name3 = (f"gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_{TEMPTYPE}"
             f"_gdgt23ratio_no3_{NO3_CUTOFF}_{col}")
    try:
        if force:
            raise FileNotFoundError
        out["eiv"] = load_posterior(name3)
        log(f"    [{label}] stage 3 eiv — cached")
    except Exception:
        log(f"    [{label}] stage 3 eiv — sampling")
        reg = coretop[["SST", col, "gdgt23ratio", "gdgt23ratio_se",
                       "no3_sf2tc_avg", "thermoNO3_se"]].dropna()
        data = build_fwd_data(
            t_crtp              = reg["SST"].values,
            proxy_crtp          = reg[col].values,
            gdgt23ratio_crtp    = reg["gdgt23ratio"].values,
            sd_gdgt23ratio_crtp = reg["gdgt23ratio_se"].values,
            no3_crtp            = reg["no3_sf2tc_avg"].values,
            sd_no3_crtp         = reg["thermoNO3_se"].values,
            sd_proxyObs         = sd_proxyobs_for(cfg["cren_rings"], len(reg)),
            R2_thermal          = R2_thermal,
            culmeso_posterior   = out["culmeso"],
            no3_cutoff          = NO3_CUTOFF,
        )
        post, _ = get_posterior(
            data=data,
            stan_file="gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv",
            temptype=TEMPTYPE, proxy_name=col, **kw)
        save_posterior(post, filename_suffix="")
        out["eiv"] = post

    out["R2_thermal"] = R2_thermal
    return out


def run_part2(proxies=None, quick=False, force=False, dry_run=False):
    labels = proxies or list(PROXIES)
    w, s = (300, 300) if quick else (DEFAULT_WARMUP, DEFAULT_SAMPLING)
    log(f"Part 2: {len(labels)} proxy definition(s) at {w}/{s}: {', '.join(labels)}")
    if dry_run:
        return {}
    posteriors = {}
    for label in labels:
        if STOP.requested:
            log("stopping as requested; completed proxies are saved")
            break
        log(f"  {label} ({PROXIES[label]['column']}, "
            f"cren={PROXIES[label]['cren_rings']} rings)")
        posteriors[label] = fit_proxy_stack(label, PROXIES[label], w, s, force=force)
    return posteriors


# ── Part 3 ──────────────────────────────────────────────────────────────────
def invt_subset(coretop, proxy_col, n=INVT_N_SITES, n_bins=INVT_N_BINS,
                seed=SEED):
    """
    A stress-test subset of coretop sites, spread evenly over the proxy RANGE.

    Not a random sample, deliberately. Because the invT posterior factorises
    across samples, N is a cost knob and not a difficulty knob -- 200 sites and
    1513 sites have identical per-sample geometry. What matters is therefore the
    per-sample worst case, and a random draw is dominated by mid-range
    temperatures where the logistic is steep and t_est is sharply identified.
    The hard samples sit near the upper asymptote, where the curve flattens, the
    likelihood goes nearly flat in T, and the posterior turns prior-dominated
    and heavy-tailed -- which is also the regime the warm paleo sites live in.

    Equal-width bins over the observed proxy range with an equal quota per
    non-empty bin gives the sparse tails representation proportional to range
    rather than to density. That makes this a stress set, not a validation set:
    error statistics over it are not population statistics for the compilation.
    """
    rng = np.random.default_rng(seed)
    x = coretop[proxy_col].to_numpy(dtype=float)
    edges = np.linspace(np.nanmin(x), np.nanmax(x), n_bins + 1)
    edges[-1] = np.nextafter(edges[-1], np.inf)   # make the top edge inclusive
    which = np.digitize(x, edges) - 1

    pools = [np.flatnonzero(which == b) for b in range(n_bins)]
    pools = [p for p in pools if p.size]
    if not pools:
        raise RuntimeError(f"no usable {proxy_col} values to subset")

    # Quota per bin, with whatever a sparse bin cannot supply redistributed
    # across the bins that still have sites left.
    picked: list[np.ndarray] = []
    remaining, live = n, list(pools)
    while remaining > 0 and live:
        quota = max(1, remaining // len(live))
        still = []
        for pool in live:
            if remaining <= 0:
                break
            take = min(quota, pool.size, remaining)
            sel = rng.choice(pool, size=take, replace=False)
            picked.append(sel)
            remaining -= take
            left = np.setdiff1d(pool, sel, assume_unique=False)
            if left.size:
                still.append(left)
        live = still

    idx = np.sort(np.concatenate(picked))
    return coretop.iloc[idx].reset_index(drop=True)


def run_invt_case(fwd_name, subset, proxy_col, iter_warmup, iter_sampling, M,
                  seed=SEED, chains=CHAINS):
    """One invT fit over the subset; returns (metrics row, per-site frame)."""
    from TEXAS.data.builder import InvTConfig
    from TEXAS.stan.invT import predict_temperature_from_proxyObs

    truth = subset["SST"].to_numpy(dtype=float)

    # A CONSTANT prior mean, not the measured SST. The commented coretop cell in
    # SI_code2 passes prior_mu_t = df["SST"], i.e. the very quantity being
    # reconstructed; with prior_sigma_t = 10 that is weak, but it still centres
    # every prior on the answer, which both flatters the error statistics and
    # makes the geometry easier than any real paleo run. One climatological
    # guess for the whole set is what a paleo reconstruction actually has.
    prior_mu = float(np.mean(truth))

    predictors = {}
    if "gdgt23ratio" in fwd_name:
        predictors["gdgt23ratio"] = subset["gdgt23ratio"].to_numpy(dtype=float)
    if "no3" in fwd_name:
        predictors["no3"] = subset["no3_sf2tc_avg"].to_numpy(dtype=float)

    t_start = time.time()
    res = predict_temperature_from_proxyObs(
        proxyObs           = subset[proxy_col].to_numpy(dtype=float),
        prior_mu_t         = np.full(len(subset), prior_mu),
        prior_sigma_t      = INVT_PRIOR_SIGMA_T,
        fwd_posterior_name = fwd_name,
        site_name          = f"budgettest_n{len(subset)}",
        temptype           = TEMPTYPE,
        proxy_name         = proxy_col,
        predictors         = predictors or None,
        config             = InvTConfig(n_draws=M),
        chains             = chains,
        iter_warmup        = iter_warmup,
        iter_sampling      = iter_sampling,
        seed               = seed,
        constraint_type    = INVT_CONSTRAINT,
        save_results       = False,   # a tuning run is not a reconstruction
    )
    wall = time.time() - t_start

    meta = res["metadata"]
    p50, p16, p84 = res["p50"], res["p16"], res["p84"]
    p05, p95 = res["p5"], res["p95"]
    err = p50 - truth

    row = {
        "fwd_posterior": fwd_name,
        "iter_warmup": iter_warmup, "iter_sampling": iter_sampling, "M": M,
        "seed": seed, "chains": chains, "n_sites": len(subset),
        "wall_sec": wall,
        "max_rhat": meta.get("stan_diag_max_rhat", np.nan),
        "min_ess_bulk": meta.get("stan_diag_min_ess_bulk", np.nan),
        "pct_divergent": meta.get("stan_diag_pct_divergent", np.nan),
        "pct_max_treedepth": meta.get("stan_diag_pct_max_treedepth", np.nan),
        # Accuracy against the measured SST. In-sample -- these sites trained
        # the forward calibration -- so this is a tuning diagnostic, never a
        # validation statistic.
        "bias_degC": float(np.mean(err)),
        "mae_degC": float(np.mean(np.abs(err))),
        "rmse_degC": float(np.sqrt(np.mean(err ** 2))),
        "coverage68": float(np.mean((truth >= p16) & (truth <= p84))),
        "coverage90": float(np.mean((truth >= p05) & (truth <= p95))),
        "mean_ci68_width": float(np.mean(p84 - p16)),
    }
    sites = pd.DataFrame({
        "iter_warmup": iter_warmup, "iter_sampling": iter_sampling, "M": M,
        "seed": seed, "site_row": np.arange(len(subset)),
        "proxy": subset[proxy_col].to_numpy(dtype=float),
        "sst_measured": truth, "p16": p16, "p50": p50, "p84": p84,
    })
    return row, sites


_INVT_KEY = ["iter_warmup", "iter_sampling", "M", "seed"]


def _invt_fwd_name():
    """The calibration Part 3 tunes against: the production forward posterior."""
    col = PROXIES[PRODUCTION_PROXY]["column"]
    return (f"gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_{TEMPTYPE}"
            f"_gdgt23ratio_no3_{NO3_CUTOFF}_{col}")


def run_part3(quick=False, force=False, dry_run=False, m_values=None):
    from TEXAS.stan.io import load_posterior

    budgets = [(300, 300), (500, 500)] if quick else INVT_BUDGETS
    m_values = m_values or ([100, 200] if quick else INVT_M_VALUES)
    n_sites = 40 if quick else INVT_N_SITES

    grid_df, site_df = (pd.DataFrame(), pd.DataFrame()) if force else (
        _read(INVT_CSV), _read(INVT_SITES_CSV))

    cells = [(w, s, m, SEED) for w, s in budgets for m in m_values]
    # The replicate: the reference configuration again at a different seed. It
    # is what turns "this cell drifts 0.3 degC from the reference" into a
    # statement about the budget rather than about the reference's own noise.
    rw, rs = max(budgets)
    cells.append((rw, rs, max(m_values), INVT_REPLICATE_SEED))

    def _done(w, s, m, sd):
        if grid_df.empty:
            return False
        seeds = (grid_df["seed"] if "seed" in grid_df.columns
                 else pd.Series(SEED, index=grid_df.index))
        return bool(((grid_df["iter_warmup"] == w)
                     & (grid_df["iter_sampling"] == s)
                     & (grid_df["M"] == m) & (seeds == sd)).any())

    todo = [c for c in cells if not _done(*c)]

    log(f"Part 3: {len(todo)} invT fit(s) to run "
        f"({len(budgets)} budget(s) x {len(m_values)} M value(s) "
        f"+ 1 seed replicate, n={n_sites} coretop sites)")
    if not todo:
        log("Part 3: everything cached, nothing to sample")
        return grid_df, site_df
    if dry_run:
        for w, s, m, sd in todo:
            tag = "  <- seed replicate" if sd != SEED else ""
            log(f"    warmup={w} sampling={s} M={m} seed={sd}{tag}")
        return grid_df, site_df

    fwd_name = _invt_fwd_name()
    # Fail here rather than 200 sites into a fit: Part 3 tunes against the
    # calibration Part 2 writes, so running it first is a sequencing error.
    try:
        load_posterior(fwd_name)
    except Exception as exc:
        raise RuntimeError(
            f"forward posterior {fwd_name!r} not found ({exc}). Part 3 tunes "
            "the inverse model against the production calibration, so Part 2 "
            "must have run first."
        ) from None

    _, coretop = load_frames()
    needed = ["SST", PROXIES[PRODUCTION_PROXY]["column"], "gdgt23ratio",
              "no3_sf2tc_avg"]
    pool = coretop[needed].dropna().reset_index(drop=True)
    subset = invt_subset(pool, PROXIES[PRODUCTION_PROXY]["column"], n=n_sites)
    log(f"    subset: {len(subset)} sites, "
        f"SST {subset['SST'].min():.1f}-{subset['SST'].max():.1f} degC, "
        f"proxy {subset.iloc[:, 1].min():.3f}-{subset.iloc[:, 1].max():.3f}")

    for i, (w, s, m, sd) in enumerate(todo, 1):
        if STOP.requested:
            log("stopping as requested; progress is saved")
            break
        tag = "  (seed replicate)" if sd != SEED else ""
        log(f"[{i}/{len(todo)}] invT warmup={w} sampling={s} M={m} "
            f"seed={sd}{tag} ...")
        try:
            row, sites = run_invt_case(
                fwd_name, subset, PROXIES[PRODUCTION_PROXY]["column"], w, s, m,
                seed=sd)
            row["status"] = "ok"
            log(f"          {row['wall_sec']:.0f}s  R-hat={row['max_rhat']:.4f}  "
                f"ESS={row['min_ess_bulk']:.0f}  RMSE={row['rmse_degC']:.2f}degC  "
                f"cov68={row['coverage68']:.2f}")
        except Exception as exc:
            log(f"          FAILED {type(exc).__name__}: {exc}")
            row = {"fwd_posterior": fwd_name, "iter_warmup": w,
                   "iter_sampling": s, "M": m, "seed": sd, "chains": CHAINS,
                   "n_sites": len(subset),
                   "status": f"failed: {type(exc).__name__}"}
            sites = pd.DataFrame()

        grid_df = pd.concat([grid_df, pd.DataFrame([row])], ignore_index=True)
        if not sites.empty:
            site_df = pd.concat([site_df, sites], ignore_index=True)
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        grid_df.to_csv(INVT_CSV, index=False)      # write after every fit
        site_df.to_csv(INVT_SITES_CSV, index=False)

    return grid_df, site_df


def recommend_invt():
    """Cheapest invT cell that converges AND is indistinguishable from the richest."""
    grid_df, site_df = _read(INVT_CSV), _read(INVT_SITES_CSV)
    if grid_df.empty:
        raise RuntimeError(f"no Part 3 results in {INVT_CSV}")
    ok = grid_df[grid_df.get("status", "ok") == "ok"].copy()
    if ok.empty:
        raise RuntimeError("every Part 3 cell failed")

    if "seed" not in ok.columns:
        ok["seed"] = SEED
    # Reference = richest cell at the primary seed. Drift is per-site so a cell
    # cannot hide a warm-end error inside a flattering mean.
    primary = ok[ok["seed"] == SEED]
    ref = primary.sort_values(["iter_warmup", "iter_sampling", "M"]).iloc[-1]
    ref_key = (int(ref["iter_warmup"]), int(ref["iter_sampling"]),
               int(ref["M"]), int(ref["seed"]))
    drift = {}
    if not site_df.empty:
        if "seed" not in site_df.columns:
            site_df["seed"] = SEED
        keyed = {k: g.set_index("site_row")["p50"]
                 for k, g in site_df.groupby(_INVT_KEY)}
        base = keyed.get(ref_key)
        for k, series in keyed.items():
            if base is None:
                break
            common = series.index.intersection(base.index)
            drift[k] = float((series[common] - base[common]).abs().max())
    ok["max_p50_drift"] = [
        drift.get((int(r.iter_warmup), int(r.iter_sampling), int(r.M),
                   int(r.seed)), np.nan)
        for r in ok.itertuples()]
    ok.to_csv(INVT_CSV, index=False)

    # The seed replicate: same configuration as the reference, different seed.
    # Its drift is what two identical runs differ by, so no cell can be asked
    # to beat it -- that would be demanding the sampler be more reproducible
    # than it is with itself.
    rep = ok[(ok["seed"] != SEED)
             & (ok["iter_warmup"] == ref_key[0])
             & (ok["iter_sampling"] == ref_key[1]) & (ok["M"] == ref_key[2])]
    floor = float(rep["max_p50_drift"].max()) if not rep.empty else np.nan
    drift_gate = INVT_CRITERIA["max_p50_drift"]
    if np.isfinite(floor):
        drift_gate = max(drift_gate, floor)

    log("")
    log("=" * 66)
    log("RECOMMENDED invT BUDGET")
    log("=" * 66)
    log(f"reference cell: warmup={ref_key[0]} sampling={ref_key[1]} "
        f"M={ref_key[2]} seed={ref_key[3]}")
    if np.isfinite(floor):
        log(f"seed-to-seed floor: {floor:.3f} degC (same config, seed "
            f"{int(rep['seed'].iloc[0])}) -> drift gate {drift_gate:.3f} degC")
    else:
        log(f"no seed replicate present; drift gate is the fixed "
            f"{drift_gate:.3f} degC and may sit below the noise floor")

    candidates = ok[ok["seed"] == SEED]      # never recommend the replicate
    passing = candidates[
        (candidates["max_rhat"] < INVT_CRITERIA["max_rhat"])
        & (candidates["min_ess_bulk"] >= INVT_CRITERIA["min_ess_bulk"])
        & (candidates["pct_divergent"] <= INVT_CRITERIA["pct_divergent"])
        & (candidates["max_p50_drift"].fillna(np.inf) <= drift_gate)]
    if passing.empty:
        log("  no swept cell meets all four criteria")
        out = {}
    else:
        best = passing.sort_values("wall_sec").iloc[0]
        out = {
            "iter_warmup": int(best["iter_warmup"]),
            "iter_sampling": int(best["iter_sampling"]),
            "M": int(best["M"]),
            "wall_sec": float(best["wall_sec"]),
            "reference_cell": {"iter_warmup": ref_key[0],
                               "iter_sampling": ref_key[1], "M": ref_key[2]},
            "seed_to_seed_floor_degC": floor,
            "drift_gate_degC": drift_gate,
            "speedup_vs_reference": float(ref["wall_sec"] / best["wall_sec"]),
            "max_rhat": float(best["max_rhat"]),
            "min_ess_bulk": float(best["min_ess_bulk"]),
            "max_p50_drift_degC": float(best["max_p50_drift"]),
            "rmse_degC": float(best["rmse_degC"]),
            "coverage68": float(best["coverage68"]),
            "n_sites": int(best["n_sites"]),
        }
        log(f"  warmup/sampling : {out['iter_warmup']}/{out['iter_sampling']}")
        log(f"  M               : {out['M']}")
        log(f"  max R-hat       : {out['max_rhat']:.4f}   "
            f"min ESS: {out['min_ess_bulk']:.0f}")
        log(f"  worst p50 drift : {out['max_p50_drift_degC']:.3f} degC vs reference")
        log(f"  RMSE / cov68    : {out['rmse_degC']:.2f} degC / {out['coverage68']:.2f}")
        log(f"  wall            : {out['wall_sec']:.0f}s vs {ref['wall_sec']:.0f}s "
            f"({out['speedup_vs_reference']:.2f}x faster)")

    INVT_RECO_JSON.write_text(json.dumps(
        {"criteria": INVT_CRITERIA, "in_sample": True,
         "seed_to_seed_floor_degC": floor, "drift_gate_degC": drift_gate,
         "prior": {"mu": "constant, subset mean SST",
                   "sigma_t": INVT_PRIOR_SIGMA_T},
         "recommendation": out}, indent=2))
    log("")
    log(f"wrote {INVT_RECO_JSON}")
    return out


# ── CLI ─────────────────────────────────────────────────────────────────────
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Headless runner for the SI_code2a sensitivity tests.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="nohup python scripts/run_param_sensitivity.py all "
               "> sensitivity.log 2>&1 &")
    ap.add_argument("stage",
                    choices=["part1", "part2", "part3", "all", "recommend"],
                    help="which stage to run")
    ap.add_argument("--models", nargs="+", choices=[k for k, _ in GRID_MODELS],
                    help="Part 1 models (default: all)")
    ap.add_argument("--proxies", nargs="+", choices=list(PROXIES),
                    help="Part 2 ring conventions (default: all)")
    ap.add_argument("--invt-m", nargs="+", type=int, metavar="M",
                    help="Part 3 calibration-draw counts (default: "
                         f"{' '.join(map(str, INVT_M_VALUES))})")
    ap.add_argument("--quick", action="store_true",
                    help="small grid and short chains; NOT publishable")
    ap.add_argument("--force", action="store_true",
                    help="ignore cached results and resample")
    ap.add_argument("--force-lock", action="store_true",
                    help="run even if another instance holds the lock")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would run, then exit")
    args = ap.parse_args(argv)

    STOP.install()
    log(f"repo    : {REPO}")
    log(f"results : {RESULTS_DIR}")
    if args.quick:
        log("QUICK mode — results are a smoke test, not publishable")

    # A dry run samples nothing, so it must not need -- or take -- the lock:
    # asking "what would run?" while a run is in flight is the most natural
    # thing to want, and it was rejected.
    lock = (nullcontext() if args.dry_run
            else single_instance(force=args.force_lock))
    with lock:
        t0 = time.time()
        if args.stage in ("part1", "all"):
            run_grid(models=args.models, quick=args.quick, force=args.force,
                     dry_run=args.dry_run)
            if not args.dry_run and not STOP.requested:
                try:
                    recommend(quick=args.quick)
                except RuntimeError as exc:
                    log(f"recommendation skipped: {exc}")
        if args.stage == "recommend":
            recommend(quick=args.quick)
            try:
                recommend_invt()
            except RuntimeError as exc:
                log(f"invT recommendation skipped: {exc}")
        if args.stage in ("part2", "all") and not STOP.requested:
            run_part2(proxies=args.proxies, quick=args.quick, force=args.force,
                      dry_run=args.dry_run)
        # Part 3 runs last in "all" on purpose: it tunes the inverse model
        # against the forward posterior Part 2 writes.
        if args.stage in ("part3", "all") and not STOP.requested:
            run_part3(quick=args.quick, force=args.force,
                      dry_run=args.dry_run, m_values=args.invt_m)
            if not args.dry_run and not STOP.requested:
                try:
                    recommend_invt()
                except RuntimeError as exc:
                    log(f"invT recommendation skipped: {exc}")
        log("")
        log(f"done in {timedelta(seconds=int(time.time() - t0))}")
        if not args.dry_run:
            log("Open the notebook and run the figure cells; the compute cells "
                "will find everything cached.")


if __name__ == "__main__":
    main()
