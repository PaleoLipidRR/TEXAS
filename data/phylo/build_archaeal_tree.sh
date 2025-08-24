#!/bin/bash

# Archaeal Phylogenetic Tree Generation Pipeline
# For TEXAS GDGT Temperature Calibration Project
# Author: Your Name
# Date: $(date +%Y-%m-%d)

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Configuration
EMAIL="rattanasriampaipong.r@gmail.com"
OUTPUT_DIR="/app/data/phylo"
SEQUENCES_DIR="${OUTPUT_DIR}/sequences"
ALIGNMENTS_DIR="${OUTPUT_DIR}/alignments"  
TREES_DIR="${OUTPUT_DIR}/trees"
LOG_FILE="${OUTPUT_DIR}/pipeline.log"

# GDGT-producing archaeal species (CORRECTED and EXPANDED)
declare -A SPECIES=(
    ["Nitrosopumilus_maritimus"]="NR_102904.1"
    ["Candidatus_Nitrosopelagicus_brevis"]="NR_118077.1"  # Added: Major marine TEX86 producer
    ["Nitrososphaera_viennensis"]="NR_109709.1"           # Added: Soil AOA
    ["Methanobrevibacter_smithii"]="NR_074174.1"          # Fixed accession
    ["Methanosarcina_barkeri"]="NR_028237.1"              # Fixed accession 
    ["Thermococcus_kodakarensis"]="NR_074233.1"           # Added: Model hyperthermophile
    ["Pyrococcus_furiosus"]="NR_029144.1"
    ["Sulfolobus_solfataricus"]="NR_074171.1"             # Fixed accession
    ["Archaeoglobus_fulgidus"]="NR_074254.1"              # Added: Thermophile
    ["Escherichia_coli"]="NR_024570.1"  # Bacterial outgroup
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

# Error handling
error_exit() {
    log "${RED}ERROR: $1${NC}"
    exit 1
}

# Success message
success() {
    log "${GREEN}✓ $1${NC}"
}

# Warning message
warning() {
    log "${YELLOW}! $1${NC}"
}

# Info message
info() {
    log "${BLUE}• $1${NC}"
}

# Check if required tools are available
check_dependencies() {
    info "Checking dependencies..."
    
    local tools=("python3" "mafft" "iqtree")
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            error_exit "$tool is not installed or not in PATH"
        fi
    done
    
    # Check Python packages
    python3 -c "
import sys
try:
    from Bio import Entrez, SeqIO
    print('✓ BioPython available')
except ImportError:
    print('✗ BioPython not available')
    sys.exit(1)
" || error_exit "BioPython is required but not installed"
    
    success "All dependencies are available"
}

# Create directory structure
setup_directories() {
    info "Setting up directory structure..."
    
    mkdir -p "${SEQUENCES_DIR}" "${ALIGNMENTS_DIR}" "${TREES_DIR}"
    
    success "Directory structure created"
}

# Download sequences from NCBI
download_sequences() {
    info "Downloading 16S rRNA sequences from NCBI..."
    
    local fasta_file="${SEQUENCES_DIR}/archaeal_16S.fasta"
    local temp_dir=$(mktemp -d)
    
    # Create Python script for downloading
    cat > "${temp_dir}/download.py" << EOF
#!/usr/bin/env python3
from Bio import Entrez, SeqIO
import sys

Entrez.email = "${EMAIL}"

# Load species from bash array
species_data = {}
EOF

    # Create Python script for downloading
    cat > "${temp_dir}/download.py" << EOF
#!/usr/bin/env python3
from Bio import Entrez, SeqIO
import sys

Entrez.email = "${EMAIL}"

# Updated species with corrected accessions
species_data = {
    "Nitrosopumilus_maritimus": "NR_102904.1",
    "Candidatus_Nitrosopelagicus_brevis": "NR_118077.1",
    "Nitrososphaera_viennensis": "NR_109709.1", 
    "Methanobrevibacter_smithii": "NR_074174.1",
    "Methanosarcina_barkeri": "NR_028237.1",
    "Thermococcus_kodakarensis": "NR_074233.1",
    "Pyrococcus_furiosus": "NR_029144.1",
    "Sulfolobus_solfataricus": "NR_074171.1", 
    "Archaeoglobus_fulgidus": "NR_074254.1",
    "Escherichia_coli": "NR_024570.1"
}

sequences = []
failed = []

print(f"Attempting to download {len(species_data)} species...")

for species, accession in species_data.items():
    try:
        print(f"Downloading {species} ({accession})...")
        handle = Entrez.efetch(db="nucleotide", id=accession, rettype="fasta", retmode="text")
        record = SeqIO.read(handle, "fasta")
        handle.close()
        
        record.id = species
        record.description = species.replace('_', ' ')
        sequences.append(record)
        print(f"✓ {species}")
        
    except Exception as e:
        print(f"✗ Failed to download {species}: {e}")
        failed.append(species)

print(f"\\nDownload Summary:")
print(f"✓ Successful: {len(sequences)}")
print(f"✗ Failed: {len(failed)}")

if len(sequences) < 8:
    print(f"ERROR: Only downloaded {len(sequences)} sequences, need at least 8")
    sys.exit(1)

with open("${fasta_file}", 'w') as f:
    SeqIO.write(sequences, f, "fasta")

print(f"Successfully wrote {len(sequences)} sequences to archaeal_16S.fasta")
if failed:
    print(f"Failed downloads: {', '.join(failed)}")
EOF

    # Run download script
    if python3 "${temp_dir}/download.py"; then
        success "Downloaded sequences to ${fasta_file}"
        
        # Log sequence info
        local seq_count=$(grep -c ">" "${fasta_file}")
        info "Total sequences downloaded: ${seq_count}"
    else
        error_exit "Failed to download sequences"
    fi
    
    # Clean up
    rm -rf "${temp_dir}"
}

# Align sequences with MAFFT
align_sequences() {
    info "Aligning sequences with MAFFT..."
    
    local input_file="${SEQUENCES_DIR}/archaeal_16S.fasta"
    local output_file="${ALIGNMENTS_DIR}/archaeal_16S_aligned.fasta"
    
    if [[ ! -f "${input_file}" ]]; then
        error_exit "Input sequences not found: ${input_file}"
    fi
    
    # Run MAFFT alignment
    if mafft \
        --auto \
        --thread 4 \
        --quiet \
        "${input_file}" > "${output_file}" 2>> "${LOG_FILE}"; then
        
        success "Alignment completed: ${output_file}"
        
        # Log alignment info
        local seq_count=$(grep -c ">" "${output_file}")
        local alignment_length=$(head -2 "${output_file}" | tail -1 | wc -c)
        info "Aligned ${seq_count} sequences, length: ${alignment_length} bp"
    else
        error_exit "MAFFT alignment failed"
    fi
}

# Build phylogenetic tree with IQ-TREE
build_tree() {
    info "Building phylogenetic tree with IQ-TREE..."
    
    local input_file="${ALIGNMENTS_DIR}/archaeal_16S_aligned.fasta"
    local output_prefix="${TREES_DIR}/archaeal_tree"
    
    if [[ ! -f "${input_file}" ]]; then
        error_exit "Aligned sequences not found: ${input_file}"
    fi
    
    # Run IQ-TREE
    if iqtree \
        -s "${input_file}" \
        -pre "${output_prefix}" \
        -m MFP \
        -bb 1000 \
        -redo \
        -quiet >> "${LOG_FILE}" 2>&1; then
        
        success "Phylogenetic tree completed: ${output_prefix}.treefile"
        
        # Extract and log key results
        if [[ -f "${output_prefix}.iqtree" ]]; then
            local model=$(grep "Model of substitution:" "${output_prefix}.iqtree" | cut -d: -f2 | xargs)
            local loglik=$(grep "Log-likelihood of the tree:" "${output_prefix}.iqtree" | cut -d: -f2 | cut -d'(' -f1 | xargs)
            info "Best model: ${model}"
            info "Log-likelihood: ${loglik}"
        fi
    else
        error_exit "IQ-TREE failed to build tree"
    fi
}

# Generate summary report
generate_report() {
    info "Generating analysis report..."
    
    local report_file="${OUTPUT_DIR}/phylogenetic_analysis_report.txt"
    
    cat > "${report_file}" << EOF
ARCHAEAL PHYLOGENETIC ANALYSIS REPORT - IMPROVED VERSION
========================================================
Date: $(date)
Email: ${EMAIL}

IMPROVEMENTS IN THIS VERSION:
- Added 4 additional GDGT-producing species (10 total vs 6)
- Fixed incorrect accession numbers
- Enhanced Thaumarchaeota coverage (3 species vs 1)
- Better temperature range representation (4°C to 103°C)
- Improved ecological diversity (marine, soil, extreme environments)

PIPELINE SUMMARY:
- Downloaded 16S rRNA sequences for GDGT-producing archaea
- Aligned sequences using MAFFT
- Built phylogenetic tree using IQ-TREE with model selection
- Bootstrap analysis: 1000 replicates

FILES GENERATED:
- Sequences: ${SEQUENCES_DIR}/archaeal_16S.fasta
- Alignment: ${ALIGNMENTS_DIR}/archaeal_16S_aligned.fasta  
- Tree: ${TREES_DIR}/archaeal_tree.treefile
- Full results: ${TREES_DIR}/archaeal_tree.*

SPECIES INCLUDED:
EOF

    # Add species info with groupings
    python3 -c "
import re
with open('${TREES_DIR}/archaeal_tree.treefile', 'r') as f:
    tree_string = f.read()
species = re.findall(r'([A-Za-z_]+):', tree_string)

# Group by taxonomic group
thaumarchaeota = [sp for sp in species if 'Nitros' in sp]
euryarchaeota = [sp for sp in species if sp in ['Methanobrevibacter_smithii', 'Methanosarcina_barkeri', 'Thermococcus_kodakarensis', 'Pyrococcus_furiosus', 'Archaeoglobus_fulgidus']]
crenarchaeota = [sp for sp in species if 'Sulfolobus' in sp]
bacteria = [sp for sp in species if sp == 'Escherichia_coli']

print('Thaumarchaeota (TEX86 producers):')
for sp in thaumarchaeota:
    print(f'- {sp.replace(\"_\", \" \")}')
print()
print('Euryarchaeota (diverse GDGT producers):') 
for sp in euryarchaeota:
    print(f'- {sp.replace(\"_\", \" \")}')
print()
print('Crenarchaeota (branched GDGT producers):')
for sp in crenarchaeota:
    print(f'- {sp.replace(\"_\", \" \")}')
print()
print('Bacterial outgroup:')
for sp in bacteria:
    print(f'- {sp.replace(\"_\", \" \")}')
" >> "${report_file}"

    cat >> "${report_file}" << EOF

NEXT STEPS FOR TEXAS PROJECT:
1. Load tree in analysis environment: Tree('${TREES_DIR}/archaeal_tree.treefile')
2. Integrate with GDGT temperature calibration data
3. Use phylogenetic context in Bayesian models
4. Create publication figures

EOF

    success "Report generated: ${report_file}"
}

# Create example species list file
create_species_template() {
    local species_file="${OUTPUT_DIR}/species_list.txt"
    
    if [[ -f "${species_file}" ]]; then
        warning "Species list file already exists: ${species_file}"
        return 0
    fi
    
    info "Creating species list template: ${species_file}"
    
    cat > "${species_file}" << EOF
# GDGT-Producing Archaeal Species List
# Format: species_name,ncbi_accession_number
# Lines starting with # are comments and will be ignored

# Thaumarchaeota - Major TEX86 producers
Nitrosopumilus_maritimus,NR_102904.1
Candidatus_Nitrosopelagicus_brevis,NR_118077.1
Nitrososphaera_viennensis,NR_109709.1

# Euryarchaeota - Diverse GDGT producers  
Methanobrevibacter_smithii,NR_044796.1
Methanosarcina_barkeri,NR_028163.1
Thermococcus_kodakarensis,NR_074233.1
Pyrococcus_furiosus,NR_029144.1
Archaeoglobus_fulgidus,NR_074254.1

# Crenarchaeota - Branched GDGT producers
Sulfolobus_solfataricus,NR_028164.1

# Bacterial outgroup
Escherichia_coli,NR_024570.1
EOF
    
    success "Species list template created. Edit ${species_file} to customize your analysis."
}
validate_results() {
    info "Validating results..."
    
    local tree_file="${TREES_DIR}/archaeal_tree.treefile"
    
    if [[ ! -f "${tree_file}" ]]; then
        error_exit "Tree file not found: ${tree_file}"
    fi
    
    # Check tree file format
    if ! grep -q ";" "${tree_file}"; then
        error_exit "Tree file appears to be invalid (no semicolon)"
    fi
    
    # Count species in tree
    local species_count=$(grep -o '[A-Za-z_]*:' "${tree_file}" | wc -l)
    if [[ ${species_count} -lt 8 ]]; then
        warning "Only ${species_count} species in tree, expected at least 8"
    else
        success "Tree validation passed: ${species_count} species"
    fi
}

# Print usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -h, --help         Show this help message"
    echo "  -e, --email        Set email for NCBI (default: ${EMAIL})"
    echo "  -o, --output       Set output directory (default: ${OUTPUT_DIR})"
    echo "  --skip-download    Skip sequence download step"
    echo "  --skip-align       Skip alignment step"
    echo "  --skip-tree        Skip tree building step"
    echo ""
    echo "Improvements in this version:"
    echo "  - Fixed incorrect accession numbers"
    echo "  - Added 4 additional GDGT-producing species"
    echo "  - Enhanced Thaumarchaeota coverage (3 species)"
    echo "  - Better temperature range representation"
}

