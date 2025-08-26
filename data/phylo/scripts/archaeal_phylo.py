#!/usr/bin/env python3
"""
Archaeal Phylogenetic Tree Builder for TEXAS GDGT Project
Build phylogenetic tree of GDGT-producing archaea
"""

import os
import subprocess
from Bio import Entrez, SeqIO
from Bio.SeqRecord import SeqRecord
from Bio.Seq import Seq
import pandas as pd
from ete3 import Tree, TreeStyle, NodeStyle, faces, AttrFace
import matplotlib.pyplot as plt

class ArchaealPhylogeny:
    def __init__(self, email, output_dir="."):
        """
        Initialize archaeal phylogeny builder
        
        Args:
            email (str): Email for NCBI Entrez queries
            output_dir (str): Output directory for files
        """
        self.email = email
        Entrez.email = email
        self.output_dir = output_dir
        
        # Create output directories
        for subdir in ['sequences', 'alignments', 'trees']:
            os.makedirs(os.path.join(output_dir, subdir), exist_ok=True)
    
    def get_representative_sequences(self):
        """
        Download representative 16S rRNA sequences for major archaeal groups
        Focus on GDGT-producing archaea
        """
        
        # Key GDGT-producing archaeal groups with representative species
        target_groups = {
            # Thaumarchaeota (major GDGT producers)
            'Nitrosopumilus_maritimus': 'CP000866.1',  # Marine ammonia oxidizer
            'Candidatus_Nitrosopelagicus_brevis': 'CP011072.1',  # Pelagic AOA
            'Nitrososphaera_viennensis': 'CP007536.1',  # Soil AOA
            
            # Euryarchaeota 
            'Methanobrevibacter_smithii': 'CP000678.1',  # Human gut methanogen
            'Methanosarcina_barkeri': 'CP000099.1',  # Versatile methanogen
            'Thermococcus_kodakarensis': 'AP006878.1',  # Hyperthermophile
            
            # Crenarchaeota (thermophiles, branched GDGTs)
            'Pyrococcus_furiosus': 'AE009950.1',  # Hyperthermophile
            'Sulfolobus_solfataricus': 'AE006641.1',  # Thermoacidophile
            'Thermoproteus_tenax': 'NR_028163.1',  # Thermophile
            
            # Aigarchaeota (newly recognized GDGT producers)
            'Candidatus_Caldalkalibacillus_thermarum': 'CP001740.1',
            
            # Outgroup (Bacteria for rooting)
            'Escherichia_coli': 'U00096.3',  # Well-known bacterial outgroup
        }
        
        sequences = []
        
        print("Downloading representative 16S rRNA sequences...")
        
        for species, accession in target_groups.items():
            try:
                print(f"Fetching {species} ({accession})...")
                
                # Download sequence
                handle = Entrez.efetch(db="nucleotide", id=accession, rettype="fasta", retmode="text")
                record = SeqIO.read(handle, "fasta")
                handle.close()
                
                # Create clean ID
                clean_id = species.replace('_', ' ').replace('Candidatus ', 'Ca. ')
                record.id = species
                record.description = clean_id
                
                sequences.append(record)
                print(f"✓ Downloaded {clean_id}")
                
            except Exception as e:
                print(f"✗ Failed to download {species}: {e}")
                continue
        
        # Save sequences
        output_file = os.path.join(self.output_dir, 'sequences', 'archaeal_16S.fasta')
        with open(output_file, 'w') as f:
            SeqIO.write(sequences, f, "fasta")
        
        print(f"\nSaved {len(sequences)} sequences to {output_file}")
        return output_file
    
    def align_sequences(self, fasta_file):
        """
        Align sequences using MAFFT
        """
        input_file = fasta_file
        output_file = os.path.join(self.output_dir, 'alignments', 'archaeal_16S_aligned.fasta')
        
        print("Aligning sequences with MAFFT...")
        
        # Run MAFFT alignment
        cmd = [
            'mafft',
            '--auto',  # Automatically choose strategy
            '--thread', '4',  # Use 4 threads
            input_file
        ]
        
        with open(output_file, 'w') as outfile:
            result = subprocess.run(cmd, stdout=outfile, stderr=subprocess.PIPE, text=True)
        
        if result.returncode == 0:
            print(f"✓ Alignment completed: {output_file}")
            return output_file
        else:
            print(f"✗ Alignment failed: {result.stderr}")
            return None
    
    def build_tree(self, alignment_file):
        """
        Build phylogenetic tree using IQ-TREE
        """
        output_prefix = os.path.join(self.output_dir, 'trees', 'archaeal_tree')
        
        print("Building phylogenetic tree with IQ-TREE...")
        
        # Run IQ-TREE
        cmd = [
            'iqtree',
            '-s', alignment_file,
            '-pre', output_prefix,
            '-m', 'MFP',  # ModelFinder Plus - automatically select best model
            '-bb', '1000',  # Ultra-fast bootstrap with 1000 replicates
            '-redo'  # Redo analysis if output files exist
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            tree_file = output_prefix + '.treefile'
            print(f"✓ Tree building completed: {tree_file}")
            return tree_file
        else:
            print(f"✗ Tree building failed: {result.stderr}")
            return None
    
    def visualize_tree(self, tree_file, gdgt_data=None):
        """
        Visualize the phylogenetic tree with optional GDGT data overlay
        
        Args:
            tree_file (str): Path to Newick tree file
            gdgt_data (dict, optional): Dictionary mapping species to GDGT data
        """
        # Load tree
        tree = Tree(tree_file)
        
        # Root the tree on bacterial outgroup
        try:
            outgroup = tree.search_nodes(name="Escherichia_coli")[0]
            tree.set_outgroup(outgroup)
            print("✓ Tree rooted on E. coli outgroup")
        except:
            print("! Could not root tree - using midpoint rooting")
            tree.set_outgroup(tree.get_midpoint_outgroup())
        
        # Style the tree
        ts = TreeStyle()
        ts.show_leaf_name = True
        ts.show_branch_length = True
        ts.show_branch_support = True
        ts.mode = "c"  # Circular mode
        ts.arc_start = -180
        ts.arc_span = 180
        
        # Color code by archaeal groups
        group_colors = {
            'Thaumarchaeota': '#1f77b4',  # Blue
            'Euryarchaeota': '#ff7f0e',   # Orange  
            'Crenarchaeota': '#2ca02c',   # Green
            'Aigarchaeota': '#d62728',    # Red
            'Bacteria': '#7f7f7f'         # Gray
        }
        
        # Assign colors based on taxonomy
        for node in tree.traverse():
            if node.is_leaf():
                # Determine group based on name
                name = node.name.lower()
                if 'nitros' in name:
                    group = 'Thaumarchaeota'
                elif any(x in name for x in ['methano', 'thermococcus']):
                    group = 'Euryarchaeota'
                elif any(x in name for x in ['pyrococcus', 'sulfolobus', 'thermoproteus']):
                    group = 'Crenarchaeota'
                elif 'caldalkalibacillus' in name:
                    group = 'Aigarchaeota'
                elif 'escherichia' in name:
                    group = 'Bacteria'
                else:
                    group = 'Unknown'
                
                # Style node
                nstyle = NodeStyle()
                nstyle["fgcolor"] = group_colors.get(group, '#000000')
                nstyle["size"] = 10
                node.set_style(nstyle)
                
                # Add group label
                group_face = AttrFace("name", fsize=10)
                group_face.fgcolor = group_colors.get(group, '#000000')
                node.add_face(group_face, column=0, position="branch-right")
        
        # Add title
        ts.title.add_face(faces.TextFace("Archaeal Phylogeny for GDGT Analysis", fsize=16), column=0)
        
        # Save tree visualization
        output_image = os.path.join(self.output_dir, 'trees', 'archaeal_tree.png')
        tree.render(output_image, tree_style=ts, dpi=300)
        print(f"✓ Tree visualization saved: {output_image}")
        
        return tree, output_image
    
    def run_full_analysis(self):
        """
        Run the complete phylogenetic analysis pipeline
        """
        print("Starting archaeal phylogenetic analysis for GDGT project...")
        print("="*60)
        
        # Step 1: Download sequences
        fasta_file = self.get_representative_sequences()
        if not fasta_file:
            return None
        
        # Step 2: Align sequences  
        alignment_file = self.align_sequences(fasta_file)
        if not alignment_file:
            return None
            
        # Step 3: Build tree
        tree_file = self.build_tree(alignment_file)
        if not tree_file:
            return None
            
        # Step 4: Visualize tree
        tree, image_file = self.visualize_tree(tree_file)
        
        print("="*60)
        print("Phylogenetic analysis completed successfully!")
        print(f"Tree file: {tree_file}")
        print(f"Tree image: {image_file}")
        
        return {
            'tree_file': tree_file,
            'image_file': image_file,
            'alignment_file': alignment_file,
            'sequences_file': fasta_file
        }

# Example usage
if __name__ == "__main__":
    # Initialize phylogeny builder
    phylo = ArchaealPhylogeny(email="rattanasriampaipong.r@gmail.com")  # Replace with your email
    
    # Run complete analysis
    results = phylo.run_full_analysis()
    
    if results:
        print("\nNext steps:")
        print("1. Examine the tree image to verify relationships")
        print("2. Add your mesocosm/culture sequences to the analysis")
        print("3. Overlay GDGT temperature calibration data")
        print("4. Integrate with your TEXAS Bayesian analysis")
