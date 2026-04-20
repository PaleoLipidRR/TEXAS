#!/usr/bin/env bash
# prepare_review_archive.sh
#
# Assembles a local staging directory for the TEXAS Zenodo data/analysis record.
# This is the MANUSCRIPT REVIEW version (v0.x.xx) — a draft Zenodo upload for
# peer reviewers.  Do NOT use this for the final post-acceptance upload.
#
# Run from the repo root:
#   bash scripts/prepare_review_archive.sh
#
# Output: review_archive_v<VERSION>/
#   posteriors/canonical/   — final scaledRI_cren3 (RI₀₋₃) posteriors, clean names
#   posteriors/reference/   — scaledRI (RI₀₋₄) posteriors for comparison
#   data/                   — training CSVs
#   README.md               — archive manifest for Zenodo

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────────────
VERSION=$(python -c "import sys; sys.path.insert(0,'src'); from TEXAS import __version__; print(__version__)" 2>/dev/null || echo "0.1.5")
ARCHIVE_DIR="review_archive_v${VERSION}"
CACHE="data/cache/TEXAS_posterior_cache"

# ── Source → clean-name mapping ─────────────────────────────────────────────
# Format: "source_filename|clean_zenodo_name"
declare -a CANONICAL=(
  "gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3_032326.nc|gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3.nc"
  "gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI_cren3_032326.nc|gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI_cren3.nc"
  "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3_041626_eiv.nc|gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3.nc"
  "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3_041626_eiv.nc|gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3.nc"
)

declare -a REFERENCE=(
  "gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_032326.nc|gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI.nc"
  "gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI_032326.nc|gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI.nc"
  "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_041626_eiv.nc|gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI.nc"
  "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI_041626_eiv.nc|gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI.nc"
)

declare -a DATA_FILES=(
  "data/spreadsheets/combined_coretop_culture_mesocosm_rev20260210.csv"
  "data/spreadsheets/ds_gridded_screened_global_compilation_finalized.csv"
)

# ── Create directory structure ───────────────────────────────────────────────
echo "Creating archive: ${ARCHIVE_DIR}/"
rm -rf "${ARCHIVE_DIR}"
mkdir -p "${ARCHIVE_DIR}/posteriors/canonical"
mkdir -p "${ARCHIVE_DIR}/posteriors/reference"
mkdir -p "${ARCHIVE_DIR}/data"

# ── Copy canonical posteriors ────────────────────────────────────────────────
echo ""
echo "Canonical posteriors (scaledRI_cren3, RI₀₋₃ — recommended):"
for entry in "${CANONICAL[@]}"; do
  src="${entry%%|*}"
  dst="${entry##*|}"
  src_path="${CACHE}/${src}"
  if [[ -f "${src_path}" ]]; then
    cp "${src_path}" "${ARCHIVE_DIR}/posteriors/canonical/${dst}"
    echo "  ✓  ${dst}"
  else
    echo "  ✗  MISSING: ${src}"
    echo "     → Regenerate with: get_posterior(...) using the appropriate data"
  fi
done

# ── Copy reference posteriors ────────────────────────────────────────────────
echo ""
echo "Reference posteriors (scaledRI, RI₀₋₄ — for comparison only):"
for entry in "${REFERENCE[@]}"; do
  src="${entry%%|*}"
  dst="${entry##*|}"
  src_path="${CACHE}/${src}"
  if [[ -f "${src_path}" ]]; then
    cp "${src_path}" "${ARCHIVE_DIR}/posteriors/reference/${dst}"
    echo "  ✓  ${dst}"
  else
    echo "  ✗  MISSING: ${src}"
  fi
done

# ── Copy training data ───────────────────────────────────────────────────────
echo ""
echo "Training data:"
for f in "${DATA_FILES[@]}"; do
  if [[ -f "${f}" ]]; then
    cp "${f}" "${ARCHIVE_DIR}/data/"
    echo "  ✓  $(basename "${f}")"
  else
    echo "  ✗  MISSING: ${f}"
  fi