# Parse command line arguments
SKIP_DOWNLOAD=false
SKIP_ALIGN=false
SKIP_TREE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        -e|--email)
            EMAIL="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --skip-download)
            SKIP_DOWNLOAD=true
            shift
            ;;
        --skip-align)
            SKIP_ALIGN=true
            shift
            ;;
        --skip-tree)
            SKIP_TREE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Main pipeline
main() {
    log "${BLUE}Starting IMPROVED Archaeal Phylogenetic Analysis Pipeline${NC}"
    log "Output directory: ${OUTPUT_DIR}"
    log "Email: ${EMAIL}"
    log "Species count: 10 (enhanced from 6 in previous version)"
    log "Key improvements: Fixed accessions, added TEX86 producers, broader temperature range"
    
    check_dependencies
    setup_directories
    
    if [[ "${SKIP_DOWNLOAD}" == false ]]; then
        download_sequences
    else
        info "Skipping sequence download"
    fi
    
    if [[ "${SKIP_ALIGN}" == false ]]; then
        align_sequences
    else
        info "Skipping sequence alignment"
    fi
    
    if [[ "${SKIP_TREE}" == false ]]; then
        build_tree
    else
        info "Skipping tree building"
    fi
    
    validate_results
    generate_report
    
    success "IMPROVED pipeline completed successfully!"
    info "Check the report: ${OUTPUT_DIR}/phylogenetic_analysis_report.txt"
    info "Main tree file: ${TREES_DIR}/archaeal_tree.treefile"
}

# Run main function
main "$@"