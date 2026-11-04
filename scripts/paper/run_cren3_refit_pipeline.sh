#!/usr/bin/env bash
# Driver for the fix/dm-screen-cren3 "elsewhere" refit, per
# data/revision1/groupA/screening_fix/README.md step 1.
# Run from the repo root of the release/v1.0.0-prep worktree.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PYTHONPATH="$REPO/src"
LOG="$REPO/logs/cren3_refit_pipeline.log"
mkdir -p "$REPO/logs"

run() {
  echo "=== $(date -Is) START: $* ===" | tee -a "$LOG"
  conda run -n texas-env --no-capture-output "$@" >>"$LOG" 2>&1
  status=$?
  echo "=== $(date -Is) END ($status): $* ===" | tee -a "$LOG"
  return $status
}

cd "$REPO" || exit 1

run python scripts/paper/run_manuscript_refits.py all || exit 1
run python scripts/paper/fit_t0shift_single_predictors.py || exit 1
run python scripts/paper/run_coretop_maps.py --arm univ || exit 1
run python scripts/paper/run_coretop_maps.py --arm bnd || exit 1
run python scripts/paper/run_coretop_maps.py --arm eiv || exit 1

echo "=== $(date -Is) PIPELINE COMPLETE ===" | tee -a "$LOG"
