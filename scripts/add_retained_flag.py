#!/usr/bin/env python3
"""Flag the warm-end samples the Mahalanobis screening retained (R2C13).

The response to reviewers promises: "The retained samples are flagged in the
archived calibration dataset for readers who wish to test alternatives."
The finalized gridded compilation is the calibration training set, but it
carried no screening columns — the flags lived only in the preprocessing
notebook. This script stamps them on, reproducing the manuscript's criterion
on the archived dataset itself:

- fit the 90% chi-square Mahalanobis ellipse on TEX86 vs Scaled RI(0-3),
  using the coretop rows with GDGT-2/3 ratio <= 5 (Section 5.1 / Fig. S6);
- ``mahalDist_TEXRI_cren3``: each row's Mahalanobis distance;
- ``mahal_outlier_090``: True where the row lies outside the ellipse;
- ``warm_end_retained``: True where a row is outside the ellipse but kept by
  the manual warm-end exception (TEX86 > 0.75 and Scaled RI(0-3) > 0.75).

Every ``warm_end_retained`` row is in the dataset only because of the
exception — dropping those rows re-screens without it.

Dry-run by default (prints counts); ``--apply`` rewrites the CSV in place.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
CSV = REPO / "data/spreadsheets/ds_gridded_screened_global_compilation_finalized.csv"
# The ellipse is fitted on the RAW sample-level database — the same domain the
# preprocessing notebook used — not on the gridded (already screened) set,
# whose tighter covariance would flag rows the original screening admitted.
RAW_CSV = REPO / "data/spreadsheets/combined_coretop_culture_mesocosm_rev20260210.csv"

FEATURES = ["TEX86", "scaledRI_cren3"]
CONFIDENCE = 0.90
G23_FIT_CUTOFF = 5.0
EXCEPTION = {"TEX86": 0.75, "scaledRI_cren3": 0.75}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="rewrite the CSV in place (default: dry run)")
    args = ap.parse_args(argv)

    from TEXAS.data import MahalanobisOutlierDetector

    df = pd.read_csv(CSV, low_memory=False)
    n0 = len(df)
    is_crtp = df["datatype"] == "coretop"
    crtp = df[is_crtp]

    # The screening is a coretop concept: the ellipse is fitted on the raw
    # sample-level low-G2/3 coretop cloud (Section 5.1 / SI_code1);
    # culture/mesocosm rows are not screened and get <NA> flags.
    raw = pd.read_csv(RAW_CSV, low_memory=False)
    fit_dom = raw[(raw["datatype"] == "coretop")
                  & (raw["lowAbundanceFlag"] == False)  # noqa: E712
                  & (raw["gdgt23ratio"] <= G23_FIT_CUTOFF)]
    det = MahalanobisOutlierDetector(FEATURES, confidence=CONFIDENCE)
    det.fit(fit_dom)

    dist = det.transform(crtp)
    outlier = det.detect_outliers(crtp)
    in_exception = ((crtp["TEX86"] > EXCEPTION["TEX86"])
                    & (crtp["scaledRI_cren3"] > EXCEPTION["scaledRI_cren3"]))
    retained = (outlier.fillna(False) & in_exception).astype(bool)

    print(f"{CSV.name}: {n0} rows ({int(is_crtp.sum())} coretop)")
    print(f"  fit domain ({RAW_CSV.name}: raw coretop, "
          f"lowAbundanceFlag=False, gdgt23ratio <= {G23_FIT_CUTOFF}): "
          f"{len(fit_dom)} rows; threshold D_M = {det.threshold:.4f}")
    print(f"  outside {CONFIDENCE:.0%} ellipse : {int(outlier.fillna(False).sum())}")
    print(f"  warm_end_retained       : {int(retained.sum())} "
          f"(TEX86 > {EXCEPTION['TEX86']} and Scaled RI0-3 > "
          f"{EXCEPTION['scaledRI_cren3']})")
    stray = outlier.fillna(False) & ~in_exception
    if stray.any():
        print(f"  NOTE: {int(stray.sum())} coretop row(s) outside the ellipse "
              "but NOT in the exception corner (gridding moved them slightly; "
              "they passed sample-level screening):")
        print(crtp.loc[stray, ["Latitude", "Longitude"] + FEATURES]
              .to_string(max_rows=10))

    df["mahalDist_TEXRI_cren3"] = pd.Series(dist, index=crtp.index)
    df["mahal_outlier_090"] = pd.Series(pd.NA, index=df.index, dtype="boolean")
    df.loc[is_crtp, "mahal_outlier_090"] = outlier.astype("boolean")
    df["warm_end_retained"] = False
    df.loc[is_crtp, "warm_end_retained"] = retained

    if not args.apply:
        print("\nDry run — CSV unchanged. Re-run with --apply to write.")
        return 0

    df.to_csv(CSV, index=False)
    print(f"\nWrote {CSV} ({n0} rows, +3 columns: "
          "mahalDist_TEXRI_cren3, mahal_outlier_090, warm_end_retained)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
