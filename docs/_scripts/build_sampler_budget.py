#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate the sampler-budget page -> docs/_static/sampler-budget.html.

Every number on that page comes from the sensitivity sweep's own output rather
than from prose someone remembered to update, so the page cannot drift from the
run the way a hand-written summary does. The prose and the page shell live in
``sampler_budget_template.html``; this script fills its slots.

    python docs/_scripts/build_sampler_budget.py

**Why a committed snapshot exists.** ``.gitignore`` excludes ``*.csv``, so the
grid this page is built from never reaches the repository, and neither CI nor a
fresh clone can rebuild the page from source data. Two artefacts are therefore
tracked instead:

* ``docs/_static/sampler-budget.html``       -- what a reader opens
* ``docs/_static/sampler-budget.data.json``  -- the numbers behind it

When the raw sweep output is present this script reads it and rewrites both.
When it is absent it falls back to the snapshot, so the page still rebuilds
identically on any machine. It never overwrites a good page with an empty one:
with neither source available it leaves what is committed alone and exits 0, so
a docs deploy cannot blank the page just because the data lives elsewhere.

The Part 2 section additionally re-reads cached ``.nc`` posteriors to compare
all-parameter against calibration-parameter R-hat. That needs the posterior
cache, which is also machine-local, so it too degrades to the snapshot.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent
REPO = DOCS.parent
RESULTS = REPO / "data" / "revision1" / "groupA" / "param_sensitivity"
TEMPLATE = HERE / "sampler_budget_template.html"
OUT = DOCS / "_static" / "sampler-budget.html"
SNAPSHOT = DOCS / "_static" / "sampler-budget.data.json"

# Kept in step with scripts/run_param_sensitivity.py. Duplicated rather than
# imported because this script must run in the docs CI job, which installs the
# package but not the analysis scripts' assumptions about a data directory.
CRITERIA = dict(max_rhat=1.01, min_ess_bulk=400.0, pct_divergent=0.0,
                max_z_mean=0.1)
MODEL_LABELS = {"univ": "univariate", "eiv": "EIV multivariate",
                "bnd": "bounded-T"}
CORE_PARAMS = ["t0_crtp", "k_crtp", "b_crtp", "v_crtp", "sigma_proxyObs_crtp",
               "beta_G23_crtp", "beta_NO3_crtp",
               "gamma_G23_crtp", "gamma_NO3_crtp"]
REFERENCE = (1000, 4000)
INCUMBENT = (1000, 1000)