done

# ── Write archive README ─────────────────────────────────────────────────────
cat > "${ARCHIVE_DIR}/README.md" << EOF
# TEXAS: GDGT calibration database and forward posteriors
**Version**: ${VERSION} (pre-publication / manuscript review)
**Package**: texas-psm — https://github.com/PaleoLipidRR/TEXAS

This archive contains the GDGT training database and pre-computed Bayesian
forward calibration posteriors used in Rattanasriampaipong et al. (in prep).

---

## Contents

### posteriors/canonical/  — RECOMMENDED

Posteriors fitted with **scaledRI_cren3** (Ring Index computed from GDGT-0
through GDGT-cren, RI₀₋₃).  These are the primary posteriors used in the
manuscript and should be used for all new inverse reconstructions.

| File | Model | Temp type |
|------|-------|-----------|
| gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3.nc | Temperature-only | SST |
| gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI_cren3.nc | Temperature-only | thermoT |
| gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3.nc | Multivariate EIV (G₂/₃ + NO₃) | SST |
| gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3.nc | Multivariate EIV (G₂/₃ + NO₃) | thermoT |

### posteriors/reference/  — for comparison only

Posteriors fitted with **scaledRI** (Ring Index including GDGT-cren', RI₀₋₄).
Retained for comparison with earlier studies; not the primary model.

| File | Model | Temp type |
|------|-------|-----------|
| gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI.nc | Temperature-only | SST |
| gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI.nc | Temperature-only | thermoT |
| gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI.nc | Multivariate EIV (G₂/₃ + NO₃) | SST |
| gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI.nc | Multivariate EIV (G₂/₃ + NO₃) | thermoT |

### data/

| File | Description |
|------|-------------|
| combined_coretop_culture_mesocosm_rev20260210.csv | Master GDGT training database (culture + mesocosm + coretop) |
| ds_gridded_screened_global_compilation_finalized.csv | Gridded screened global coretop compilation |

---

## Usage

\`\`\`python
import TEXAS

# Download all posteriors from Zenodo (once DOI is live):
TEXAS.download_posteriors()

# Or load a local posterior directly:
post = TEXAS.load_posterior("gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3")

# Inverse reconstruction (multivariate EIV):
result = TEXAS.predict_T_from_proxyObs(
    proxyObs=my_ri_array,
    prior_mu_t=15.0,
    prior_sigma_t=10.0,
    fwd_posterior_name="gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3",
    gdgt23ratio=my_g23_array,
    no3=my_no3_array,             # from ocean_prop_ds["no3_sf2tc_avg"]
    # or: no3=10.0                # to disable NO₃ correction (value above 1.0 µmol/L cutoff)
    temptype="SST",
)
\`\`\`

---

## Citation

Rattanasriampaipong, R. et al. (in prep). *TEXAS: A proxy system model for
TEX86 paleothermometry.* AGU Paleoceanography and Paleoclimatology.
EOF

# ── Print manifest ───────────────────────────────────────────────────────────
echo ""
echo "────────────────────────────────────────────────────────────"
echo "Archive ready: ${ARCHIVE_DIR}/"
echo ""
find "${ARCHIVE_DIR}" -type f | sort | while read -r f; do
  size=$(du -sh "${f}" 2>/dev/null | cut -f1)
  echo "  ${size}  ${f#${ARCHIVE_DIR}/}"
done
echo ""
echo "Next steps:"
echo "  1. Review the files above — do NOT upload until the manuscript"
echo "     is ready for submission."
echo "  2. Create a Zenodo DRAFT record (do not publish yet):"
echo "     https://zenodo.org/deposit/new"
echo "  3. Drag the contents of ${ARCHIVE_DIR}/ into the Zenodo upload."
echo "  4. Save as draft — Zenodo will assign a DOI preview."
echo "  5. Fill CITATION.cff and download.py with the DOI when ready to publish."
echo "────────────────────────────────────────────────────────────"
