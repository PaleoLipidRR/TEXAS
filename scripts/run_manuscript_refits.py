#!/usr/bin/env python
"""
Refit every manuscript case at one sampler budget, both model variants.

    nohup python scripts/run_manuscript_refits.py all > refits.log 2>&1 &
    tail -f refits.log

    python scripts/run_manuscript_refits.py forward     # the 7 calibrations
    python scripts/run_manuscript_refits.py inverse     # the 64 reconstructions
    python scripts/run_manuscript_refits.py audit       # comparability report only
    python scripts/run_manuscript_refits.py all --dry-run

The point of this script is **comparability**. The manuscript compares the
parent additive-EIV calibration against the bounded-T one, and that comparison
is only worth anything if the two arms differ in the model and in nothing else.
So both arms are held to the same budget, the same seed, the same chain count,
the same training rows, the same M, and the same paleo inputs -- and ``audit``
re-reads what was written and fails if any of that is untrue.

**Budgets.** Forward runs use 400/1000, which is not the cheapest cell for any
single model but is the cheapest that clears all four gates for *all three*
(univariate 21.8 s, parent EIV 157.7 s, bounded-T 118.5 s; see
``docs/sampler_budget.md``). Using each model's own optimum -- 400/600,
400/800, 300/900 -- would sample the two arms differently, which is a confound
in precisely the comparison being made. Inverse runs use 500/1000 with M=300.

**Ordering is forced, not stylistic.** The coretop fits need hyperpriors from
the culmeso posterior, the EIV fits additionally need R2_thermal from the
thermal-only coretop fit of the same target, and every reconstruction needs its
forward posterior. The stages run in that order and each checks its inputs
before sampling rather than an hour in.

Resumable: every completed run is appended to ``manifest.csv`` immediately and
skipped on the next pass. Kill it at any point; you lose at most the run in
flight. Filenames carry no date -- the run date is in the ``run_timestamp``
attr -- and forward refits take the next free member, so a re-run lands beside
its predecessor rather than on top of it.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


def find_repo_root(start: Path | None = None) -> Path:
    p = (start or Path(__file__).resolve().parent).resolve()
    for cand in (p, *p.parents):
        if (cand / "pyproject.toml").exists() and (cand / "src" / "TEXAS").exists():
            return cand
    raise FileNotFoundError(f"could not locate the TEXAS repo root above {p}")


REPO = find_repo_root()
SPREADSHEETS = REPO / "data" / "spreadsheets"
PUBLISHED = SPREADSHEETS / "published_data"
COMPILATION = "ds_gridded_screened_global_compilation_finalized.csv"
PHANTEX = "PhanTEX_v001_modified_032626.csv"
GIG_CSV = "PhanTEX_GIG_df.csv"

RESULTS_DIR = REPO / "data" / "revision1" / "groupA" / "manuscript_refit"
MANIFEST = RESULTS_DIR / "manifest.csv"
AUDIT_JSON = RESULTS_DIR / "comparability_audit.json"
LOCKFILE = RESULTS_DIR / ".run.lock"
# The sensitivity sweep's lock. Two Stan jobs on this box share one compiled
# binary cache and one set of cores; running both roughly triples per-iteration
# cost and has killed a kernel outright.
OTHER_LOCKS = [REPO / "data" / "revision1" / "groupA" / "param_sensitivity" / ".run.lock"]

# ── configuration — keep in step with SI03's registry ───────────────────────
CHAINS = 4
SEED = 42

FWD_WARMUP, FWD_SAMPLING = 400, 1000
INV_WARMUP, INV_SAMPLING = 500, 1000
INV_M = 300
PRIOR_SIGMA_T = 10.0

PROXY = "scaledRI_cren3"
NO3_CUTOFF = 1.0
# temptype label -> the column in the compilation that carries it
TEMPTYPES = {"SST": "SST", "thermoT": "t_sf2tc_avg"}

UNIV_STEM = "gen_logi_fixed_hier_crtp_univ_priorApprox"
CULMESO_STEM = "gen_logi_fixed_culmeso"
VARIANTS = {
    "eiv": dict(fwd="gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv",
                label="additive EIV"),
    "bnd": dict(fwd="gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT",
                label="bounded-T"),
}

GIG_SITES = ["DSDP591", "MD98-2152", "U1482", "U1510"]
GIG_SCENARIOS = [
    dict(key="Tg23r_no3", tag="no3_modern", no3="modern"),
    dict(key="Tg23r_no3_01", tag="no3_01", no3=0.1),
    dict(key="Tg23r_no3_001", tag="no3_001", no3=0.01),
]
GIG_PRIOR_MU_T = 20.0

PETM_SITES = ["ODP959", "South Dover Bridge"]
PETM_SCENARIOS = [
    dict(key="Tg23r_no3", tag="no3_10", no3=10),
    dict(key="Tg23r_no3_01", tag="no3_01", no3="column:PETM_no3_01"),
]
PETM_RENAME = {"South Dover Bridge": "SDB", "Wilson Lake": "WL"}
# The PETM body, by whichever depth scale that site is reported on. There is no
# PETM_interval column in the compilation -- SI03 derives it from these windows,
# and so does this script.
PETM_WINDOW_SAMPLEDEPTH = {"SDB": (630, 670)}
PETM_WINDOW_MBSF = {"ODP959": (802.7, 804.1)}
# site -> (prior inside the PETM interval, prior outside it), degC
PETM_PRIORS = {"ODP959": (38, 33), "SDB": (32, 28)}
PETM_TEMPTYPES = ["SST"]          # PETM analysis is SST-only in the manuscript


def log(msg: str = "") -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}" if msg else "", flush=True)


# ── single instance ────────────────────────────────────────────────────────
def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


@contextmanager
def single_instance(force: bool = False):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    for other in OTHER_LOCKS:
        if not other.exists():
            continue
        try:
            pid = int(json.loads(other.read_text())["pid"])
        except Exception:
            continue
        if _pid_alive(pid) and not force:
            sys.exit(f"The sensitivity sweep is live (pid {pid}, {other}).\n"
                     "Two Stan jobs share one binary cache and one set of cores.\n"
                     "Wait for it, or re-run with --force-lock.")
    if LOCKFILE.exists():
        try:
            info = json.loads(LOCKFILE.read_text())
            pid, started = int(info["pid"]), info.get("started", "?")
        except Exception:
            pid, started = -1, "?"
        if pid > 0 and _pid_alive(pid) and not force:
            sys.exit(f"Another refit run is live (pid {pid}, started {started}).\n"
                     f"If you are certain it is dead:  rm {LOCKFILE}")
        if pid > 0 and not _pid_alive(pid):
            log(f"clearing stale lock from dead pid {pid}")
    LOCKFILE.write_text(json.dumps(
        {"pid": os.getpid(), "started": f"{datetime.now():%Y-%m-%d %H:%M:%S}"}))
    try:
        yield
    finally:
        try:
            mine = int(json.loads(LOCKFILE.read_text())["pid"]) == os.getpid()
        except Exception:
            mine = True
        if mine:
            LOCKFILE.unlink(missing_ok=True)


class _Stop:
    """Finish the run in flight, record it, then exit -- never mid-write."""

    def __init__(self):
        self.requested = False

    def install(self):
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._handle)

    def _handle(self, signum, frame):
        if self.requested:
            log("second signal — exiting immediately")
            sys.exit(130)
        self.requested = True
        log(f"signal {signum} received — finishing the current run, then stopping")


STOP = _Stop()


# ── manifest ───────────────────────────────────────────────────────────────
def read_manifest() -> pd.DataFrame:
    return pd.read_csv(MANIFEST) if MANIFEST.exists() else pd.DataFrame()


def record(row: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df = read_manifest()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(MANIFEST, index=False)


def already_done(key: str) -> bool:
    df = read_manifest()
    if df.empty or "key" not in df:
        return False
    hit = df[(df["key"] == key) & (df.get("status", "ok") == "ok")]
    return not hit.empty


# ── data ───────────────────────────────────────────────────────────────────
_CACHE: dict = {}


def compilation() -> pd.DataFrame:
    if "compilation" not in _CACHE:
        _CACHE["compilation"] = pd.read_csv(SPREADSHEETS / COMPILATION,
                                            low_memory=False)
    return _CACHE["compilation"]


def coretop() -> pd.DataFrame:
    if "coretop" not in _CACHE:
        df = compilation()
        _CACHE["coretop"] = (df[df["datatype"] == "coretop"]
                             .dropna(subset=["no3_sf2tc_avg", "SST"])
                             .reset_index(drop=True))
    return _CACHE["coretop"]


def gig_frame() -> pd.DataFrame:
    if "gig" not in _CACHE:
        df = pd.read_csv(PUBLISHED / GIG_CSV)
        df = df.drop(columns=[c for c in df.columns if c.endswith("_x")])
        df = df.rename(columns=lambda c: c.removesuffix("_y"))
        _CACHE["gig"] = df
    return _CACHE["gig"]


def petm_frame() -> pd.DataFrame:
    """
    Rebuild SI03's PETM frame: site filter, depth windows, priors per interval.

    Replicated rather than imported because the notebook builds it inline. The
    site list, depth windows and prior values are module constants above and are
    pinned against the notebook by tests/test_manuscript_refit_config.py, so the
    two cannot drift silently.
    """
    if "petm" in _CACHE:
        return _CACHE["petm"]
    df = pd.read_csv(PUBLISHED / PHANTEX, low_memory=False)
    d = df[df["TEXRI_cren3_mahalDist_low23ratio_outliers_manual"] == False]  # noqa: E712
    d = d[d["SiteName"].isin(PETM_SITES)].reset_index(drop=True)

    # ODP959: MBSF 801-810, Frieling2018 only
    d = d[~((d["SiteName"] == "ODP959")
            & ((d["MBSF"] < 801) | (d["MBSF"] > 810)
               | (d["pubYear"] != "Frieling2018")))].reset_index(drop=True)
    # South Dover Bridge: sample depth 611-700
    d = d[~((d["SiteName"] == "South Dover Bridge")
            & ((d["SampleDepth"] < 611)
               | (d["SampleDepth"] > 700)))].reset_index(drop=True)

    d["SiteName"] = d["SiteName"].replace(PETM_RENAME)

    # Derive PETM_interval from the depth windows, as SI03 does. Vectorised
    # rather than row-looped, but the boundaries are inclusive on both ends
    # exactly as the notebook has them, so the assignment is identical.
    d["PETM_interval"] = "non-PETM"
    for site, (lo, hi) in {**PETM_WINDOW_SAMPLEDEPTH, **PETM_WINDOW_MBSF}.items():
        col = "SampleDepth" if site in PETM_WINDOW_SAMPLEDEPTH else "MBSF"
        is_site = d["SiteName"] == site
        depth = d[col]
        d.loc[is_site & (depth >= lo) & (depth <= hi), "PETM_interval"] = "PETM"
        d.loc[is_site & (depth < lo), "PETM_interval"] = "post-PETM"
        d.loc[is_site & (depth > hi), "PETM_interval"] = "pre-PETM"

    d["prior_mu_T"] = np.nan
    d["PETM_no3_01"] = 10.0
    d["PETM_no3_001"] = 10.0
    for site, (inside, outside) in PETM_PRIORS.items():
        is_site = d["SiteName"] == site
        in_petm = is_site & (d["PETM_interval"] == "PETM")
        out_petm = is_site & ~(d["PETM_interval"] == "PETM")
        d.loc[in_petm, "prior_mu_T"] = inside
        d.loc[out_petm, "prior_mu_T"] = outside
        d.loc[in_petm, "PETM_no3_01"] = 0.1
        d.loc[in_petm, "PETM_no3_001"] = 0.01

    _CACHE["petm"] = d
    return d


# ── stage 1: forward ───────────────────────────────────────────────────────
def _fwd_kwargs() -> dict:
    return dict(iter_warmup=FWD_WARMUP, iter_sampling=FWD_SAMPLING,
                chains=CHAINS, seed=SEED)


def fit_culmeso(force=False):
    from TEXAS.data import build_fwd_data
    from TEXAS.stan.io import load_posterior, save_posterior
    from TEXAS.stan.sampler import get_posterior

    key = f"fwd|culmeso|cultureT|{PROXY}"
    # Resume off the MANIFEST, not off the cache. Reusing whatever posterior
    # happens to be cached would silently mix budgets -- the cached culmeso was
    # sampled at the old one -- and, because the reused run is never recorded,
    # the audit's "one forward budget" check would pass by not looking at it.
    if not force and already_done(key):
        prior = read_manifest()
        path = prior[prior["key"] == key].iloc[-1]["path"]
        log(f"    culmeso: already refit by this runner -> {Path(path).name}")
        import xarray as xr
        return xr.open_dataset(path)
    df = compilation()
    cul = df[df["datatype"] == "culture"].dropna(subset=[PROXY, "SST"])
    meso = df[df["datatype"] == "mesocosm"].dropna(subset=[PROXY, "SST"])
    data = build_fwd_data(t_cul=cul["SST"].values, proxy_cul=cul[PROXY].values,
                          t_meso=meso["SST"].values, proxy_meso=meso[PROXY].values)
    t0 = time.time()
    post, _ = get_posterior(data=data, stan_file=CULMESO_STEM,
                            temptype="cultureT", proxy_name=PROXY, **_fwd_kwargs())
    path = save_posterior(post)
    record(dict(key=key, stage="forward", model="culmeso", variant="-",
                temptype="cultureT", site="-", scenario="-",
                iter_warmup=FWD_WARMUP, iter_sampling=FWD_SAMPLING, M="-",
                n_obs=len(cul) + len(meso), wall_sec=round(time.time() - t0, 1),
                path=str(path), status="ok"))
    return post


def fit_univ(temptype, culmeso_post, force=False):
    from TEXAS.data import build_fwd_data
    from TEXAS.stan.io import load_posterior, save_posterior
    from TEXAS.stan.sampler import get_posterior

    key = f"fwd|univ|{temptype}|{PROXY}"
    # As above: resume off the manifest so the budget this stage was actually
    # sampled at is the one recorded. R2_thermal comes from here and feeds both
    # arms, so a stale univariate fit would propagate into every EIV run.
    if not force and already_done(key):
        prior = read_manifest()
        path = prior[prior["key"] == key].iloc[-1]["path"]
        log(f"    univ {temptype}: already refit by this runner -> {Path(path).name}")
        import xarray as xr
        return xr.open_dataset(path)
    col = TEMPTYPES[temptype]
    reg = coretop()[[col, PROXY]].dropna()
    data = build_fwd_data(t_crtp=reg[col].values, proxy_crtp=reg[PROXY].values,
                          culmeso_posterior=culmeso_post)
    t0 = time.time()
    post, _ = get_posterior(data=data, stan_file=UNIV_STEM, temptype=temptype,
                            proxy_name=PROXY, **_fwd_kwargs())
    path = save_posterior(post)
    record(dict(key=key, stage="forward", model="univ", variant="-",
                temptype=temptype, site="-", scenario="-",
                iter_warmup=FWD_WARMUP, iter_sampling=FWD_SAMPLING, M="-",
                n_obs=len(reg), wall_sec=round(time.time() - t0, 1),
                path=str(path), status="ok"))
    return post


def fit_multiv(variant, temptype, culmeso_post, univ_post, force=False):
    """Both arms share this builder: identical rows, identical data dict."""
    from TEXAS.data import build_fwd_data
    from TEXAS.stan.io import save_posterior
    from TEXAS.stan.sampler import get_posterior

    key = f"fwd|{variant}|{temptype}|{PROXY}"
    if not force and already_done(key):
        log(f"    {variant} {temptype}: already in the manifest")
        return
    col = TEMPTYPES[temptype]
    reg = coretop()[[col, PROXY, "gdgt23ratio", "gdgt23ratio_se",
                     "no3_sf2tc_avg", "thermoNO3_se"]].dropna()
    r2 = float(univ_post["R2_full"].mean())
    data = build_fwd_data(
        t_crtp=reg[col].values, proxy_crtp=reg[PROXY].values,
        gdgt23ratio_crtp=reg["gdgt23ratio"].values,
        sd_gdgt23ratio_crtp=reg["gdgt23ratio_se"].values,
        no3_crtp=reg["no3_sf2tc_avg"].values,
        sd_no3_crtp=reg["thermoNO3_se"].values,
        R2_thermal=r2, culmeso_posterior=culmeso_post, no3_cutoff=NO3_CUTOFF,
    )
    t0 = time.time()
    post, _ = get_posterior(data=data, stan_file=VARIANTS[variant]["fwd"],
                            temptype=temptype, proxy_name=PROXY, **_fwd_kwargs())
    path = save_posterior(post)
    wall = round(time.time() - t0, 1)
    log(f"    {variant} {temptype}: {wall}s  R-hat="
        f"{post.attrs.get('stan_diag_max_rhat')}  -> {Path(path).parent.name}")
    record(dict(key=key, stage="forward", model=VARIANTS[variant]["fwd"],
                variant=variant, temptype=temptype, site="-", scenario="-",
                iter_warmup=FWD_WARMUP, iter_sampling=FWD_SAMPLING, M="-",
                n_obs=len(reg), wall_sec=wall, r2_thermal=r2,
                max_rhat=post.attrs.get("stan_diag_max_rhat"),
                path=str(path), status="ok"))


def run_forward(temptypes=None, force=False, dry_run=False):
    temptypes = temptypes or list(TEMPTYPES)
    n = 1 + len(temptypes) + len(VARIANTS) * len(temptypes)
    log(f"Forward: {n} calibration(s) at {FWD_WARMUP}/{FWD_SAMPLING}, "
        f"proxy={PROXY}, temptypes={temptypes}")
    if dry_run:
        log("    culmeso cultureT")
        for tt in temptypes:
            log(f"    univ {tt}")
        for tt in temptypes:
            for v in VARIANTS:
                log(f"    {v} {tt} (G23 + NO3 cutoff {NO3_CUTOFF})")
        return

    log("  stage 1 | culmeso (hyperpriors for everything below)")
    culmeso = fit_culmeso(force=force)

    univ = {}
    for tt in temptypes:
        if STOP.requested:
            return
        log(f"  stage 2 | univariate {tt} (thermal baseline, gives R2_thermal)")
        univ[tt] = fit_univ(tt, culmeso, force=force)

    for tt in temptypes:
        for v in VARIANTS:
            if STOP.requested:
                log("stopping as requested; the manifest is current")
                return
            log(f"  stage 3 | {VARIANTS[v]['label']} {tt}")
            fit_multiv(v, tt, culmeso, univ[tt], force=force)


# ── stage 2: inverse ───────────────────────────────────────────────────────
def _legacy_fwd_name(variant, temptype, univ=False):
    if univ:
        return f"{UNIV_STEM}_{temptype}_{PROXY}"
    return (f"{VARIANTS[variant]['fwd']}_{temptype}_gdgt23ratio"
            f"_no3_{NO3_CUTOFF}_{PROXY}")


def _fwd_name(variant, temptype, univ=False):
    """
    The case id of the posterior THIS RUN wrote, not a legacy name.

    Legacy names cannot be used here. ``resolve_posterior_path`` tries an exact
    flat ``<name>.nc`` first, and this cache still holds flat files with exactly
    the names above -- so a legacy name resolves to the pre-refit posterior and
    silently shadows every case directory the refit just created. The
    reconstructions would then marginalise over the old calibration while the
    manifest recorded 400/1000, which is the kind of error that survives review.

    The manifest records the exact path of each forward fit, so the case id is
    read back from there. Falls back to the legacy name only when this run has
    no forward row -- which the caller checks for separately.
    """
    key = (f"fwd|univ|{temptype}|{PROXY}" if univ
           else f"fwd|{variant}|{temptype}|{PROXY}")
    df = read_manifest()
    if not df.empty and "key" in df:
        hit = df[(df["key"] == key) & (df.get("status", "ok") == "ok")]
        if not hit.empty:
            path = Path(str(hit.iloc[-1]["path"]))
            if path.parent.name.startswith("tx."):
                return path.parent.name          # the case id, member and all
    return _legacy_fwd_name(variant, temptype, univ=univ)


def _predict(site, temptype, proxy_vals, prior_mu, predictors, tag, key,
             variant, scenario, fwd_name):
    from TEXAS.data.builder import InvTConfig
    from TEXAS.predict import predict_T_from_proxyObs

    t0 = time.time()
    # `fwd_posterior` takes the NAME here -- TEXAS.predict's wrapper accepts a
    # str or a Dataset under that one parameter, unlike stan.invT's lower-level
    # function, which has a separate fwd_posterior_name. Passing the case id as
    # a string is what routes this through resolve_posterior_path to the exact
    # member this run wrote.
    predict_T_from_proxyObs(
        proxyObs=proxy_vals, prior_mu_t=prior_mu, prior_sigma_t=PRIOR_SIGMA_T,
        fwd_posterior=fwd_name, predictors=predictors or None,
        site_name=site, temptype=temptype, proxy_name=PROXY,
        config=InvTConfig(n_draws=INV_M),
        chains=CHAINS, iter_warmup=INV_WARMUP, iter_sampling=INV_SAMPLING,
        seed=SEED, save_results=True, filename_tag=tag,
    )
    wall = round(time.time() - t0, 1)
    log(f"    {site} {temptype} {variant} {scenario}: {wall}s  n={len(proxy_vals)}")
    record(dict(key=key, stage="inverse", model=fwd_name, variant=variant,
                temptype=temptype, site=site, scenario=scenario,
                iter_warmup=INV_WARMUP, iter_sampling=INV_SAMPLING, M=INV_M,
                n_obs=len(proxy_vals), wall_sec=wall, path="-", status="ok"))


def run_inverse(temptypes=None, force=False, dry_run=False):
    from TEXAS.stan.io import load_posterior

    temptypes = temptypes or list(TEMPTYPES)
    gig, petm = gig_frame(), petm_frame()

    todo = []
    for tt in temptypes:
        for site in GIG_SITES:
            todo.append(("gig", site, tt, "univ", "thermal"))
            for v in VARIANTS:
                for sc in GIG_SCENARIOS:
                    todo.append(("gig", site, tt, v, sc["key"]))
    for tt in [t for t in temptypes if t in PETM_TEMPTYPES]:
        for site in sorted(petm["SiteName"].unique()):
            for v in VARIANTS:
                for sc in PETM_SCENARIOS:
                    todo.append(("petm", site, tt, v, sc["key"]))

    pending = [t for t in todo
               if force or not already_done("inv|" + "|".join(t))]
    log(f"Inverse: {len(todo)} reconstruction(s) at {INV_WARMUP}/{INV_SAMPLING}, "
        f"M={INV_M} — {len(pending)} pending")
    if dry_run:
        for t in pending[:12]:
            log("    " + " ".join(t))
        if len(pending) > 12:
            log(f"    ... and {len(pending) - 12} more")
        return

    # Fail before sampling, not an hour in. Every reconstruction must
    # marginalise over a posterior THIS run produced; a legacy name here would
    # resolve to the flat pre-refit file and quietly use the wrong calibration.
    missing, shadowed = [], []
    for tt in temptypes:
        for variant, univ in [(None, True)] + [(v, False) for v in VARIANTS]:
            name = _fwd_name(variant, tt, univ=univ)
            if not name.startswith("tx."):
                shadowed.append(f"{variant or 'univ'}/{tt}")
                continue
            try:
                load_posterior(name)
            except Exception:
                missing.append(name)
    if shadowed:
        raise RuntimeError(
            "no forward posterior from this run is recorded for: "
            + ", ".join(shadowed) +
            "\nWithout a case id these reconstructions would fall back to a "
            "legacy name, which resolves to the pre-refit flat file. Run the "
            "forward stage first.")
    if missing:
        raise RuntimeError(
            "these forward posteriors are absent, so the reconstructions that "
            "need them cannot run:\n  " + "\n  ".join(missing) +
            "\nRun the forward stage first.")

    for i, (dataset, site, tt, variant, scen) in enumerate(pending, 1):
        if STOP.requested:
            log("stopping as requested; the manifest is current")
            return
        key = "inv|" + "|".join((dataset, site, tt, variant, scen))
        log(f"[{i}/{len(pending)}] {dataset} {site} {tt} {variant} {scen}")
        df = gig if dataset == "gig" else petm
        g = df[df["SiteName"] == site]
        proxy_vals = g[PROXY].astype(float).tolist()

        if variant == "univ":
            _predict(site, tt, proxy_vals, GIG_PRIOR_MU_T, {}, "", key,
                     "univ", scen, _fwd_name(None, tt, univ=True))
            continue

        scenarios = GIG_SCENARIOS if dataset == "gig" else PETM_SCENARIOS
        sc = next(s for s in scenarios if s["key"] == scen)
        if isinstance(sc["no3"], str) and sc["no3"].startswith("column:"):
            no3 = g[sc["no3"].split(":", 1)[1]].values
        elif sc["no3"] == "modern":
            no3 = g["no3"].values if "no3" in g else g["no3_sf2tc_avg"].values
        else:
            no3 = sc["no3"]
        prior = (GIG_PRIOR_MU_T if dataset == "gig"
                 else g["prior_mu_T"].values)
        _predict(site, tt, proxy_vals, prior,
                 {"gdgt23ratio": g["gdgt23ratio"].values, "no3": no3},
                 sc["tag"], key, variant, scen, _fwd_name(variant, tt))


# ── stage 3: audit ─────────────────────────────────────────────────────────
def audit() -> dict:
    """
    Re-read what was written and check the two arms are actually comparable.

    A comparison of two models is only worth something if the model is the only
    thing that differs. This checks that claim against the files rather than
    trusting that the loop above did what it says.
    """
    from TEXAS.stan.io import load_posterior

    report: dict = {"checks": [], "ok": True}

    def check(name, ok, detail=""):
        report["checks"].append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok:
            report["ok"] = False

    df = read_manifest()
    check("manifest exists", not df.empty, f"{len(df)} rows")
    if df.empty:
        return report

    fwd = df[df["stage"] == "forward"]
    inv = df[df["stage"] == "inverse"]

    # Every forward stage must be present, or "one budget" is a claim about
    # whichever subset happened to be recorded. culmeso and the univariate fits
    # are the ones most likely to be silently reused from an older budget --
    # they are cheap, they already exist in the cache, and R2_thermal from the
    # univariate fit feeds both arms.
    models = set(fwd["model"])
    check("culmeso refit by this runner", "culmeso" in models,
          f"forward models recorded: {sorted(models)}")
    expected_univ = {tt for tt in TEMPTYPES
                     if tt in set(fwd[fwd["model"] == "univ"]["temptype"])}
    check("univariate refit for every target",
          expected_univ == set(fwd[fwd["variant"].isin(VARIANTS)]["temptype"]),
          f"univariate: {sorted(expected_univ)}, "
          f"multivariate: {sorted(set(fwd[fwd['variant'].isin(VARIANTS)]['temptype']))}")

    check("one forward budget",
          fwd["iter_warmup"].nunique() <= 1 and fwd["iter_sampling"].nunique() <= 1,
          f"warmups={sorted(fwd['iter_warmup'].unique())}, "
          f"samplings={sorted(fwd['iter_sampling'].unique())}")
    if not inv.empty:
        check("one inverse budget",
              inv["iter_warmup"].nunique() <= 1 and inv["M"].nunique() <= 1,
              f"warmups={sorted(inv['iter_warmup'].unique())}, "
              f"M={sorted(inv['M'].unique())}")

    # Both arms present for every target, on the same training rows.
    for tt in sorted(set(fwd[fwd["variant"].isin(VARIANTS)]["temptype"])):
        rows = fwd[(fwd["temptype"] == tt) & (fwd["variant"].isin(VARIANTS))]
        check(f"both arms fitted for {tt}",
              set(rows["variant"]) == set(VARIANTS),
              f"have {sorted(set(rows['variant']))}")
        check(f"identical training rows for {tt}",
              rows["n_obs"].nunique() <= 1,
              f"n_obs={sorted(rows['n_obs'].unique())}")
        check(f"identical R2_thermal for {tt}",
              "r2_thermal" not in rows or rows["r2_thermal"].nunique() <= 1,
              f"r2={sorted(rows['r2_thermal'].dropna().unique())}"
              if "r2_thermal" in rows else "")

    # Every reconstruction has a counterpart in the other arm.
    if not inv.empty:
        pairs = inv[inv["variant"].isin(VARIANTS)]
        grouped = pairs.groupby(["site", "temptype", "scenario"])["variant"].nunique()
        unpaired = grouped[grouped < len(VARIANTS)]
        check("every reconstruction is paired across arms", unpaired.empty,
              f"{len(unpaired)} unpaired: {list(unpaired.index)[:6]}")

    # Convergence of what was actually written.
    fails = []
    for tt in sorted(set(fwd["temptype"])):
        for v in VARIANTS:
            try:
                ds = load_posterior(_fwd_name(v, tt))
            except Exception:
                continue
            if ds.attrs.get("stan_diag_rhat_status") == "FAIL":
                fails.append(f"{v}/{tt} max_rhat={ds.attrs.get('stan_diag_max_rhat')}")
    check("no forward posterior fails the strict R-hat gate", not fails,
          "; ".join(fails) + " (check the calibration-parameter R-hat before "
          "treating this as a problem — the EIV models' latents dominate)"
          if fails else "")

    # Every reconstruction must name a case id this run produced. A legacy name
    # here means it marginalised over the pre-refit flat file instead.
    if not inv.empty and "model" in inv:
        legacy = sorted({m for m in inv["model"].astype(str)
                         if not m.startswith("tx.")})
        check("reconstructions used this run's calibrations", not legacy,
              f"{len(legacy)} used a legacy name: {legacy[:3]}")

    # Dates must not be back in filenames.
    import re
    stamped = [p for p in df.get("path", pd.Series(dtype=str)).astype(str)
               if re.search(r"\d{6}", Path(p).name)]
    check("no date stamps in filenames", not stamped, f"{len(stamped)} stamped")

    # The case ids this run produced, ready to paste into a notebook.
    #
    # This is what makes the case id usable as the canonical identity. Loading
    # by legacy name cannot address these posteriors at all: the cache still
    # holds flat files with exactly those names, and an exact flat hit is the
    # first thing resolution tries, so a legacy name silently returns the
    # pre-refit posterior. The flat files stay -- SI_code3, the original
    # submission, reads them -- so the way forward is to name the new ones
    # explicitly rather than to delete the old ones.
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    case_ids = {}
    for r in fwd.itertuples():
        path = Path(str(r.path))
        if path.parent.name.startswith("tx."):
            label = (f"{r.model}|{r.temptype}" if r.variant == "-"
                     else f"{r.variant}|{r.temptype}")
            case_ids[label] = path.parent.name
    report["case_ids"] = case_ids
    (RESULTS_DIR / "case_ids.json").write_text(
        json.dumps(case_ids, indent=2) + "\n")

    AUDIT_JSON.write_text(json.dumps(report, indent=2) + "\n")

    log("")
    log("=" * 66)
    log("COMPARABILITY AUDIT")
    log("=" * 66)
    for c in report["checks"]:
        log(f"  [{'ok' if c['ok'] else 'FAIL'}] {c['check']}"
            + (f"  — {c['detail']}" if c["detail"] else ""))
    log("")
    log(f"{'READY' if report['ok'] else 'NOT READY'} — wrote {AUDIT_JSON}")
    return report


# ── CLI ────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="nohup python scripts/run_manuscript_refits.py all "
               "> refits.log 2>&1 &")
    ap.add_argument("stage", choices=["forward", "inverse", "all", "audit"])
    ap.add_argument("--temptypes", nargs="+", choices=list(TEMPTYPES),
                    help="default: all")
    ap.add_argument("--force", action="store_true",
                    help="ignore the manifest and re-run")
    ap.add_argument("--force-lock", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    STOP.install()
    log(f"repo    : {REPO}")
    log(f"results : {RESULTS_DIR}")
    log(f"budgets : forward {FWD_WARMUP}/{FWD_SAMPLING} · "
        f"inverse {INV_WARMUP}/{INV_SAMPLING} M={INV_M} · "
        f"chains {CHAINS} · seed {SEED}")

    from contextlib import nullcontext
    lock = nullcontext() if args.dry_run else single_instance(force=args.force_lock)
    with lock:
        t0 = time.time()
        if args.stage in ("forward", "all"):
            run_forward(args.temptypes, force=args.force, dry_run=args.dry_run)
        if args.stage in ("inverse", "all") and not STOP.requested:
            run_inverse(args.temptypes, force=args.force, dry_run=args.dry_run)
        if args.stage == "audit" or (args.stage == "all" and not args.dry_run
                                     and not STOP.requested):
            audit()
        log("")
        log(f"done in {timedelta(seconds=int(time.time() - t0))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
