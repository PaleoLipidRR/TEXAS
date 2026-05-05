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
#   posteriors/forward/         — forward calibration posteriors (scaledRI_cren3, RI₀₋₃)
#   posteriors/invT/coretop/    — global coretop invT posteriors (combined)
#   posteriors/invT/paleo/      — paleo-site invT posteriors shown in manuscript figures
#   data/                       — training CSVs
#   README.md                   — archive manifest for Zenodo

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────────────
VERSION=$(python -c "from importlib.metadata import version; print(version('texas-psm'))" 2>/dev/null || \
          grep '^version' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')
ARCHIVE_DIR="review_archive_v${VERSION}"
FWD_CACHE="data/cache/TEXAS_posterior_cache"
INVT_CACHE="data/cache/TEXAS_invT_posterior_cache"

# ── Forward posteriors: source → clean-name mapping ─────────────────────────
# Format: "source_filename|clean_zenodo_name"
# All fitted with scaledRI_cren3 (RI₀₋₃); date tag stripped for Zenodo.
declare -a FWD_CANONICAL=(
  "gen_logi_fixed_culmeso_cultureT_scaledRI_cren3_050126.nc|gen_logi_fixed_culmeso_cultureT_scaledRI_cren3.nc"
  "gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3_050126.nc|gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3.nc"
  "gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI_cren3_050126.nc|gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI_cren3.nc"
  "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_scaledRI_cren3_050126.nc|gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_scaledRI_cren3.nc"
  "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_no3_1.0_scaledRI_cren3_050126.nc|gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_no3_1.0_scaledRI_cren3.nc"
  "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_eiv.nc|gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3.nc"
  "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_scaledRI_cren3_050126.nc|gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_scaledRI_cren3.nc"
  "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_no3_1.0_scaledRI_cren3_050126.nc|gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_no3_1.0_scaledRI_cren3.nc"
  "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_eiv.nc|gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3.nc"
)

# ── InvT posteriors: coretop (combined, 1513 obs each) ──────────────────────
declare -a INVT_CORETOP=(
  "global_coretop_invT_gen_logi_fixed_univ_unconstrained_SST_scaledRI_cren3_050126_direct.nc"
  "global_coretop_invT_gen_logi_fixed_univ_unconstrained_thermoT_scaledRI_cren3_050126_direct.nc"
  "global_coretop_invT_gen_logi_fixed_multiv_unconstrained_SST_gdgt23ratio_scaledRI_cren3_050126_direct.nc"
  "global_coretop_invT_gen_logi_fixed_multiv_unconstrained_thermoT_gdgt23ratio_scaledRI_cren3_050126_direct.nc"
  "global_coretop_invT_gen_logi_fixed_multiv_unconstrained_SST_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_direct.nc"
  "global_coretop_invT_gen_logi_fixed_multiv_unconstrained_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_direct.nc"
)

# ── InvT posteriors: paleo sites shown in manuscript figures ─────────────────
declare -a INVT_PALEO=(
  "Co1010_invT_gen_logi_fixed_multiv_unconstrained_SST_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_direct.nc"
  "DSDP591_invT_gen_logi_fixed_univ_unconstrained_sst_scaledRI_cren3_050126_direct.nc"
  "DSDP591_invT_gen_logi_fixed_univ_unconstrained_thermoT_scaledRI_cren3_050126_direct.nc"
  "DSDP591_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_direct.nc"
  "DSDP591_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_001_direct.nc"
  "DSDP591_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_01_direct.nc"
  "DSDP591_invT_gen_logi_fixed_multiv_unconstrained_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_direct.nc"
  "DSDP591_invT_gen_logi_fixed_multiv_unconstrained_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_001_direct.nc"
  "DSDP591_invT_gen_logi_fixed_multiv_unconstrained_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_01_direct.nc"
  "MD98-2152_invT_gen_logi_fixed_univ_unconstrained_sst_scaledRI_cren3_050126_direct.nc"
  "MD98-2152_invT_gen_logi_fixed_univ_unconstrained_thermoT_scaledRI_cren3_050126_direct.nc"
  "MD98-2152_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_direct.nc"
  "MD98-2152_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_001_direct.nc"
  "MD98-2152_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_01_direct.nc"
  "MD98-2152_invT_gen_logi_fixed_multiv_unconstrained_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_direct.nc"
  "MD98-2152_invT_gen_logi_fixed_multiv_unconstrained_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_001_direct.nc"
  "MD98-2152_invT_gen_logi_fixed_multiv_unconstrained_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_01_direct.nc"
  "ODP1259_invT_gen_logi_fixed_multiv_unconstrained_SST_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_direct.nc"
  "ODP959_invT_gen_logi_fixed_univ_unconstrained_sst_scaledRI_cren3_050126_direct.nc"
  "ODP959_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_001_direct.nc"
  "ODP959_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_01_direct.nc"
  "ODP959_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_10_direct.nc"
  "ODP959_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_modern_direct.nc"
  "SDB_invT_gen_logi_fixed_univ_unconstrained_sst_scaledRI_cren3_050126_direct.nc"
  "SDB_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_001_direct.nc"
  "SDB_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_01_direct.nc"
  "SDB_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_10_direct.nc"
  "SDB_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_modern_direct.nc"
  "U1482_invT_gen_logi_fixed_univ_unconstrained_sst_scaledRI_cren3_050126_direct.nc"
  "U1482_invT_gen_logi_fixed_univ_unconstrained_thermoT_scaledRI_cren3_050126_direct.nc"
  "U1482_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_direct.nc"
  "U1482_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_001_direct.nc"
  "U1482_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_01_direct.nc"
  "U1482_invT_gen_logi_fixed_multiv_unconstrained_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_direct.nc"
  "U1482_invT_gen_logi_fixed_multiv_unconstrained_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_001_direct.nc"
  "U1482_invT_gen_logi_fixed_multiv_unconstrained_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_01_direct.nc"
  "U1510_invT_gen_logi_fixed_univ_unconstrained_sst_scaledRI_cren3_050126_direct.nc"
  "U1510_invT_gen_logi_fixed_univ_unconstrained_thermoT_scaledRI_cren3_050126_direct.nc"
  "U1510_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_direct.nc"
  "U1510_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_001_direct.nc"
  "U1510_invT_gen_logi_fixed_multiv_unconstrained_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_01_direct.nc"
  "U1510_invT_gen_logi_fixed_multiv_unconstrained_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_direct.nc"
  "U1510_invT_gen_logi_fixed_multiv_unconstrained_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_001_direct.nc"
  "U1510_invT_gen_logi_fixed_multiv_unconstrained_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_01_direct.nc"
)

declare -a DATA_FILES=(
  "data/spreadsheets/combined_coretop_culture_mesocosm_rev20260210.csv"
  "data/spreadsheets/ds_gridded_screened_global_compilation_finalized.csv"
)

# ── Create directory structure ───────────────────────────────────────────────
echo "Creating archive: ${ARCHIVE_DIR}/"
rm -rf "${ARCHIVE_DIR}"
mkdir -p "${ARCHIVE_DIR}/posteriors/forward"
mkdir -p "${ARCHIVE_DIR}/posteriors/invT/coretop"
mkdir -p "${ARCHIVE_DIR}/posteriors/invT/paleo"
mkdir -p "${ARCHIVE_DIR}/data"

# ── Copy forward posteriors ──────────────────────────────────────────────────
echo ""
echo "Forward calibration posteriors (scaledRI_cren3, RI₀₋₃):"
for entry in "${FWD_CANONICAL[@]}"; do
  src="${entry%%|*}"
  dst="${entry##*|}"
  src_path="${FWD_CACHE}/${src}"
  if [[ -f "${src_path}" ]]; then
    cp "${src_path}" "${ARCHIVE_DIR}/posteriors/forward/${dst}"
    echo "  ✓  ${dst}"
  else
    echo "  ✗  MISSING: ${src}"
    echo "     → Regenerate with: get_posterior(...) using the appropriate data"
  fi
done

# ── Copy coretop invT posteriors ─────────────────────────────────────────────
echo ""
echo "Coretop invT posteriors (combined, 1513 obs):"
for f in "${INVT_CORETOP[@]}"; do
  src_path="${INVT_CACHE}/${f}"
  if [[ -f "${src_path}" ]]; then
    cp "${src_path}" "${ARCHIVE_DIR}/posteriors/invT/coretop/${f}"
    echo "  ✓  ${f}"
  else
    echo "  ✗  MISSING: ${f}"
  fi
done

# ── Copy paleo-site invT posteriors ──────────────────────────────────────────
echo ""
echo "Paleo-site invT posteriors (manuscript figures):"
for f in "${INVT_PALEO[@]}"; do
  src_path="${INVT_CACHE}/${f}"
  if [[ -f "${src_path}" ]]; then
    cp "${src_path}" "${ARCHIVE_DIR}/posteriors/invT/paleo/${f}"
    echo "  ✓  ${f}"
  else
    echo "  ✗  MISSING: ${f}"
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
# TEXAS: GDGT calibration database and posteriors
**Version**: ${VERSION} (pre-publication / manuscript review)
**Package**: texas-psm — https://github.com/PaleoLipidRR/TEXAS

This archive contains the GDGT training database and pre-computed Bayesian posteriors
used in Rattanasriampaipong et al. (in prep).

All posteriors use **scaledRI_cren3** (Ring Index computed from GDGT-0 through
GDGT-cren, RI₀₋₃).

---

## Contents

### posteriors/forward/

Forward calibration posteriors. All fitted with scaledRI_cren3.

| File | Model | Temp type |
|------|-------|-----------|
| gen_logi_fixed_culmeso_cultureT_scaledRI_cren3.nc | Culture+mesocosm only | cultureT |
| gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3.nc | Temperature-only | SST |
| gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI_cren3.nc | Temperature-only | thermoT |
| gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_scaledRI_cren3.nc | G₂/₃ only | SST |
| gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_no3_1.0_scaledRI_cren3.nc | NO₃ only | SST |
| gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3.nc | Multivariate EIV (G₂/₃ + NO₃) | SST |
| gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_scaledRI_cren3.nc | G₂/₃ only | thermoT |
| gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_no3_1.0_scaledRI_cren3.nc | NO₃ only | thermoT |
| gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3.nc | Multivariate EIV (G₂/₃ + NO₃) | thermoT |

### posteriors/invT/coretop/

Inverse temperature posteriors for the global coretop dataset (1513 sites, combined
from batched runs). Used in calibration validation figures.

### posteriors/invT/paleo/

Inverse temperature posteriors for paleo-site reconstructions shown in the manuscript
figures (Co1010, DSDP591, MD98-2152, ODP1259, ODP959, SDB, U1482, U1510).
Sensitivity variants (no3_001, no3_01, no3_10, no3_modern) are included where shown.

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
    no3=my_no3_array,
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
