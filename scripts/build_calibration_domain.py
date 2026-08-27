#!/usr/bin/env python3
"""Freeze the calibration-domain ellipse that ships with the package.

Section 5.1 of the manuscript defines the screening ellipse on a **fixed
reference cluster** -- core-top samples with GDGT-2/GDGT-3 <= 5, low-abundance
samples removed -- not on whatever data is being screened. Re-fitting on a
user's own record would let the domain move with the record: an all-warm
Paleogene section would recentre the ellipse onto itself and flag nothing.

So the reference ellipse is a published property of the calibration, and it has
to travel with the package. This script computes it once from the training
database and writes ``src/TEXAS/data/calibration_domain.json``.

Confidence is deliberately NOT baked in: only the centroid and inverse
covariance are stored, so ``from_calibration(confidence=...)`` can derive the
threshold for any level from the chi-square quantile.

    python scripts/build_calibration_domain.py            # dry run
    python scripts/build_calibration_domain.py --apply
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
TRAINING = REPO / "data/spreadsheets/combined_coretop_culture_mesocosm_rev20260210.csv"
OUT = REPO / "src/TEXAS/data/calibration_domain.json"

FEATURES = ["TEX86", "scaledRI_cren3"]
G23_CUTOFF = 5.0          # the "reference cluster" of Section 5.1
CONFIDENCE_DEFAULT = 0.90


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    from TEXAS.data import MahalanobisOutlierDetector

    df = pd.read_csv(TRAINING, low_memory=False)
    ref = df[(df["datatype"] == "coretop")
             & (df["lowAbundanceFlag"] == False)      # noqa: E712
             & (df["gdgt23ratio"] <= G23_CUTOFF)]

    det = MahalanobisOutlierDetector(FEATURES, confidence=CONFIDENCE_DEFAULT).fit(ref)
    valid = ref[FEATURES].replace([np.inf, -np.inf], np.nan).dropna()

    payload = {
        "features": FEATURES,
        "mean": [float(x) for x in det.mean_vec],
        "inv_cov": [[float(v) for v in row] for row in det.inv_cov],
        "n_reference": int(len(valid)),
        "reference_cluster": (
            f"core-top samples, lowAbundanceFlag == False, "
            f"GDGT-2/GDGT-3 <= {G23_CUTOFF} (manuscript Section 5.1)"
        ),
        "source": TRAINING.name,
        "threshold_at_0.90": float(det.threshold),
    }

    print(f"reference cluster : {payload['n_reference']} samples from {TRAINING.name}")
    print(f"features          : {FEATURES}")
    print(f"centroid          : {np.round(det.mean_vec, 4).tolist()}")
    print(f"D_M threshold@0.90: {det.threshold:.4f}")
    if not args.apply:
        print(f"\nDry run -- would write {OUT.relative_to(REPO)}")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