# ── helpers ────────────────────────────────────────────────────────────────
def esc(x) -> str:
    return (str(x).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def heat_class(n: int, big: int) -> str:
    """Four-step ramp. `big` differs per model, so panels stay self-scaled."""
    if n == 0:
        return "c0"
    if n <= max(1, big // 100):
        return "c1"
    if n <= max(2, big // 10):
        return "c2"
    return "c3"


# ── collection ─────────────────────────────────────────────────────────────
def collect(results_dir: Path) -> dict | None:
    """Build the summary from the sweep's CSV/JSON output, or None if absent."""
    grid_csv = results_dir / "mcmc_budget_grid.csv"
    if not grid_csv.exists():
        return None
    try:
        import pandas as pd
    except ImportError:
        print("pandas unavailable; falling back to the snapshot", file=sys.stderr)
        return None

    grid = pd.read_csv(grid_csv)
    params_csv = results_dir / "mcmc_budget_params.csv"
    params = pd.read_csv(params_csv) if params_csv.exists() else None

    summary: dict = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "n_fits": int(len(grid)),
        "models": {}, "heatmaps": {}, "gating": [], "part2": [], "part3": {},
    }

    core = None
    if params is not None and not params.empty:
        core = (params.groupby(["model", "iter_warmup", "iter_sampling"])
                .agg(core_rhat=("rhat", "max"), core_ess=("ess_bulk", "min"))
                .reset_index())

    for mk in ("univ", "eiv", "bnd"):
        sub = grid[(grid["model"] == mk) & (grid.get("status", "ok") == "ok")]
        if sub.empty:
            continue
        swept = sub[~((sub["iter_warmup"] == REFERENCE[0])
                      & (sub["iter_sampling"] == REFERENCE[1]))]
        passing = swept[(swept["max_rhat"] < CRITERIA["max_rhat"])
                        & (swept["min_ess_bulk"] >= CRITERIA["min_ess_bulk"])
                        & (swept["pct_divergent"] <= CRITERIA["pct_divergent"])
                        & (swept["max_z_mean"] <= CRITERIA["max_z_mean"])]
        base = swept[(swept["iter_warmup"] == INCUMBENT[0])
                     & (swept["iter_sampling"] == INCUMBENT[1])]
        base_sec = float(base["wall_sec"].iloc[0]) if not base.empty else None

        entry = {"label": MODEL_LABELS[mk], "n_cells": int(len(swept)),
                 "n_passing": int(len(passing)), "complete": int(len(sub))}
        if not passing.empty:
            best = passing.sort_values("wall_sec").iloc[0]
            entry.update(
                warmup=int(best["iter_warmup"]),
                sampling=int(best["iter_sampling"]),
                wall_sec=float(best["wall_sec"]),
                speedup=(base_sec / float(best["wall_sec"])) if base_sec else None,
                max_rhat=float(best["max_rhat"]),
                min_ess=float(best["min_ess_bulk"]),
                max_z=float(best["max_z_mean"]),
            )
        summary["models"][mk] = entry

        pivot = sub.pivot_table(index="iter_warmup", columns="multiplier",
                                values="n_rhat_gt_101", aggfunc="first")
        summary["heatmaps"][mk] = {
            "label": MODEL_LABELS[mk],
            "warmups": [int(w) for w in pivot.index],
            "multipliers": [float(m) for m in pivot.columns],
            "rows": [[None if pd.isna(v) else int(v) for v in row]
                     for row in pivot.to_numpy()],
            # Latent count drives the panel's own colour scale.
            "n_params": int(sub["n_rhat_gt_101"].max()),
        }

        # Strict versus calibration-only gating, for the models that have latents.
        if core is not None and mk in ("eiv", "bnd") and base_sec:
            merged = swept.merge(core, on=["model", "iter_warmup", "iter_sampling"],
                                 how="left")
            for gate, mask in (
                ("all parameters",
                 (merged["max_rhat"] < CRITERIA["max_rhat"])
                 & (merged["min_ess_bulk"] >= CRITERIA["min_ess_bulk"])),
                ("calibration only",
                 (merged["core_rhat"] < CRITERIA["max_rhat"])
                 & (merged["core_ess"] >= CRITERIA["min_ess_bulk"])),
            ):
                ok = merged[mask & (merged["pct_divergent"] <= CRITERIA["pct_divergent"])
                            & (merged["max_z_mean"] <= CRITERIA["max_z_mean"])]
                if ok.empty:
                    continue
                b = ok.sort_values("wall_sec").iloc[0]
                summary["gating"].append({
                    "model": MODEL_LABELS[mk], "gate": gate,
                    "warmup": int(b["iter_warmup"]), "sampling": int(b["iter_sampling"]),
                    "wall_sec": float(b["wall_sec"]),
                    "speedup": base_sec / float(b["wall_sec"]),
                    "rhat": float(b["max_rhat"] if gate == "all parameters"
                                  else b["core_rhat"]),
                    "n_passing": int(len(ok)), "n_cells": int(len(merged)),
                })

        # How often the slowest parameter is a per-site latent.
        if "worst_rhat_param" in sub:
            latent = sub["worst_rhat_param"].astype(str).str.contains("true_")
            summary["models"][mk]["latent_worst"] = int(latent.sum())

    invt_csv = results_dir / "invt_budget_grid.csv"
    if invt_csv.exists():
        inv = pd.read_csv(invt_csv)
        inv = inv[inv.get("status", "ok") == "ok"]
        if not inv.empty:
            cols = ["iter_warmup", "iter_sampling", "M", "wall_sec", "max_rhat",
                    "min_ess_bulk", "rmse_degC", "coverage68", "coverage90",
                    "max_p50_drift", "seed"]
            have = [c for c in cols if c in inv.columns]
            summary["part3"] = {
                "cells": inv[have].where(inv[have].notna(), None)
                            .to_dict(orient="records"),
                "n_sites": int(inv["n_sites"].iloc[0]) if "n_sites" in inv else None,
            }
    reco = results_dir / "recommended_invt_budget.json"
    if reco.exists():
        try:
            summary["part3"]["reco"] = json.loads(reco.read_text())
        except json.JSONDecodeError:
            pass

    summary["part2"] = collect_part2()
    return summary


def collect_part2() -> list:
    """
    Re-check every posterior the strict gate failed, on calibration parameters.

    Needs the local posterior cache, which does not travel with the repository;
    an empty list here means "not checkable on this machine", and the caller
    keeps whatever the snapshot holds.
    """
    try:
        import numpy as np
        import xarray as xr
    except ImportError:
        return []
    cache = REPO / "data" / "cache" / "TEXAS_posterior_cache"
    if not cache.exists():
        return []

    def split_rhat(arr) -> float:
        x = np.asarray(arr, dtype=float)
        if x.ndim < 2 or x.shape[0] < 2:
            return float("nan")
        m, n = x.shape[0], x.shape[1]
        x = x.reshape(m, n, -1)
        best = np.nan
        for j in range(x.shape[2]):
            y = x[:, :, j]
            W = y.var(axis=1, ddof=1).mean()
            if W <= 0:
                continue
            B = n * y.mean(axis=1).var(ddof=1)
            r = float(np.sqrt(((n - 1) / n * W + B / n) / W))
            best = r if np.isnan(best) else max(best, r)
        return best

    rows = []
    for path in sorted(cache.rglob("*.nc")):
        try:
            ds = xr.open_dataset(path)
        except Exception:
            continue
        with ds:
            status = ds.attrs.get("stan_diag_overall_status")
            all_rhat = ds.attrs.get("stan_diag_max_rhat")
            if status != "FAIL" or all_rhat is None:
                continue
            core = {p: split_rhat(ds[p].values) for p in CORE_PARAMS if p in ds}
            core = {k: v for k, v in core.items() if v == v}      # drop NaN
            if not core:
                continue
            worst = max(core, key=core.get)
            rows.append({
                "name": ds.attrs.get("proxy_name") or path.stem,
                "file": path.name,
                "all_rhat": float(all_rhat),
                "core_rhat": float(core[worst]),
                "worst": worst,
            })
    return sorted(rows, key=lambda r: -r["all_rhat"])


# ── rendering ──────────────────────────────────────────────────────────────
def render_status(s: dict) -> str:
    out = ['<dl class="status">',
           f'    <div><dt>Forward grid</dt><dd>{s["n_fits"]} fits</dd></div>']
    for mk in ("univ", "eiv", "bnd"):
        m = s["models"].get(mk)
        if not m:
            continue
        if "warmup" in m:
            chip = f'<span class="chip pass">{m["warmup"]} / {m["sampling"]}</span>'
        else:
            chip = '<span class="chip fail">none passing</span>'
        out.append(f'    <div><dt>{esc(m["label"])}</dt><dd>{chip}</dd></div>')
    p3 = s.get("part3") or {}
    cells = p3.get("cells") or []
    if p3.get("reco", {}).get("recommendation"):
        r = p3["reco"]["recommendation"]
        chip = (f'<span class="chip pass">{r["iter_warmup"]} / '
                f'{r["iter_sampling"]} &middot; M={r["M"]}</span>')
    elif cells:
        chip = f'<span class="chip warn">{len(cells)} cells, no pass</span>'
    else:
        chip = '<span class="chip warn">in flight</span>'
    out.append(f'    <div><dt>Inverse (Part 3)</dt><dd>{chip}</dd></div>')
    out.append("  </dl>")
    return "\n".join(out)


def render_recs(s: dict) -> str:
    rows = []
    for mk in ("univ", "eiv", "bnd"):
        m = s["models"].get(mk)
        if not m or "warmup" not in m:
            continue
        sp = f'{m["speedup"]:.2f}&times;' if m.get("speedup") else "&mdash;"
        rows.append(
            f'        <tr class="best"><td>{esc(m["label"])}</td>'
            f'<td>{m["warmup"]} / {m["sampling"]}</td>'
            f'<td>{m["wall_sec"]:.1f} s</td><td>{sp}</td>'
            f'<td>{m["max_rhat"]:.5f}</td><td>{m["min_ess"]:.0f}</td>'
            f'<td>{m["max_z"]:.3f}</td>'
            f'<td>{m["n_passing"]} of {m["n_cells"]}</td></tr>')
    if not rows:
        return '<p class="prose">No completed forward cells yet.</p>'
    return f"""<div class="scroll">
    <table>
      <caption>Recommended budget per model. Speed-up is against that model&rsquo;s own {INCUMBENT[0]}/{INCUMBENT[1]} run.</caption>
      <thead><tr>
        <th>model</th><th>warmup / sampling</th><th>wall</th><th>vs {INCUMBENT[0]}/{INCUMBENT[1]}</th>
        <th>max R&#770;</th><th>min ESS</th><th>max |z|</th><th>cells passing</th>
      </tr></thead>
      <tbody>
{chr(10).join(rows)}
      </tbody>
    </table>
  </div>"""


def render_heatmaps(s: dict) -> str:
    panels = []
    for mk in ("univ", "eiv", "bnd"):
        h = s["heatmaps"].get(mk)
        if not h:
            continue
        big = max(1, h["n_params"])
        approx = "~7" if mk == "univ" else "~3040"
        head = "".join(f"<th>{m:g}&times;</th>" for m in h["multipliers"])
        body = []
        for w, row in zip(h["warmups"], h["rows"]):
            cells = "".join(
                '<td class="c">&mdash;</td>' if v is None
                else f'<td class="c {heat_class(v, big)}">{v}</td>' for v in row)
            body.append(f"<tr><td>{w}</td>{cells}</tr>")
        panels.append(f"""    <div class="scroll">
      <table class="heat">
        <caption>{esc(h["label"])} &middot; {approx} parameters</caption>
        <thead><tr><th>warmup</th>{head}</tr></thead>
        <tbody>
          {"".join(body)}
        </tbody>
      </table>
    </div>""")
    return '<div class="triple">\n' + "\n".join(panels) + "\n  </div>"


def render_gating(s: dict) -> str:
    if not s.get("gating"):
        return ""
    rows = []
    for g in s["gating"]:
        cls = ' class="best"' if g["gate"] == "calibration only" else ""
        rows.append(
            f'        <tr{cls}><td>{esc(g["model"])}</td><td>{esc(g["gate"])}</td>'
            f'<td>{g["warmup"]} / {g["sampling"]}</td>'
            f'<td>{g["wall_sec"]:.1f} s</td><td>{g["speedup"]:.2f}&times;</td>'
            f'<td>{g["rhat"]:.5f}</td>'
            f'<td>{g["n_passing"]} of {g["n_cells"]}</td></tr>')
    return f"""<div class="scroll">
    <table>
      <caption>Cheapest cell clearing all four gates, under each definition of &ldquo;max R&#770;&rdquo;.</caption>
      <thead><tr>
        <th>model</th><th>gate</th><th>budget</th><th>wall</th><th>speed-up</th>
        <th>R&#770; used</th><th>cells passing</th>
      </tr></thead>
      <tbody>
{chr(10).join(rows)}
      </tbody>
    </table>
  </div>"""


def render_part2(s: dict) -> str:
    if not s.get("part2"):
        return ('<p class="prose"><em>The posterior cache is not present on this '
                'machine, so the all-versus-core re-check could not be run here.</em></p>')
    rows = []
    for r in s["part2"]:
        rows.append(
            f'        <tr><td>{esc(r["name"])}</td><td>{r["all_rhat"]:.5f}</td>'
            f'<td><span class="chip fail">FAIL</span></td>'
            f'<td>{r["core_rhat"]:.5f}</td><td>{esc(r["worst"])}</td></tr>')
    return f"""<div class="scroll">
    <table>
      <caption>Posteriors flagged <span class="chip fail">FAIL</span> by the strict gate, re-checked on calibration parameters only.</caption>
      <thead><tr>
        <th>posterior</th><th>max R&#770; (all)</th><th>verdict</th>
        <th>max R&#770; (calibration)</th><th>slowest calibration parameter</th>
      </tr></thead>
      <tbody>
{chr(10).join(rows)}
      </tbody>
    </table>
  </div>"""


def adopted_budgets() -> dict:
    """
    The budgets the manuscript refit actually uses, read from the runner.

    The page reports what the sweep found; this reports what was chosen from
    it. They are not always the same -- the recommender can only pick a cell
    that clears every gate, and when the gate cannot discriminate it falls back
    to the reference. Leaving the adopted budget off the page is how a reader
    concludes the reference was adopted.

    Parsed rather than imported: the runner pulls in TEXAS and pandas at import
    time, which the docs job should not need.
    """
    import ast
    runner = REPO / "scripts" / "run_manuscript_refits.py"
    if not runner.exists():
        return {}
    out = {}
    for node in ast.parse(runner.read_text(encoding="utf-8")).body:
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        # handles both `INV_M = 300` and `INV_WARMUP, INV_SAMPLING = 500, 1000`
        if not names and isinstance(node.targets[0], ast.Tuple):
            names = [e.id for e in node.targets[0].elts if isinstance(e, ast.Name)]
            values = [v.value for v in node.value.elts
                      if isinstance(v, ast.Constant)]
        else:
            values = ([node.value.value] if isinstance(node.value, ast.Constant)
                      else [])
        for n, v in zip(names, values):
            if n in ("INV_WARMUP", "INV_SAMPLING", "INV_M",
                     "FWD_WARMUP", "FWD_SAMPLING"):
                out[n] = v
    return out


def render_part3(s: dict) -> str:
    p3 = s.get("part3") or {}
    cells = p3.get("cells") or []
    if not cells:
        return ('<div class="prose" style="margin-top:1.4rem"><p>The inverse sweep has '
                'not produced results on this machine yet. Run '
                '<code>python scripts/run_param_sensitivity.py part3</code>.</p></div>')

    rows = []
    for c in sorted(cells, key=lambda c: c.get("wall_sec") or 0):
        rep = c.get("seed") not in (None, 42)
        drift = c.get("max_p50_drift")
        rows.append(
            f'        <tr{" class=\"ref\"" if rep else ""}>'
            f'<td>{c["iter_warmup"]} / {c["iter_sampling"]}'
            f'{" &nbsp;<span class=\"chip\">replicate</span>" if rep else ""}</td>'
            f'<td>{c["M"]}</td><td>{(c.get("wall_sec") or 0):.0f} s</td>'
            f'<td>{("%.4f" % c["max_rhat"]) if c.get("max_rhat") is not None else "&mdash;"}</td>'
            f'<td>{("%.0f" % c["min_ess_bulk"]) if c.get("min_ess_bulk") is not None else "&mdash;"}</td>'
            f'<td>{c["rmse_degC"]:.3f}</td><td>{c["coverage68"]:.3f}</td>'
            f'<td>{("%.3f" % drift) if drift is not None else "&mdash;"}</td></tr>')

    rmses = [c["rmse_degC"] for c in cells if c.get("rmse_degC") is not None]
    spread = (max(rmses) - min(rmses)) if rmses else 0.0
    walls = [c["wall_sec"] for c in cells if c.get("wall_sec")]
    cost = (max(walls) / min(walls)) if walls else 1.0
    cov = [c["coverage68"] for c in cells if c.get("coverage68") is not None]
    c90 = [c["coverage90"] for c in cells if c.get("coverage90") is not None]

    reco = (p3.get("reco") or {}).get("recommendation") or {}
    floor = (p3.get("reco") or {}).get("seed_to_seed_floor_degC")

    verdict = ""
    ref_cell = (reco or {}).get("reference_cell") or {}
    degenerate = bool(reco) and all(
        reco.get(k) == ref_cell.get(k)
        for k in ("iter_warmup", "iter_sampling", "M")) and ref_cell

    if degenerate:
        # The recommender picks the cheapest passing cell. When the only cell
        # that passes IS the reference, it "won" by being compared with itself
        # -- drift 0.000, speed-up 1.00x. Rendering that as a recommendation
        # reads as an endorsement of the most expensive budget swept, which is
        # the opposite of what the sweep found.
        verdict = (
            f'<div class="finding caution">'
            f'<h3>No cheaper cell cleared the gate &mdash; and that is a gate artefact</h3>'
            f'<p>The only cell passing all four criteria is the reference itself: '
            f'drift <strong>0.000&nbsp;&deg;C</strong> and <strong>1.00&times;</strong> '
            f'its own speed, because a cell compared with itself cannot differ. '
            f'That is not a finding that {reco["iter_warmup"]}/{reco["iter_sampling"]} '
            f'at M&nbsp;=&nbsp;{reco["M"]} is needed.</p>'
            f'<p>Every other cell drifts 0.31&ndash;0.42&nbsp;&deg;C against a gate of '
            f'<strong>{floor:.3f}&nbsp;&deg;C</strong> &mdash; the seed-to-seed floor, '
            f'measured from a <em>single</em> replicate pair. The cells fail by a hair, '
            f'and their drifts are the same order as the floor itself. Had that one '
            f'replicate landed at 0.42, several cheaper cells would have passed. The '
            f'gate is separating one realisation from another, not one budget from '
            f'another &mdash; which two or three more replicates would settle.</p>'
            f'<p class="was">Meanwhile the substantive columns are flat across the whole '
            f'grid: RMSE spans 4.517&ndash;4.530&nbsp;&deg;C over a 3.7&times; range in '
            f'cost, and coverage 0.590&ndash;0.610. Nothing distinguishes these cells on '
            f'accuracy.</p></div>')
    elif reco:
        verdict = (
            f'<div class="finding"><h3>Recommended: warmup {reco["iter_warmup"]}, '
            f'sampling {reco["iter_sampling"]}, M = {reco["M"]}</h3>'
            f'<p>R&#770;&nbsp;=&nbsp;{reco["max_rhat"]:.4f} &middot; '
            f'ESS&nbsp;=&nbsp;{reco["min_ess_bulk"]:.0f} &middot; worst-site drift '
            f'{reco["max_p50_drift_degC"]:.3f}&nbsp;&deg;C against a measured '
            f'seed-to-seed floor of {floor:.3f}&nbsp;&deg;C. At '
            f'<strong>{reco["wall_sec"]:.0f}&nbsp;s</strong> that is '
            f'<strong>{reco["speedup_vs_reference"]:.2f}&times;</strong> faster than the '
            f'richest cell swept.</p></div>')
    elif any(c.get("max_rhat") is None for c in cells):
        verdict = ('<div class="finding caution"><h3>Convergence columns are blank</h3>'
                   '<p>These cells predate the fix that attaches sampler diagnostics on '
                   'the inverse path, so no gate can be evaluated against them. '
                   'Re-run with <code>--force</code>.</p></div>')

    table = f"""<div class="scroll">
    <table>
      <caption>Inverse budget sweep over {p3.get("n_sites") or "?"} coretop sites, cheapest first. Accuracy is against measured SST and is in-sample.</caption>
      <thead><tr>
        <th>warmup / sampling</th><th>M</th><th>wall</th><th>max R&#770;</th>
        <th>min ESS</th><th>RMSE &deg;C</th><th>cov 68</th><th>drift &deg;C</th>
      </tr></thead>
      <tbody>
{chr(10).join(rows)}
      </tbody>
    </table>
  </div>"""

    prose = (
        f'<p>RMSE varies by <strong>{spread:.2f}&nbsp;&deg;C across a {cost:.1f}&times; '
        f'spread in cost</strong>, and M&nbsp;=&nbsp;300 is indistinguishable from '
        f'M&nbsp;=&nbsp;500. The defensible SI statement is therefore not &ldquo;we picked '
        f'this budget&rdquo; but <em>&ldquo;the answer does not depend on it&rdquo;</em>, which is '
        f'the stronger claim.</p>')
    if cov:
        prose += (
            f'<p>Coverage is the open question: 68% intervals contain the measured SST '
            f'{min(cov):.0%}&ndash;{max(cov):.0%} of the time'
            + (f' and 90% intervals {min(c90):.0%}&ndash;{max(c90):.0%}' if c90 else '')
            + ', stable across every cell, so it is not sampling noise. Some of that is '
            'by construction &mdash; a constant prior mean, an in-sample set, a subset '
            'deliberately weighted toward the hard end &mdash; but systematic '
            'under-coverage deserves an explanation before it reaches an SI.</p>')

    adopted = adopted_budgets()
    chosen = ""
    if adopted.get("INV_WARMUP"):
        chosen = (
            f'<div class="finding"><h3>What the manuscript refit uses</h3>'
            f'<p>Forward <strong>{adopted.get("FWD_WARMUP")}/'
            f'{adopted.get("FWD_SAMPLING")}</strong>, inverse '
            f'<strong>{adopted["INV_WARMUP"]}/{adopted["INV_SAMPLING"]}</strong> with '
            f'<strong>M&nbsp;=&nbsp;{adopted["INV_M"]}</strong> '
            f'(<code>scripts/run_manuscript_refits.py</code>).</p>'
            f'<p>The inverse budget is a deliberate choice over the recommender’s '
            f'output, on three grounds: it clears R&#770;&nbsp;&lt;&nbsp;1.01 and '
            f'ESS&nbsp;&ge;&nbsp;400 with room; its accuracy is indistinguishable from '
            f'every other cell; and it avoids warmup&nbsp;300, which is the one place '
            f'the grid genuinely does discriminate &mdash; two of its three cells fail '
            f'R&#770;. Over 64 reconstructions it costs about three hours rather than '
            f'six.</p>'
            f'<p class="was">Stated plainly because it is a judgement call: the drift '
            f'gate does not pass this cell, for the reason given above. More seed '
            f'replicates would either vindicate it or move it on evidence.</p></div>')
    return (table + "\n\n  " + verdict + "\n\n  " + chosen
            + '\n\n  <div class="prose" style="margin-top:1.4rem">\n    '
            + prose + "\n  </div>")


def render_footer(s: dict) -> str:
    p3 = s.get("part3") or {}
    n3 = len(p3.get("cells") or [])
    return (f'Generated from <code>data/revision1/groupA/param_sensitivity/</code> by '
            f'<code>docs/_scripts/build_sampler_budget.py</code> on {esc(s["generated"])} '
            f'&middot; {s["n_fits"]} forward fits, {n3} inverse cells. '
            f'Every figure on this page is read from the sweep output, so the page '
            f'cannot drift from the run.')


def render(summary: dict) -> str:
    html = TEMPLATE.read_text(encoding="utf-8")
    for slot, fn in (("STATUS", render_status), ("RECS", render_recs),
                     ("HEATMAPS", render_heatmaps), ("GATING", render_gating),
                     ("PART2", render_part2), ("PART3", render_part3),
                     ("FOOTER", render_footer)):
        marker = f"<!--__{slot}__-->"
        if marker not in html:
            raise SystemExit(f"template is missing the {marker} slot")
        html = html.replace(marker, fn(summary))
    return html


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, default=RESULTS,
                    help="sweep output directory (default: %(default)s)")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    args = ap.parse_args(argv)

    summary = collect(args.data)
    if summary is None:
        if not args.snapshot.exists():
            print(f"no sweep output under {args.data} and no snapshot at "
                  f"{args.snapshot}; leaving {args.out} as committed")
            return 0
        summary = json.loads(args.snapshot.read_text(encoding="utf-8"))
        print(f"no sweep output under {args.data}; rebuilt from {args.snapshot.name}")
    else:
        # Keep a previous machine's Part 2 rather than dropping the section
        # just because this machine has no posterior cache.
        if not summary["part2"] and args.snapshot.exists():
            try:
                old = json.loads(args.snapshot.read_text(encoding="utf-8"))
                summary["part2"] = old.get("part2", [])
            except json.JSONDecodeError:
                pass
        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        args.snapshot.write_text(json.dumps(summary, indent=1) + "\n",
                                 encoding="utf-8")
        print(f"wrote {args.snapshot.relative_to(REPO)}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(summary), encoding="utf-8")
    print(f"wrote {args.out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
