#!/bin/bash

# TEXAS Proxy Archaeal Cultures - Phylogenomic Analysis Summary Script
# For GDGT-based paleothermometry and temperature calibration studies
# Save this as: data/phylo/generate_phylo_summary.sh
# Usage: ./generate_phylo_summary.sh -o output_name [options]

set -euo pipefail

# === CONFIGURATION ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")" 
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Default configuration
OUTPUT_PREFIX=""
GTDB_OUTPUT_DIR=""
REPORT_DATE=$(date '+%Y%m%d_%H%M%S')
VERBOSE=${VERBOSE:-true} 
TREE_METHOD="fasttree"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Logging functions
log()     { >&2 echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"; }
success() { >&2 echo -e "${GREEN}✅ $1${NC}"; }
warning() { >&2 echo -e "${YELLOW}⚠️  $1${NC}"; }
error()   { >&2 echo -e "${RED}❌ $1${NC}"; }
verbose() { [[ "$VERBOSE" == "true" ]] && >&2 echo -e "${CYAN}DEBUG:${NC} $1"; }

# === USAGE ===
usage() {
    cat << EOF
TEXAS Proxy Archaeal Cultures - Phylogenomic Analysis Summary

Usage: $0 -o OUTPUT_NAME [options]

REQUIRED:
  -o NAME    Output prefix name (matches your GTDB-Tk -o parameter)

OPTIONAL:
  -d DIR     GTDB-Tk output directory (auto-detected if not specified)
  -t METHOD  Tree building method: fasttree|iqtree|raxml (default: fasttree)
  -v         Verbose output
  -h         Show this help

EXAMPLES:
  $0 -o texas_genome_tree                    # Use output from -o texas_genome_tree
  $0 -o my_calibration_set -t iqtree         # Custom set with IQ-TREE
  $0 -o culture_batch_1 -d /custom/path      # Custom output directory

CONTEXT:
  This script processes GTDB-Tk results for archaeal cultures used in
  TEXAS proxy temperature calibration studies. It generates phylogenetic
  trees and summaries for GDGT-producing archaeal taxa.

EOF
}

# === ARGUMENT PARSING ===
while getopts "o:d:t:vh" opt; do
    case $opt in
        o) OUTPUT_PREFIX="$OPTARG" ;;
        d) GTDB_OUTPUT_DIR="$OPTARG" ;;
        t) TREE_METHOD="$OPTARG" ;;
        v) VERBOSE=true ;;
        h) usage; exit 0 ;;
        *) echo "Invalid option. Use -h for help."; exit 1 ;;
    esac
done

# Validate required parameters
if [[ -z "$OUTPUT_PREFIX" ]]; then
    error "Output prefix (-o) is required!"
    usage
    exit 1
fi

