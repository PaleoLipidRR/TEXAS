#!/bin/bash

# TEXAS Phylo Directory Cleanup and Organization Script
# Save as: data/phylo/cleanup_phylo_directory.sh
# Usage: ./cleanup_phylo_directory.sh

set -euo pipefail

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

# Get current directory
PHYLO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log "Starting TEXAS phylo directory cleanup..."
log "Working in: $PHYLO_DIR"

# Create organized directory structure
log "Creating organized directory structure..."

mkdir -p "$PHYLO_DIR/scripts"
mkdir -p "$PHYLO_DIR/reports" 
mkdir -p "$PHYLO_DIR/logs"
mkdir -p "$PHYLO_DIR/data/species_lists"
mkdir -p "$PHYLO_DIR/data/genome_lists"
mkdir -p "$PHYLO_DIR/results"
mkdir -p "$PHYLO_DIR/alignments"  # Keep existing
mkdir -p "$PHYLO_DIR/trees"       # Keep existing  
mkdir -p "$PHYLO_DIR/sequences"   # Keep existing

# Ensure key subdirectories exist
mkdir -p "$PHYLO_DIR/results/gtdbtk_outputs"
mkdir -p "$PHYLO_DIR/results/temp"

success "Directory structure created"

# Move files to organized locations
log "Organizing existing files..."

# 1. SCRIPTS
echo "📝 Moving scripts..."
for script in *.py *.sh; do
    if [[ -f "$script" && "$script" != "cleanup_phylo_directory.sh" ]]; then
        if [[ ! -f "scripts/$script" ]]; then
            mv "$script" "scripts/"
            echo "  → scripts/$script"
        fi
    fi
done

# 2. REPORTS  
echo "📋 Moving reports..."
for report in *.txt *.md; do
    if [[ -f "$report" && "$report" =~ (report|analysis|summary) ]]; then
        if [[ ! -f "reports/$report" ]]; then
            mv "$report" "reports/"
            echo "  → reports/$report"
        fi
    fi
done

# 3. LOGS
echo "📊 Moving logs..."  
for log_file in *.log; do
    if [[ -f "$log_file" ]]; then
        if [[ ! -f "logs/$log_file" ]]; then
            mv "$log_file" "logs/"
            echo "  → logs/$log_file"
        fi
    fi
done

# 4. SPECIES LISTS
echo "🧬 Moving species lists..."
for species_file in species_list*.txt *species*.txt; do
    if [[ -f "$species_file" ]]; then
        if [[ ! -f "data/species_lists/$species_file" ]]; then
            mv "$species_file" "data/species_lists/"
            echo "  → data/species_lists/$species_file"
        fi
    fi
done

# 5. GENOME LISTS
echo "🧬 Moving genome lists..."
for genome_file in genome_list*.txt *genome*.txt; do
    if [[ -f "$genome_file" ]]; then
        if [[ ! -f "data/genome_lists/$genome_file" ]]; then
            mv "$genome_file" "data/genome_lists/"
            echo "  → data/genome_lists/$genome_file"
        fi
    fi
done

# 6. GTDB-TK OUTPUTS
echo "🔬 Moving GTDB-Tk outputs..."
if [[ -d "genome_tree_output" ]]; then
    if [[ ! -d "results/gtdbtk_outputs/genome_tree_output" ]]; then
        mv "genome_tree_output" "results/gtdbtk_outputs/"
        echo "  → results/gtdbtk_outputs/genome_tree_output"
    fi
fi

# 7. SCRATCH/TEMP
echo "🗑️  Moving temporary files..."
if [[ -d "scratch" ]]; then
    if [[ ! -d "results/temp/scratch" ]]; then
        mv "scratch" "results/temp/"
        echo "  → results/temp/scratch"
    fi
fi

# 8. DATABASE (if moved here accidentally)
if [[ -d "release220" ]]; then
    warning "Found GTDB database directory 'release220' - consider moving to /gtdb or separate location"
    echo "  Database directories should typically be in system locations like /gtdb"
