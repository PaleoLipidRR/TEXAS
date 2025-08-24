#!/usr/bin/env python3
"""
Simple Archaeal Phylogenetic Analysis - works around permission issues
"""

import os
import subprocess
from Bio import Entrez, SeqIO
from Bio.SeqRecord import SeqRecord
import pandas as pd

# Set email for NCBI
Entrez.email = 'rattanasriampaipong.r@gmail.com'

def download_sequences():
    """Download representative sequences"""
    
    # Key GDGT-producing archaeal groups
    target_groups = {
        'Nitrosopumilus_maritimus': 'NR_102904.1',  # 16S rRNA gene
        'Nitrososphaera_viennensis': 'NR_109709.1',
        'Methanobrevibacter_smithii': 'NR_044796.1', 
        'Methanosarcina_barkeri': 'NR_028163.1',
        'Pyrococcus_furiosus': 'NR_029144.1',
        'Sulfolobus_solfataricus': 'NR_028164.1',
        'Escherichia_coli': 'NR_024570.1',  # Bacterial outgroup
    }
    
    sequences = []
    print("Downloading 16S rRNA sequences...")
    
    for species, accession in target_groups.items():
        try:
            print(f"Fetching {species}...")
            handle = Entrez.efetch(db="nucleotide", id=accession, rettype="fasta", retmode="text")
            record = SeqIO.read(handle, "fasta")
            handle.close()
            
            # Clean up the record
            record.id = species
            record.description = species.replace('_', ' ')
            sequences.append(record)
            print(f"✓ {species}")
            
        except Exception as e:
            print(f"✗ Failed {species}: {e}")
    
    # Save sequences to current directory
    output_file = "archaeal_16S.fasta"
    with open(output_file, 'w') as f:
        SeqIO.write(sequences, f, "fasta")
    
    print(f"\n✓ Saved {len(sequences)} sequences to {output_file}")
    return output_file

def align_sequences(input_file):
    """Align with MAFFT"""
    output_file = "archaeal_16S_aligned.fasta"
    
    print("Running MAFFT alignment...")
    cmd = ['mafft', '--auto', input_file]
    
    with open(output_file, 'w') as outfile:
        result = subprocess.run(cmd, stdout=outfile, stderr=subprocess.PIPE, text=True)
    
    if result.returncode == 0:
        print(f"✓ Alignment saved to {output_file}")
        return output_file
    else:
        print(f"✗ MAFFT failed: {result.stderr}")
        return None

def build_tree(alignment_file):
    """Build tree with IQ-TREE"""
    output_prefix = "archaeal_tree"
    
    print("Building tree with IQ-TREE...")
    cmd = [
        'iqtree', 
        '-s', alignment_file,
        '-pre', output_prefix,
        '-m', 'MFP',  # Model selection
        '-bb', '1000',  # Bootstrap
        '-redo'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        tree_file = output_prefix + '.treefile'
        print(f"✓ Tree saved to {tree_file}")
        return tree_file
    else:
        print(f"✗ IQ-TREE failed: {result.stderr}")
        return None

def visualize_tree(tree_file):
    """Simple tree visualization"""
    try:
        from ete3 import Tree, TreeStyle
        
        tree = Tree(tree_file)
        
        # Root on E. coli
        outgroup = tree.search_nodes(name="Escherichia_coli")[0]
        tree.set_outgroup(outgroup)
        
        # Simple circular tree
        ts = TreeStyle()
        ts.mode = "c"
        ts.show_leaf_name = True
        ts.show_branch_length = True
        ts.show_branch_support = True
        
        output_image = "archaeal_tree.png"
        tree.render(output_image, tree_style=ts, dpi=300)
        print(f"✓ Tree image saved to {output_image}")
        
        return output_image
        
    except Exception as e:
        print(f"✗ Visualization failed: {e}")
        print("Tree file is available for manual visualization")
        return None

def main():
    """Run the complete analysis"""
    print("Simple Archaeal Phylogenetic Analysis")
    print("="*50)
    
    # Step 1: Download sequences
    fasta_file = download_sequences()
    if not fasta_file:
        return
    
    # Step 2: Align
    alignment_file = align_sequences(fasta_file)
    if not alignment_file:
        return
        
    # Step 3: Build tree
    tree_file = build_tree(alignment_file)
    if not tree_file:
        return
        
    # Step 4: Visualize
    image_file = visualize_tree(tree_file)
    
    print("="*50)
    print("Analysis completed!")
    print(f"Files created:")
    print(f"  - Sequences: {fasta_file}")
    print(f"  - Alignment: {alignment_file}")  
    print(f"  - Tree: {tree_file}")
    if image_file:
        print(f"  - Image: {image_file}")

if __name__ == "__main__":
    main()
