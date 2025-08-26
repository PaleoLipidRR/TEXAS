#!/bin/bash

# Flexible Archaeal Phylogenetic Tree Pipeline (bash v3 compatible)
# Can use custom species lists or default GDGT species

set -euo pipefail

# --- Configuration ---
EMAIL="rattanasriampaipong.r@gmail.com"
OUTPUT_DIR="/app/data/phylo"
SEQUENCES_DIR="${OUTPUT_DIR}/sequences"
ALIGNMENTS_DIR="${OUTPUT_DIR}/alignments"
TREES_DIR="${OUTPUT_DIR}/trees"
LOG_FILE="${OUTPUT_DIR}/pipeline.log"
SPECIES_FILE="${OUTPUT_DIR}/species_list.txt"
# Default output file prefix
OUTPUT_PREFIX="custom_archaeal_tree"

# --- Colors for output ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Initialize species arrays (standard indexed arrays for bash v3+)
declare -a SPECIES_NAMES
declare -a SPECIES_ACCESSIONS

# --- Logging functions ---
log() { echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"; }
error_exit() { log "${RED}ERROR: $1${NC}"; exit 1; }
success() { log "${GREEN}✓ $1${NC}"; }
warning() { log "${YELLOW}! $1${NC}"; }
info() { log "${BLUE}• $1${NC}"; }

# --- Core Functions ---

# Load species list from file
load_species_list() {
    if [[ -f "${SPECIES_FILE}" ]]; then
        info "Loading species from ${SPECIES_FILE}"
        while IFS= read -r line; do
            [[ "$line" =~ ^[[:space:]]*# ]] && continue
            [[ "$line" =~ ^[[:space:]]*$ ]] && continue
            if [[ "$line" == *","* ]]; then
                IFS=',' read -r species accession <<< "$line"
                species_trimmed=$(echo "$species" | xargs)
                accession_trimmed=$(echo "$accession" | xargs)
                if [[ -n "$species_trimmed" && -n "$accession_trimmed" ]]; then
                    SPECIES_NAMES+=("$species_trimmed")
                    SPECIES_ACCESSIONS+=("$accession_trimmed")
                fi
            fi
        done < "${SPECIES_FILE}"
        info "Loaded ${#SPECIES_NAMES[@]} species from custom list"
    else
        warning "No custom species list found at ${SPECIES_FILE}, using defaults"
        load_default_species
    fi
    if [[ ${#SPECIES_NAMES[@]} -lt 4 ]]; then
        error_exit "Need at least 4 species for meaningful phylogenetic analysis"
    fi
    info "Total species for analysis: ${#SPECIES_NAMES[@]}"
}

# Default GDGT species list
load_default_species() {
    info "Loading default GDGT-producing species"
    SPECIES_NAMES=(
        "Nitrosopumilus_maritimus" "Candidatus_Nitrosopelagicus_brevis" "Nitrososphaera_viennensis"
        "Methanobrevibacter_smithii" "Methanosarcina_barkeri" "Thermococcus_kodakarensis"
        "Pyrococcus_furiosus" "Sulfolobus_solfataricus" "Archaeoglobus_fulgidus" "Escherichia_coli"
    )
    SPECIES_ACCESSIONS=(
        "NR_102904.1" "NR_118077.1" "NR_109709.1" "NR_074174.1" "NR_028237.1"
        "NR_074233.1" "NR_029144.1" "NR_074171.1" "NR_074254.1" "NR_024570.1"
    )
}

# Create species template file
create_species_template() {
    info "Creating species list template: ${SPECIES_FILE}"
    cat > "${SPECIES_FILE}" << 'EOF'
# Custom Species List for Phylogenetic Analysis
# Format: species_name,ncbi_accession_number
Nitrosopumilus_maritimus,NR_102904.1
Candidatus_Nitrosopelagicus_brevis,NR_118077.1
Nitrososphaera_viennensis,NR_109709.1
Escherichia_coli,NR_024570.1
EOF
    success "Template created. Edit ${SPECIES_FILE} and re-run analysis"
}

# Validate NCBI accession numbers
validate_accessions() {
    info "Validating NCBI accession numbers..."
    local valid_count=0
    local total_count=${#SPECIES_NAMES[@]}
    for i in "${!SPECIES_NAMES[@]}"; do
        local species="${SPECIES_NAMES[i]}"
        local accession="${SPECIES_ACCESSIONS[i]}"
        if [[ "$accession" =~ ^[A-Z]{1,2}_[0-9]{6,}(\.[0-9]+)?$ ]]; then
            ((valid_count++))
            echo "  ✓ ${species}: ${accession}"
        else
            warning "  ? ${species}: ${accession} (unusual format)"
            ((valid_count++))
        fi
    done
    info "Validated ${valid_count}/${total_count} accessions"
}

# Check for required software dependencies
check_dependencies() {
    info "Checking dependencies..."
    local tools=("python3" "mafft" "iqtree")
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            error_exit "$tool is not installed or not in PATH"
        fi
    done
    python3 -c "import sys; from Bio import Entrez, SeqIO; print('✓ BioPython available')" || error_exit "BioPython is required"
    success "All dependencies available"
}

# Setup output directories
setup_directories() {
    info "Setting up directories..."
    mkdir -p "${SEQUENCES_DIR}" "${ALIGNMENTS_DIR}" "${TREES_DIR}"
    success "Directories ready"
}

# Download sequences from NCBI
download_sequences() {
    info "Downloading sequences from NCBI..."
    local fasta_file="${SEQUENCES_DIR}/${OUTPUT_PREFIX}_16S.fasta"
    local temp_dir=$(mktemp -d)
    
    cat > "${temp_dir}/download.py" << 'PYTHON_SCRIPT'
#!/usr/bin/env python3
from Bio import Entrez, SeqIO
import sys, time
Entrez.email = "PLACEHOLDER_EMAIL"
species_data = {}
sequences, failed = [], []
print(f"Starting download of {len(species_data)} species...")
print("-" * 50)
for species, accession in species_data.items():
    try:
        print(f"Downloading {species} ({accession})...")
        handle = Entrez.efetch(db="nucleotide", id=accession, rettype="fasta", retmode="text")
        record = SeqIO.read(handle, "fasta")
        handle.close()
        record.id, record.description = species, species.replace('_', ' ')
        sequences.append(record)
        print(f"  ✓ Success")
        time.sleep(0.3)
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        failed.append(species)
print("-" * 50)
print(f"Download Summary:\n  ✓ Successful: {len(sequences)}\n  ✗ Failed: {len(failed)}")
if len(sequences) < 3:
    print(f"ERROR: Only {len(sequences)} sequences downloaded")
    sys.exit(1)
output_file = "PLACEHOLDER_OUTPUT"
with open(output_file, 'w') as f:
    SeqIO.write(sequences, f, "fasta")
print(f"\n✓ Saved {len(sequences)} sequences to {output_file}")
if failed:
    print(f"\nFailed species: {', '.join(failed)}")
PYTHON_SCRIPT

    local species_insert_file="${temp_dir}/species_to_insert.py"
    for i in "${!SPECIES_NAMES[@]}"; do
        echo "species_data[\"${SPECIES_NAMES[i]}\"] = \"${SPECIES_ACCESSIONS[i]}\"" >> "${species_insert_file}"
    done
    
    sed -i "s/PLACEHOLDER_EMAIL/${EMAIL}/g" "${temp_dir}/download.py"
    sed -i "s|PLACEHOLDER_OUTPUT|${fasta_file}|g" "${temp_dir}/download.py"
    sed "/species_data = {}/r ${species_insert_file}" "${temp_dir}/download.py" > "${temp_dir}/final_download.py"

    if python3 "${temp_dir}/final_download.py"; then
        success "Sequences downloaded to ${fasta_file}"
        info "Downloaded $(grep -c ">" "${fasta_file}") sequences"
    else
        error_exit "Sequence download failed"
    fi
    rm -rf "${temp_dir}"
}

# Align sequences with MAFFT
align_sequences() {
    info "Aligning sequences with MAFFT..."
    local input_file="${SEQUENCES_DIR}/${OUTPUT_PREFIX}_16S.fasta"
    local output_file="${ALIGNMENTS_DIR}/${OUTPUT_PREFIX}_16S_aligned.fasta"
    if [[ ! -f "${input_file}" ]]; then error_exit "Input sequences not found: ${input_file}"; fi
    if mafft --auto --thread 4 --quiet "${input_file}" > "${output_file}" 2>> "${LOG_FILE}"; then
        success "Alignment completed: ${output_file}"
        info "Aligned $(grep -c ">" "${output_file}") sequences"
    else
        error_exit "MAFFT alignment failed"
    fi
}

# Build phylogenetic tree with IQ-TREE
build_tree() {
    info "Building phylogenetic tree with IQ-TREE..."
    local input_file="${ALIGNMENTS_DIR}/${OUTPUT_PREFIX}_16S_aligned.fasta"
    local output_prefix_path="${TREES_DIR}/${OUTPUT_PREFIX}"
    if [[ ! -f "${input_file}" ]]; then error_exit "Aligned sequences not found: ${input_file}"; fi
    if iqtree -s "${input_file}" -pre "${output_prefix_path}" -m MFP -bb 1000 -redo -quiet >> "${LOG_FILE}" 2>&1; then
        success "Tree building completed: ${output_prefix_path}.treefile"
        if [[ -f "${output_prefix_path}.iqtree" ]]; then
            local model=$(grep "Model of substitution:" "${output_prefix_path}.iqtree" | cut -d: -f2 | xargs)
            local loglik=$(grep "Log-likelihood of the tree:" "${output_prefix_path}.iqtree" | cut -d: -f2 | cut -d'(' -f1 | xargs)
            info "Best model: ${model}"
            info "Log-likelihood: ${loglik}"
        fi
    else
        error_exit "IQ-TREE failed"
    fi
}

# Generate a final summary report
generate_report() {
    info "Generating analysis report..."
    local report_file="${OUTPUT_DIR}/${OUTPUT_PREFIX}_report.txt"
    cat > "${report_file}" << EOF
CUSTOM PHYLOGENETIC ANALYSIS REPORT
===================================
Date: $(date)
Email: ${EMAIL}
Species file: ${SPECIES_FILE}
Output Prefix: ${OUTPUT_PREFIX}

ANALYSIS SUMMARY:
- Species analyzed: ${#SPECIES_NAMES[@]}
- Pipeline: Download → MAFFT → IQ-TREE
- Bootstrap replicates: 1000

FILES GENERATED:
- Sequences: ${SEQUENCES_DIR}/${OUTPUT_PREFIX}_16S.fasta
- Alignment: ${ALIGNMENTS_DIR}/${OUTPUT_PREFIX}_16S_aligned.fasta
- Tree: ${TREES_DIR}/${OUTPUT_PREFIX}.treefile
- Report: ${report_file}

SPECIES ANALYZED:
EOF
    for i in "${!SPECIES_NAMES[@]}"; do
        echo "- ${SPECIES_NAMES[i]} (${SPECIES_ACCESSIONS[i]})" >> "${report_file}"
    done
    cat >> "${report_file}" << EOF

NEXT STEPS:
1. Visualize tree: ${TREES_DIR}/${OUTPUT_PREFIX}.treefile
2. Validate species identification from download results
3. Consider adding/removing species based on research needs
EOF
    success "Report generated: ${report_file}"
}

# Print usage information
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Flexible phylogenetic tree builder with custom species support."
    echo ""
    echo "Options:"
    echo "  -h, --help           Show this help"
    echo "  -e, --email EMAIL    Set email for NCBI (default: ${EMAIL})"
    echo "  -s, --species FILE   Species list file (default: species_list.txt)"
    echo "  -o, --output PREFIX  Set the output prefix for files (default: ${OUTPUT_PREFIX})"
    echo "  --create-template    Create species list template and exit"
    echo "  --validate-only      Only validate accession numbers"
    echo "  --skip-download      Skip sequence download"
    echo "  --skip-align         Skip alignment step"
    echo "  --skip-tree          Skip tree building"
}

# --- Argument Parsing ---
CREATE_TEMPLATE=false
VALIDATE_ONLY=false
SKIP_DOWNLOAD=false
SKIP_ALIGN=false
SKIP_TREE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage; exit 0 ;;
        -e|--email)
            EMAIL="$2"; shift 2 ;;
        -s|--species)
            SPECIES_FILE="$2"; shift 2 ;;
        -o|--output)
            OUTPUT_PREFIX="$2"; shift 2 ;;
        --create-template)
            CREATE_TEMPLATE=true; shift ;;
        --validate-only)
            VALIDATE_ONLY=true; shift ;;
        --skip-download)
            SKIP_DOWNLOAD=true; shift ;;
        --skip-align)
            SKIP_ALIGN=true; shift ;;
        --skip-tree)
            SKIP_TREE=true; shift ;;
        *)
            echo "Unknown option: $1"; usage; exit 1 ;;
    esac
done

# --- Main Pipeline ---
main() {
    log "${BLUE}Flexible Archaeal Phylogenetic Pipeline${NC}"
    log "Email: ${EMAIL}"
    log "Species file: ${SPECIES_FILE}"
    
    setup_directories
    
    if [[ "${CREATE_TEMPLATE}" == true ]]; then
        create_species_template
        info "Edit ${SPECIES_FILE} and re-run without --create-template"
        exit 0
    fi
    
    load_species_list
    
    if [[ "${VALIDATE_ONLY}" == true ]]; then
        validate_accessions
        info "Validation complete. Use without --validate-only to run analysis"
        exit 0
    fi
    
    check_dependencies
    
    if [[ "${SKIP_DOWNLOAD}" == false ]]; then
        download_sequences
    fi
    
    if [[ "${SKIP_ALIGN}" == false ]]; then
        align_sequences
    fi
    
    if [[ "${SKIP_TREE}" == false ]]; then
        build_tree
    fi
    
    generate_report
    
    success "Custom phylogenetic analysis completed!"
    info "Tree file: ${TREES_DIR}/${OUTPUT_PREFIX}.treefile"
}

main "$@"