fi

success "File organization complete"

# Create documentation
log "Creating directory documentation..."

cat > "$PHYLO_DIR/README_DIRECTORY_STRUCTURE.md" << 'EOF'
# TEXAS Phylo Directory Structure

## 📁 Organization

### Core Analysis Directories
- **`alignments/`** - Multiple sequence alignments (MSA files)
- **`trees/`** - Phylogenetic trees (Newick, other formats)  
- **`sequences/`** - Raw sequence files, FASTA files

### Scripts and Code
- **`scripts/`** - All Python and Bash scripts
  - Phylogenetic analysis scripts
  - Data processing scripts
  - Pipeline scripts

### Data Files
- **`data/`** - Input data and lists
  - `genome_lists/` - NCBI accession lists
  - `species_lists/` - Species/taxa lists

### Results and Outputs  
- **`results/`** - Analysis results
  - `gtdbtk_outputs/` - GTDB-Tk classification results
  - `temp/` - Temporary files and scratch directories

### Documentation
- **`reports/`** - Analysis reports and summaries
- **`logs/`** - Pipeline logs and debug files

## 🎯 TEXAS Proxy Context

This directory contains phylogenomic analyses supporting TEXAS proxy temperature calibration research:

- **Purpose**: Understanding phylogenetic controls on GDGT production
- **Organisms**: Archaeal cultures for temperature calibration
- **Methods**: GTDB-Tk classification, phylogenetic tree construction
- **Applications**: Paleothermometry and climate reconstruction

## 🔄 Workflow

1. **Input**: Genome accession lists in `data/genome_lists/`
2. **Processing**: Scripts in `scripts/` directory
3. **Analysis**: GTDB-Tk results in `results/gtdbtk_outputs/`
4. **Outputs**: Trees in `trees/`, alignments in `alignments/`
5. **Documentation**: Reports in `reports/` directory

## 📊 File Types

- **`.newick`, `.tree`** → `trees/`
- **`.fasta`, `.msa`** → `alignments/`  
- **`.py`, `.sh`** → `scripts/`
- **`.txt`, `.md` reports** → `reports/`
- **`.log`** → `logs/`
- **GTDB-Tk outputs** → `results/gtdbtk_outputs/`

---

**Last updated**: $(date)
**Purpose**: TEXAS proxy phylogenomic analysis organization
EOF

success "Documentation created: README_DIRECTORY_STRUCTURE.md"

# Create .gitignore if it doesn't exist
if [[ ! -f "$PHYLO_DIR/.gitignore" ]]; then
    log "Creating .gitignore..."
    cat > "$PHYLO_DIR/.gitignore" << 'EOF'
# Temporary files
*.tmp
*.temp
*~

# Logs (but keep structure)
logs/*.log
!logs/.gitkeep

# Temporary results  
results/temp/*
!results/temp/.gitkeep

# Large database files (should be in system location)
release*/
*.msh
*.db

# OS files
.DS_Store
Thumbs.db

# Backup files
*.backup
*.bak
EOF

    # Create .gitkeep files to preserve directory structure
    touch "$PHYLO_DIR/logs/.gitkeep"
    touch "$PHYLO_DIR/results/temp/.gitkeep"
    
    success "Git configuration created"
fi

# Show final structure
log "Final directory structure:"
echo ""
tree -L 3 "$PHYLO_DIR" 2>/dev/null || {
    echo "Directory structure (tree command not available):"
    find "$PHYLO_DIR" -type d | head -20 | sed 's/^/  /'
}

echo ""
success "TEXAS phylo directory cleanup complete! 🧬"
log "Directory is now organized for your temperature calibration research"

echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Review the organized structure"
echo "2. Update script paths in your workflows" 
echo "3. Consider updating build_genome_tree.sh to use organized structure"
echo "4. Add any missing files to appropriate directories"