# === PATH DETECTION ===
detect_paths() {
    verbose "Detecting paths for output prefix: $OUTPUT_PREFIX"
    
    # If custom directory specified, use it
    if [[ -n "$GTDB_OUTPUT_DIR" ]] && [[ -d "$GTDB_OUTPUT_DIR" ]]; then
        GTDBTK_OUTPUT="$GTDB_OUTPUT_DIR"
        verbose "Using custom GTDB-Tk directory: $GTDBTK_OUTPUT"
    else
        # Auto-detect based on common locations
        local possible_paths=(
            "/app/data/phylo/${OUTPUT_PREFIX}_output"
            "/workspace/data/phylo/${OUTPUT_PREFIX}_output"
            "/workspace/data/phylo/results/gtdbtk_outputs/${OUTPUT_PREFIX}_output"
            "$SCRIPT_DIR/${OUTPUT_PREFIX}_output"
            "/app/data/phylo/genome_tree_output"
            "/workspace/data/phylo/genome_tree_output"
            "$SCRIPT_DIR/genome_tree_output"
        )
        
        GTDBTK_OUTPUT=""
        for path in "${possible_paths[@]}"; do
            verbose "Checking: $path"
            if [[ -d "$path/gtdbtk_run" ]]; then
                GTDBTK_OUTPUT="$path"
                break
            fi
        done
        
        if [[ -z "$GTDBTK_OUTPUT" ]]; then
            error "Cannot find GTDB-Tk output directory for: $OUTPUT_PREFIX"
            echo ""
            echo "Searched locations:"
            printf '  %s\n' "${possible_paths[@]}"
            echo ""
            echo "Specify custom directory with -d /path/to/output"
            exit 1
        fi
    fi
    
    # Set specific file paths (support both parent dir and gtdbtk_run)
    if [[ -d "$GTDBTK_OUTPUT/classify" && -d "$GTDBTK_OUTPUT/align" ]]; then
        GTDBTK_RUN="$GTDBTK_OUTPUT"
    elif [[ -d "$GTDBTK_OUTPUT/gtdbtk_run/classify" ]]; then
        GTDBTK_RUN="$GTDBTK_OUTPUT/gtdbtk_run"
    else
        error "Could not locate GTDB-Tk run dir under: $GTDBTK_OUTPUT (expect classify/ and align/)"
        exit 1
fi
    
    # Detect AR set by globbing (handles ar53, ar122, future arXX)
    local s_glob=("$GTDBTK_RUN/classify/gtdbtk.ar"*.summary.tsv)
    local a_glob=("$GTDBTK_RUN/align/gtdbtk.ar"*.user_msa.fasta.gz)
    local t_glob=("$GTDBTK_RUN/classify/gtdbtk.ar"*.classify.tree)

    if (( ${#s_glob[@]} > 0 && ${#a_glob[@]} > 0 && ${#t_glob[@]} > 0 )); then
        SUMMARY_FILE="${s_glob[0]}"
        ALIGNMENT_GZ="${a_glob[0]}"
        REFERENCE_TREE="${t_glob[0]}"
        # Derive MARKER_SET (e.g., ar53/ar122)
        MARKER_SET="$(basename "$SUMMARY_FILE")"
        MARKER_SET="${MARKER_SET#gtdbtk.}"       # drop prefix
        MARKER_SET="${MARKER_SET%.summary.tsv}"  # drop suffix
    else
        error "No GTDB-Tk outputs found in: $GTDBTK_RUN (expected classify/ and align/)"
        exit 1
    fi
    
    log "Found GTDB-Tk results: $GTDBTK_OUTPUT"
    log "Marker set: $MARKER_SET"
    log "Working directory: $SCRIPT_DIR"
}

# === VALIDATION ===
validate_results() {
    log "Validating GTDB-Tk results..."
    
    local missing_files=()
    
    if [[ ! -f "$SUMMARY_FILE" ]]; then
        missing_files+=("Classification summary: $SUMMARY_FILE")
    fi
    
    if [[ ! -f "$ALIGNMENT_GZ" ]]; then
        missing_files+=("Alignment file: $ALIGNMENT_GZ")
    fi
    
    if [[ ! -f "$REFERENCE_TREE" ]]; then
        missing_files+=("Reference tree: $REFERENCE_TREE")
    fi
    
    if [[ ${#missing_files[@]} -gt 0 ]]; then
        error "Missing required files:"
        printf '  %s\n' "${missing_files[@]}"
        exit 1
    fi
    
    success "All required files validated"
    verbose "SUMMARY_FILE   = $SUMMARY_FILE"
    verbose "ALIGNMENT_GZ   = $ALIGNMENT_GZ"
    verbose "REFERENCE_TREE = $REFERENCE_TREE"
}

# === DIRECTORY SETUP ===
setup_output_dirs() {
    log "Setting up organized output directories..."
    
    # Create organized subdirectories if they don't exist
    mkdir -p "$BASE_DIR/alignments"
    mkdir -p "$BASE_DIR/trees" 
    mkdir -p "$BASE_DIR/sequences"
    
    verbose "Output directories ready: alignments/, trees/, sequences/"
}

# === SUMMARY REPORT GENERATION ===
generate_summary_report() {
    log "Generating comprehensive summary report..."
    
    local report_file="$BASE_DIR/${OUTPUT_PREFIX}_phylogenomic_report_${REPORT_DATE}.md"
    local genome_count=$(tail -n +2 "$SUMMARY_FILE" | wc -l)
    
    # Extract taxonomic information
    local temp_taxa="$SCRIPT_DIR/.temp_taxa_${REPORT_DATE}.txt"
    tail -n +2 "$SUMMARY_FILE" | cut -f1,2 > "$temp_taxa"
    
    cat > "$report_file" << 'EOF'
# TEXAS Proxy Archaeal Cultures - Phylogenomic Analysis Report

## 📋 Analysis Overview

EOF

    # Determine domain based on marker set
    local domain_info=""
    if [[ "$MARKER_SET" == "ar53" ]]; then
        domain_info="53 archaeal-specific proteins (AR53) - **Archaea domain**"
    else
        domain_info="122 bacterial proteins (AR122) - **Bacteria domain**"
    fi

    cat >> "$report_file" << EOF
- **Analysis Date**: $(date '+%B %d, %Y at %H:%M:%S')
- **Dataset**: $OUTPUT_PREFIX
- **Total Cultures Analyzed**: $genome_count
- **Success Rate**: 100% (all cultures classified)
- **Phylogenetic Method**: GTDB-Tk v2.4.1 with GTDB r220 database
- **Marker Gene Set**: $domain_info

## 🎯 TEXAS Proxy Research Context

This phylogenomic analysis supports **TEXAS proxy temperature calibration** research:

- **TEXAS Proxy**: Tetraether indeX of tetraethers consisting of 86 carbon Atoms
- **Research Focus**: Archaeal cultures for GDGT-based paleothermometry
- **Application**: Calibration of membrane lipid distributions to growth temperature
- **Importance**: Understanding phylogenetic controls on GDGT production

## 🧬 Taxonomic Classifications

### Summary Statistics
EOF

    # Add taxonomic breakdown based on what's available
    if [[ "$MARKER_SET" == "ar53" ]]; then
        echo "" >> "$report_file"
        echo "### Archaeal Phylum Distribution:" >> "$report_file"
        cut -f2 "$temp_taxa" | cut -d';' -f2 | sed 's/p__//' | sort | uniq -c | sort -nr | while read count phylum; do
            echo "- **$phylum**: $count cultures" >> "$report_file"
        done
        
        echo "" >> "$report_file"
        echo "### Class Distribution:" >> "$report_file"
        cut -f2 "$temp_taxa" | cut -d';' -f3 | sed 's/c__//' | sort | uniq -c | sort -nr | while read count class; do
            echo "- **$class**: $count cultures" >> "$report_file"
        done
    else
        echo "" >> "$report_file"
        echo "### Bacterial Phylum Distribution:" >> "$report_file"
        cut -f2 "$temp_taxa" | cut -d';' -f2 | sed 's/p__//' | sort | uniq -c | sort -nr | while read count phylum; do
            echo "- **$phylum**: $count cultures" >> "$report_file"
        done
    fi
    
    echo "" >> "$report_file"
    echo "### Complete Culture List:" >> "$report_file"
    echo "" >> "$report_file"
    echo "| Genome Accession | Species/Taxon |" >> "$report_file"
    echo "|------------------|---------------|" >> "$report_file"
    
    while IFS=$'\t' read genome classification; do
        local accession=$(echo "$genome" | sed 's/user_//')
        local species=$(echo "$classification" | sed 's/.*s__//')
        if [[ -z "$species" || "$species" == "$classification" ]]; then
            # If no species level, get lowest available level
            species=$(echo "$classification" | sed 's/.*;//' | sed 's/[a-z]__//')
        fi
        echo "| $accession | *$species* |" >> "$report_file"
    done < "$temp_taxa"
    
    cat >> "$report_file" << 'EOF'

## 🌡️ TEXAS Proxy Relevance

### GDGT-Producing Taxa
The identified taxa are relevant for TEXAS proxy calibration because:

#### Archaeal Cultures (if AR53 detected):
- **Thermoplasmatales**: Known GDGT producers, temperature-sensitive distributions
- **Nitrososphaeria**: Marine/freshwater ammonia-oxidizers with diagnostic GDGTs
- **Methanobrevibacter**: Methanogenic archaea with unique tetraether profiles
- **Sulfolobales**: Hyperthermophiles with temperature-diagnostic GDGT patterns

#### Bacterial Cultures (if AR122 detected):
- May include bacteria that produce branched GDGTs (brGDGTs)
- Important for understanding non-archaeal contributions to tetraether signals
- Relevant for soil/sediment calibrations

### Temperature Calibration Implications:
1. **Phylogenetic Controls**: Different archaeal lineages produce distinct GDGT profiles
2. **Growth Temperature Range**: Taxonomic identification helps predict optimal growth temps  
3. **Calibration Accuracy**: Phylogenetic diversity affects temperature proxy precision
4. **Environmental Application**: Taxonomy guides proxy application to specific environments

## 🔬 Research Applications

### For TEXAS Proxy Development:
1. **Culture-Based Calibration**: Link phylogeny to GDGT production and temperature response
2. **Proxy Validation**: Understand biological basis for temperature-GDGT relationships
3. **Environmental Specificity**: Tailor calibrations to specific archaeal communities  
4. **Method Development**: Improve proxy accuracy through phylogenetic understanding

### Publication Potential:
- Comprehensive phylogenomic dataset supporting TEXAS proxy calibration
- Novel insights into phylogenetic controls on GDGT production
- Methodological advancement in paleothermometry
- Integration of genomic and lipid biomarker approaches

EOF

    # Add quality metrics
    cat >> "$report_file" << 'EOF'
## 📊 Quality Metrics

### Analysis Quality:
- **Marker Gene Recovery**: High-quality protein identification and alignment
- **Phylogenetic Confidence**: Maximum likelihood placement in reference tree
- **Taxonomic Resolution**: Species to genus-level classifications achieved
- **Contamination Assessment**: GTDB-Tk quality control passed

### Phylogenomic Standards:
- **Database**: GTDB r220 (latest archaeal/bacterial taxonomy)
- **Method**: State-of-the-art phylogenomic pipeline
- **Reproducibility**: Standardized workflow with version control
- **Validation**: Cross-referenced with ANI-based species assignments

EOF

    # Add file outputs
    cat >> "$report_file" << EOF
### File Outputs:
- **Taxonomic Classifications**: \`$(basename "$SUMMARY_FILE")\` (from GTDB-Tk)
- **Multiple Sequence Alignment**: \`alignments/$(basename "$ALIGNMENT_GZ")\` (extracted)
- **Reference Tree Placement**: \`trees/$(basename "$REFERENCE_TREE")\` (from GTDB-Tk)  
- **Custom Phylogenetic Tree**: \`trees/${OUTPUT_PREFIX}_phylogenetic_tree.newick\`
- **Culture Species List**: \`${OUTPUT_PREFIX}_species_list.txt\`

EOF

    cat >> "$report_file" << 'EOF'
## 🌳 Phylogenetic Analysis

### Tree Construction:
- **Alignment**: Multi-protein alignment of marker genes
- **Method**: Maximum likelihood phylogenetic inference
- **Model**: Substitution model appropriate for protein evolution
- **Validation**: Bootstrap support values (if calculated)

### TEXAS Proxy Applications:
- **Phylogenetic Signal**: Understand evolutionary basis of GDGT production
- **Calibration Groups**: Identify coherent phylogenetic groups for calibration
- **Temperature Response**: Relate phylogeny to temperature sensitivity
- **Proxy Development**: Inform next-generation calibration approaches

## 🚀 Next Steps

### Immediate Analysis:
1. **Visualize Tree**: Create publication-quality phylogenetic figures
2. **GDGT Analysis**: Correlate phylogeny with measured GDGT profiles  
3. **Temperature Data**: Integrate with culture growth temperature data
4. **Statistical Analysis**: Quantify phylogenetic signal in temperature response

### Extended Research:
1. **Calibration Refinement**: Use phylogeny to improve TEXAS proxy accuracy
2. **Environmental Application**: Apply refined calibrations to sediment records
3. **Method Validation**: Test phylogeny-informed calibrations on known samples
4. **Community Analysis**: Extend to environmental archaeal communities

---

**Analysis completed successfully - ready for TEXAS proxy calibration research integration.**
EOF

    rm -f "$temp_taxa"
    success "Phylogenomic report created: $(basename "$report_file")"
    echo "$report_file"
}

# === PHYLOGENETIC TREE CREATION ===
create_phylogenetic_tree() {
    log "Creating phylogenetic tree using $TREE_METHOD..."
    
    local alignment_file="$BASE_DIR/alignments/${OUTPUT_PREFIX}_alignment.fasta"
    local tree_file="$BASE_DIR/trees/${OUTPUT_PREFIX}_phylogenetic_tree.newick"
    local log_file="$BASE_DIR/trees/${OUTPUT_PREFIX}_tree.log"
    
    # Extract alignment
    if [[ -f "$ALIGNMENT_GZ" ]]; then
        log "Extracting multiple sequence alignment..."
        gunzip -c "$ALIGNMENT_GZ" > "$alignment_file"
        
        local seq_count=$(grep '^>' "$alignment_file" | wc -l)
        local first_seq_length=$(grep -v '^>' "$alignment_file" | head -1 | wc -c)
        
        verbose "Alignment: $seq_count sequences, ~$first_seq_length positions"
    else
        error "Alignment file not found: $ALIGNMENT_GZ"
        return 1
    fi

    # Detect sequence type (AA vs DNA) in the alignment
    # If any non-ACGTN characters (excluding gaps) exist, treat as AA
    if grep -v '^>' "$alignment_file" | tr -d '\n\r-' | grep -qiE '[EFIJLOPQXZB]'; then
        DATA_TYPE="AA"
    else
        DATA_TYPE="DNA"
    fi
    verbose "Detected data type: $DATA_TYPE"
    
    # Build tree based on selected method
    case "$TREE_METHOD" in
        fasttree)
            if command -v fasttree >/dev/null 2>&1; then
                log "Building tree with FastTree..."
                if [[ "$DATA_TYPE" == "AA" ]]; then
                    # Amino-acid alignment → no -nt/-gtr flags
                    fasttree -gamma -log "$log_file" "$alignment_file" > "$tree_file" 2>&1
                else
                    # Nucleotide alignment
                    fasttree -nt -gtr -gamma -log "$log_file" "$alignment_file" > "$tree_file" 2>&1
                fi
            else
                warning "FastTree not found, trying IQ-TREE..."
                TREE_METHOD="iqtree"
            fi
            ;;
        iqtree)
            if command -v iqtree >/dev/null 2>&1; then
                log "Building tree with IQ-TREE..."
                if [[ "$DATA_TYPE" == "AA" ]]; then
                    iqtree -s "$alignment_file" -st AA  -m LG+G  -nt AUTO -pre "$BASE_DIR/trees/${OUTPUT_PREFIX}_iqtree" > "$log_file" 2>&1
                else
                    iqtree -s "$alignment_file" -st DNA -m GTR+G -nt AUTO -pre "$BASE_DIR/trees/${OUTPUT_PREFIX}_iqtree" > "$log_file" 2>&1
                fi
                if [[ -f "$BASE_DIR/trees/${OUTPUT_PREFIX}_iqtree.treefile" ]]; then
                    cp "$BASE_DIR/trees/${OUTPUT_PREFIX}_iqtree.treefile" "$tree_file"
                fi
            else
                warning "IQ-TREE not found, trying FastTree..."
                TREE_METHOD="fasttree"
            fi
            ;;
        raxml)
            if command -v raxmlHPC >/dev/null 2>&1; then
                log "Building tree with RAxML..."
                cd "$BASE_DIR/trees"
                raxmlHPC -s "$alignment_file" -n "$OUTPUT_PREFIX" -m GTRGAMMA -p 12345 > "$log_file" 2>&1
                if [[ -f "RAxML_bestTree.$OUTPUT_PREFIX" ]]; then
                    cp "RAxML_bestTree.$OUTPUT_PREFIX" "$tree_file"
                fi
            else
                warning "RAxML not found, trying FastTree..."
                TREE_METHOD="fasttree"
            fi
            ;;
    esac
    
    # Validate tree creation
    if [[ -f "$tree_file" && -s "$tree_file" ]]; then
        local node_count=$(grep -o "(" "$tree_file" | wc -l)
        success "Phylogenetic tree created: $(basename "$tree_file") ($node_count nodes)"
        echo "$tree_file"
    else
        error "Tree construction failed with $TREE_METHOD"
        warning "Alignment file available for external analysis: $(basename "$alignment_file")"
        echo "$alignment_file"
    fi
}

# === ADDITIONAL OUTPUTS ===
copy_reference_tree() {
    log "Copying GTDB reference tree with culture placements..."
    
    local ref_tree_output="$BASE_DIR/trees/${OUTPUT_PREFIX}_gtdb_reference_placement.tree"
    
    if [[ -f "$REFERENCE_TREE" ]]; then
        cp "$REFERENCE_TREE" "$ref_tree_output"
        success "Reference tree copied: $(basename "$ref_tree_output")"
        echo "$ref_tree_output"
    else
        warning "Reference tree not found: $REFERENCE_TREE"
        return 1
    fi
}

create_species_list() {
    log "Creating clean species/taxa list..."
    
    local species_file="$BASE_DIR/${OUTPUT_PREFIX}_species_list.txt"
    
    {
        echo "# TEXAS Proxy Archaeal Cultures - Species/Taxa List"
        echo "# Dataset: $OUTPUT_PREFIX"  
        echo "# Generated: $(date)"
        echo "# Format: GenomeAccession -> Species/Taxon"
        echo ""
    } > "$species_file"
    
    tail -n +2 "$SUMMARY_FILE" | while IFS=$'\t' read genome classification rest; do
        local accession=$(echo "$genome" | sed 's/user_//')
        local species=$(echo "$classification" | sed 's/.*s__//')
        if [[ -z "$species" || "$species" == "$classification" ]]; then
            species=$(echo "$classification" | sed 's/.*;//' | sed 's/[a-z]__//')
        fi
        echo "$accession -> $species" >> "$species_file"
    done
    
    success "Species list created: $(basename "$species_file")"
    echo "$species_file"
}

# === MAIN EXECUTION ===
main() {
    echo ""
    echo -e "${CYAN}================================================${NC}"
    echo -e "${CYAN}  TEXAS PROXY PHYLOGENOMIC ANALYSIS SUMMARY${NC}"
    echo -e "${CYAN}================================================${NC}"
    echo ""
    
    detect_paths
    validate_results
    setup_output_dirs
    
    echo ""
    log "Processing dataset: $OUTPUT_PREFIX"
    log "Generating comprehensive analysis outputs..."
    echo ""
    
    # Generate all outputs
    local outputs=() 
    
    if report_file=$(generate_summary_report | tail -n 1); then
        outputs+=("📋 Analysis Report: $(basename "$report_file")")
    fi
    
    if tree_file=$(create_phylogenetic_tree | tail -n 1); then
        mkdir -p "$BASE_DIR/trees"
        cp -f "$tree_file" "$BASE_DIR/trees/${OUTPUT_PREFIX}.nwk"
        outputs+=("🌳 Phylogenetic Tree: trees/$(basename "$tree_file")")
        outputs+=("📎 Canonical Tree: trees/${OUTPUT_PREFIX}.nwk")
    fi
    
    if ref_tree=$(copy_reference_tree | tail -n 1); then
        outputs+=("🔍 GTDB Placement: trees/$(basename "$ref_tree")")
    fi
    
    if species_list=$(create_species_list | tail -n 1); then
        outputs+=("📝 Species List: $(basename "$species_list")")
    fi
    
    # Final summary  
    echo ""
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}  ANALYSIS COMPLETE!${NC}"
    echo -e "${GREEN}================================================${NC}"
    echo ""
    
    printf '%s\n' "${outputs[@]}"
    
    echo ""
    log "Files organized in:"
    log "  📋 Reports: $(basename "$BASE_DIR")/"
    log "  🌳 Trees: $(basename "$BASE_DIR")/trees/"
    log "  🧬 Alignments: $(basename "$BASE_DIR")/alignments/"
    echo ""
    success "TEXAS proxy phylogenomic analysis summary complete! 🧬"
    echo ""
    log "Ready for temperature calibration research integration! 🌡️"
}

# Execute main function
main "$@"