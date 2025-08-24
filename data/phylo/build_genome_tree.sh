#!/bin/bash

# Phylogenomics Tree Pipeline using GTDB-Tk
# Builds a tree from a list of NCBI genome assembly accession numbers.

set -euo pipefail

# --- Configuration ---
EMAIL="rattanasriampaipong.r@gmail.com"
OUTPUT_DIR="/app/data/phylo/genome_tree_output"
GENOMES_DIR="${OUTPUT_DIR}/genomes"
GTDBTK_DIR="${OUTPUT_DIR}/gtdbtk_run"
LOG_FILE="${OUTPUT_DIR}/genome_pipeline.log"
GENOME_LIST_FILE="genome_list.txt" # Default input file name
OUTPUT_PREFIX="custom_genome_tree"

# --- Colors for output ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# --- Logging functions ---
log() { echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"; }
error_exit() { log "${RED}ERROR: $1${NC}"; exit 1; }
success() { log "${GREEN}✓ $1${NC}"; }
info() { log "${BLUE}• $1${NC}"; }

# --- Core Functions ---

# Download genomes using NCBI's datasets tool
download_genomes() {
    info "Downloading genomes from NCBI..."
    if ! command -v datasets &> /dev/null; then
        error_exit "'datasets' command not found. Please ensure NCBI Datasets CLI is installed."
    fi

    # Read accessions from the list file
    mapfile -t accessions < "${GENOME_LIST_FILE}"

    for accession in "${accessions[@]}"; do
        # Skip comments and empty lines
        [[ "$accession" =~ ^[[:space:]]*# ]] && continue
        [[ "$accession" =~ ^[[:space:]]*$ ]] && continue
        
        info "Downloading genome: ${accession}"
        datasets download genome accession "${accession}" --filename "${GENOMES_DIR}/${accession}.zip"
        unzip -q -o "${GENOMES_DIR}/${accession}.zip" -d "${GENOMES_DIR}/${accession}"
        # Find the actual genome file and move it
        find "${GENOMES_DIR}/${accession}" -name "*.fna" -exec mv {} "${GENOMES_DIR}/${accession}.fna" \;
        rm -rf "${GENOMES_DIR}/${accession}.zip" "${GENOMES_DIR}/${accession}"
    done
    success "All genomes downloaded to ${GENOMES_DIR}"
}

# Run the GTDB-Tk pipeline
run_gtdbtk() {
    info "Running GTDB-Tk analysis..."
    gtdbtk classify_wf \
        --genome_dir "${GENOMES_DIR}" \
        --out_dir "${GTDBTK_DIR}" \
        --cpus 8 \
        --extension fna \
        --skip_ani_screen # <-- This is the required flag we added
    success "GTDB-Tk analysis complete."
}

# Finalize and report
generate_report() {
    info "Finalizing outputs and generating report..."
    local final_tree_file="${OUTPUT_DIR}/${OUTPUT_PREFIX}.tree"
    # GTDB-Tk places the final tree here:
    cp "${GTDBTK_DIR}/gtdbtk.ar122.user_msa.inferred.tree" "${final_tree_file}"

    log "Phylogenomic analysis completed!"
    log "Final tree file: ${final_tree_file}"
    log "Full GTDB-Tk output is in: ${GTDBTK_DIR}"
}

# --- Argument Parsing & Main Execution ---
usage() {
    echo "Usage: $0 -g <genome_list.txt> -o <output_prefix>"
    echo "  -g : Text file with one NCBI genome assembly accession per line."
    echo "  -o : Prefix for the final output tree file (default: ${OUTPUT_PREFIX})."
}

while getopts ":g:o:h" opt; do
  case ${opt} in
    g ) GENOME_LIST_FILE=$OPTARG ;;
    o ) OUTPUT_PREFIX=$OPTARG ;;
    h ) usage; exit 0 ;;
    \? ) usage; exit 1 ;;
  esac
done

# Main pipeline
mkdir -p "${GENOMES_DIR}" "${GTDBTK_DIR}"
log "Starting Phylogenomics Pipeline"
log "Genome List: ${GENOME_LIST_FILE}"
log "Output Prefix: ${OUTPUT_PREFIX}"

download_genomes
run_gtdbtk
generate_report

success "Pipeline finished successfully!"

