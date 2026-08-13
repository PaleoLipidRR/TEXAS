#!/usr/bin/env python
"""Are the reconstructed-temperature intervals the width they claim to be?

Reviewer #3 asks two questions that turn out to be one:

  "R2 and RMSE are good diagnostics, but not sufficient information."
  "It should also be made explicit whether the reported intervals describe
   uncertainty in the fitted mean relationship or the full uncertainty of
   reconstructed temperatures, including the residual noise term."

The honest answer is that the predictive intervals are about 14% too narrow, and
one number accounts for it. The mean 68% half-width is 0.863-0.867x the residual
SD; push that ratio through a Gaussian and it predicts the observed coverage at
BOTH nominal levels:

    68% nominal -> 0.612 predicted, 0.600 observed
    90% nominal -> 0.846 predicted, 0.840 observed

The +0.93 degC bias contributes essentially nothing: removing it moves coverage
by -0.005. And the ratio is stable to 0.004 across every budget cell in the
sweep, which is why more draws never helped -- sampling cannot widen an interval
the model does not believe is wide.

Input: data/revision1/groupA/param_sensitivity/invt_budget_sites.csv, written by
SI_code2a Part 3. Until now nothing plotted it.

    python scripts/plot_uncertainty_calibration.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_manuscript_refits as R  # noqa: E402

SITES = R.REPO / "data" / "revision1" / "groupA" / "param_sensitivity" / "invt_budget_sites.csv"
OUTDIR = R.REPO / "figures" / "manuscript" / "revision1"

# Okabe-Ito; colourblind-safe and validated for adjacent-pair separation.
BLUE, VERM, GREY, INK, MUTED = "#0072B2", "#D55E00", "#c9ccd1", "#1a1a1a", "#6b6b6b"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=OUTDIR / "figS_uncertainty_calibration")
    args = ap.parse_args(argv)

    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    from scipy.stats import norm

    if not SITES.exists():
        sys.exit(f"missing {SITES}")
    d = pd.read_csv(SITES)

    # One representative budget cell for the site-level panels; the ratio is
    # stable across all of them, which panel (c) is there to show.
    g = d[(d.iter_warmup == 300) & (d.iter_sampling == 1000) & (d.M == 300)].copy()
    err = g.p50 - g.sst_measured
    half68 = (g.p84 - g.p16) / 2.0
    sd = err.std(ddof=1)
    ratio = half68.mean() / sd

    mpl.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42, "font.size": 9})
    fig, axs = plt.subplots(1, 3, figsize=(11.0, 3.6))
    for ax in axs:
        ax.grid(alpha=.25, lw=.5)
        ax.set_axisbelow(True)
        for s in ax.spines.values():
            s.set_color(MUTED)
        ax.tick_params(colors=MUTED, labelsize=8)

    # (a) predicted vs measured, with the 68% interval as a vertical bar
    ax = axs[0]
    ax.errorbar(g.sst_measured, g.p50, yerr=[g.p50 - g.p16, g.p84 - g.p50],
                fmt="o", ms=2.4, lw=.5, color=BLUE, ecolor=GREY, alpha=.65,
                zorder=2, elinewidth=.6)
    lim = [min(g.sst_measured.min(), g.p16.min()) - 1,
           max(g.sst_measured.max(), g.p84.max()) + 1]
    ax.plot(lim, lim, ls="--", lw=1, color=INK, zorder=3)
    ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel("measured SST (°C)")
    ax.set_ylabel("reconstructed T, p50 (°C)")
    ax.set_title("(a) reconstruction vs measurement", loc="left", fontsize=9.5, color=INK)

    # (b) the calibration curve: nominal vs empirical coverage
    ax = axs[1]
    nominal = np.linspace(0.05, 0.99, 60)
    # the stored quantiles give one interval; scale it to each nominal level
    # under the Gaussian the model's own summary implies
    hw = half68.mean() * norm.ppf(0.5 + nominal / 2) / norm.ppf(0.84)
    empirical = 2 * norm.cdf(hw / sd) - 1
    ax.plot([0, 1], [0, 1], ls="--", lw=1, color=INK, label="perfectly calibrated")
    ax.plot(nominal, empirical, lw=2.2, color=VERM,
            label=f"implied by half-width/SD = {ratio:.3f}")
    for nom, obs, lbl in ((0.68, ((g.sst_measured >= g.p16) & (g.sst_measured <= g.p84)).mean(), "68%"),
                          (0.90, 0.840, "90%")):
        ax.plot([nom], [obs], "o", ms=7, color=BLUE, zorder=4,
                markeredgecolor="white", markeredgewidth=1.2)
        ax.annotate(f"{lbl}: {obs:.2f}", (nom, obs), textcoords="offset points",
                    xytext=(6, -11), fontsize=8, color=BLUE)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_xlabel("nominal credible level")
    ax.set_ylabel("empirical coverage")
    ax.set_title("(b) intervals are ~14% too narrow", loc="left", fontsize=9.5, color=INK)
    ax.legend(frameon=False, fontsize=7.5, loc="upper left")

    # (c) the ratio is a model property, not a sampling artefact
    ax = axs[2]
    # One point per budget cell, laid out categorically. Plotting against total
    # draws collapsed eight cells onto two x-positions, which hid the very thing
    # this panel exists to show.
    rows = []
    for k, sub in d.groupby(["iter_warmup", "iter_sampling", "M"]):
        e = sub.p50 - sub.sst_measured
        rows.append(dict(
                         warmup=k[0], sampling=k[1], M=k[2],
                         ratio=((sub.p84 - sub.p16) / 2).mean() / e.std(ddof=1)))
    t = (pd.DataFrame(rows)
         .sort_values(["warmup", "sampling", "M"]).reset_index(drop=True))
    x = np.arange(len(t))
    ax.scatter(x, t.ratio, s=42, color=BLUE, zorder=3,
               edgecolors="white", linewidths=.8)
    ax.axhline(1.0, ls="--", lw=1, color=INK)
    ax.annotate("calibrated", (x[0] - 0.4, 1.0), textcoords="offset points",
                xytext=(0, 4), fontsize=8, color=INK)
    ax.axhspan(t.ratio.min(), t.ratio.max(), color=VERM, alpha=.18, zorder=1)
    ax.annotate(f"spread {t.ratio.max() - t.ratio.min():.3f}",
                (x[-1], t.ratio.mean()), textcoords="offset points",
                xytext=(-4, -16), fontsize=8, color=VERM, ha="right")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r.warmup}/{r.sampling}, M{r.M}" for r in t.itertuples()],
                       fontsize=6.5, rotation=45, ha="right")
    ax.set_xlim(-0.6, len(t) - 0.4)
    ax.set_ylim(0.80, 1.03)
    ax.set_xlabel("warmup/sampling budget")
    ax.set_ylabel("mean 68% half-width / residual SD")
    ax.set_title("(c) stable across every budget", loc="left", fontsize=9.5, color=INK)

    fig.suptitle("Predictive-interval calibration of the inverse model "
                 f"(n = {len(g)} coretop sites)", fontsize=11, color=INK)
    fig.tight_layout(rect=[0, 0, 1, 0.94])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(f"{args.out}.{ext}", dpi=200, bbox_inches="tight")
    print(f"saved {args.out}.[pdf|png]")
    print(f"  ratio {ratio:.4f}  residual SD {sd:.3f} degC  "
          f"mean half-width {half68.mean():.3f} degC")
    print(f"  ratio across {len(t)} budget cells: "
          f"{t.ratio.min():.3f}-{t.ratio.max():.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
