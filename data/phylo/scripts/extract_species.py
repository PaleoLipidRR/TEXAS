#!/usr/bin/env python3
"""
Extract species list from TEXAS experimental data for phylogenetic analysis
"""

import pandas as pd
import numpy as np
from Bio import Entrez
import time
import re

def load_and_examine_data(csv_file):
    """Load CSV and examine taxonomic information"""
    
    df = pd.read_csv(csv_file)
    
    print("TEXAS EXPERIMENTAL DATA OVERVIEW")
    print("=" * 50)
    print(f"Total samples: {len(df)}")
    print(f"Temperature range: {df['Temperature'].min()}°C - {df['Temperature'].max()}°C")
    print(f"TEX86 range: {df['TEX86'].min():.3f} - {df['TEX86'].max():.3f}")
    print()
    
    return df

def extract_unique_species(df):
    """Extract unique species from taxonomic columns"""
    
    print("EXTRACTING SPECIES FROM YOUR DATA")
    print("=" * 40)
    
    # Priority order: use best available taxonomic info
    species_sources = [
        ('GTDB_species', 'GTDB Species'),
        ('NCBI_species', 'NCBI Species'), 
        ('GTDB_genus', 'GTDB Genus'),
        ('NCBI_genus', 'NCBI Genus'),
        ('Strains', 'Strain Info')
    ]
    
    species_data = []
    
    for col, description in species_sources:
        if col in df.columns:
            unique_vals = df[col].dropna().unique()
            print(f"\n{description} ({col}):")
            print(f"  Unique values: {len(unique_vals)}")
            
            # Show examples
            examples = list(unique_vals[:8])
            for ex in examples:
                print(f"    • {ex}")
            
            if len(unique_vals) > 8:
                print(f"    ... and {len(unique_vals) - 8} more")
            
            # Store for analysis
            for val in unique_vals:
                species_data.append({
                    'name': val,
                    'source': col,
                    'type': description,
                    'sample_count': len(df[df[col] == val])
                })
    
    return pd.DataFrame(species_data)

def clean_species_names(species_df):
    """Clean and standardize species names"""
    
    print(f"\nCLEANING SPECIES NAMES")
    print("=" * 30)
    
    cleaned_species = []
    
    for _, row in species_df.iterrows():
        name = str(row['name'])
        
        # Skip if obviously not a species name
        if any(skip in name.lower() for skip in ['unknown', 'unidentified', 'uncultured', 'nan', 'none']):
            continue
            
        # Clean the name
        cleaned_name = name.strip()
        
        # Convert to standard format if it looks like a species name
        if ' ' in cleaned_name and not cleaned_name.startswith('Candidatus'):
            # Standard genus species format
            parts = cleaned_name.split()[:2]  # Take first two parts
            cleaned_name = f"{parts[0]}_{parts[1]}"
        elif cleaned_name.startswith('Candidatus '):
            # Handle Candidatus names
            cleaned_name = cleaned_name.replace('Candidatus ', 'Candidatus_').replace(' ', '_')
        else:
            # Single name (genus level)
            cleaned_name = cleaned_name.replace(' ', '_')
        
        # Remove problematic characters
        cleaned_name = re.sub(r'[^a-zA-Z0-9_]', '', cleaned_name)
        
        if len(cleaned_name) > 3:  # Skip very short names
            cleaned_species.append({
                'original_name': name,
                'cleaned_name': cleaned_name,
                'source': row['source'],
                'sample_count': row['sample_count']
            })
    
    # Remove duplicates, keeping the one with most samples
    cleaned_df = pd.DataFrame(cleaned_species)
    if not cleaned_df.empty:
        cleaned_df = cleaned_df.groupby('cleaned_name').agg({
            'original_name': 'first',
            'source': 'first', 
            'sample_count': 'sum'
        }).reset_index()
    
    print(f"✓ Cleaned {len(cleaned_df)} unique species names")
    return cleaned_df

def search_ncbi_accessions(species_list, email="your.email@domain.com", max_species=15):
    """Search for NCBI accession numbers for species"""
    
    print(f"\nSEARCHING NCBI FOR 16S rRNA SEQUENCES")
    print("=" * 45)
    print(f"Email: {email}")
    print(f"Species to search: {min(len(species_list), max_species)}")
    print()
    
    Entrez.email = email
    results = []
    
    # Sort by sample count and take top species
    top_species = species_list.nlargest(max_species, 'sample_count')
    
    for i, (_, row) in enumerate(top_species.iterrows(), 1):
        species = row['cleaned_name']
        original = row['original_name']
        
        print(f"[{i}/{len(top_species)}] Searching: {species}")
        
        try:
            # Try different search terms
            search_terms = [
                f"{species.replace('_', ' ')} 16S ribosomal RNA",
                f"{species.replace('_', ' ')} 16S rRNA",
                f"{species.replace('_', ' ')} small subunit ribosomal RNA"
            ]
            
            best_result = None
            
            for search_term in search_terms:
                try:
                    handle = Entrez.esearch(db="nucleotide", term=search_term, retmax=3)
                    search_results = Entrez.read(handle)
                    handle.close()
                    
                    if search_results['IdList']:
                        # Get details of first result
                        seq_id = search_results['IdList'][0]
                        handle = Entrez.esummary(db="nucleotide", id=seq_id)
                        summary = Entrez.read(handle)[0]
                        handle.close()
                        
                        title = summary.get('Title', '')
                        accession = summary.get('Caption', seq_id)
                        
                        # Prefer complete genomes or 16S sequences
                        if '16S' in title or 'ribosomal RNA' in title:
                            best_result = {
                                'species': species,
                                'original_name': original,
                                'accession': accession,
                                'title': title[:80] + ('...' if len(title) > 80 else ''),
                                'sample_count': row['sample_count'],
                                'search_term': search_term
                            }
                            break
                    
                    time.sleep(0.3)  # Be nice to NCBI
                    
                except Exception as e:
                    print(f"    Search failed for '{search_term}': {e}")
                    continue
            
            if best_result:
                results.append(best_result)
                print(f"    ✓ Found: {best_result['accession']}")
                print(f"      {best_result['title']}")
            else:
                print(f"    ✗ No suitable sequences found")
                # Still add it for manual lookup
                results.append({
                    'species': species,
                    'original_name': original,
                    'accession': 'MANUAL_LOOKUP_NEEDED',
                    'title': 'No automatic match found',
                    'sample_count': row['sample_count'],
                    'search_term': 'None'
                })
            
            print()
            
        except Exception as e:
            print(f"    ✗ Error: {e}")
            print()
    
    return pd.DataFrame(results)

def create_species_list_file(accession_df, output_file="species_list_from_data.txt"):
    """Create species list file for phylogenetic analysis"""
    
    print(f"CREATING SPECIES LIST FILE")
    print("=" * 35)
    
    with open(output_file, 'w') as f:
        f.write("# Species list extracted from TEXAS experimental data\n")
        f.write("# Format: species_name,ncbi_accession_number\n")
        f.write("# Generated automatically from culture_mesocosm_combined_rev_030425.csv\n")
        f.write("\n")
        f.write("# === SPECIES FROM YOUR EXPERIMENTAL DATA ===\n")
        
        for _, row in accession_df.iterrows():
            if row['accession'] != 'MANUAL_LOOKUP_NEEDED':
                f.write(f"{row['species']},{row['accession']}\n")
            else:
                f.write(f"# {row['species']},MANUAL_LOOKUP_NEEDED  # Search manually\n")
        
        f.write("\n# === REFERENCE SPECIES (optional) ===\n")
        f.write("# Add reference species for comparison if needed\n")
        f.write("# Nitrosopumilus_maritimus,NR_102904.1\n")
        f.write("# Candidatus_Nitrosopelagicus_brevis,NR_118077.1\n")
        f.write("\n# === BACTERIAL OUTGROUP (required) ===\n")
        f.write("Escherichia_coli,NR_024570.1\n")
    
    print(f"✓ Species list saved to: {output_file}")
    print(f"✓ Found accessions for {len(accession_df[accession_df['accession'] != 'MANUAL_LOOKUP_NEEDED'])} species")
    print(f"✓ Manual lookup needed for {len(accession_df[accession_df['accession'] == 'MANUAL_LOOKUP_NEEDED'])} species")
    
    return output_file

def create_summary_report(df, species_df, accession_df, output_file="species_extraction_report.txt"):
    """Create summary report"""
    
    with open(output_file, 'w') as f:
        f.write("SPECIES EXTRACTION REPORT - TEXAS PROJECT\n")
        f.write("="*50 + "\n")
        f.write(f"Date: {pd.Timestamp.now()}\n")
        f.write(f"Source: culture_mesocosm_combined_rev_030425.csv\n\n")
        
        f.write("DATA OVERVIEW:\n")
        f.write(f"  Total samples: {len(df)}\n")
        f.write(f"  Temperature range: {df['Temperature'].min()}°C - {df['Temperature'].max()}°C\n")
        f.write(f"  TEX86 range: {df['TEX86'].min():.3f} - {df['TEX86'].max():.3f}\n\n")
        
        f.write("SPECIES IDENTIFICATION:\n")
        f.write(f"  Unique species found: {len(species_df)}\n")
        f.write(f"  Accessions found: {len(accession_df[accession_df['accession'] != 'MANUAL_LOOKUP_NEEDED'])}\n")
        f.write(f"  Manual lookup needed: {len(accession_df[accession_df['accession'] == 'MANUAL_LOOKUP_NEEDED'])}\n\n")
        
        f.write("TOP SPECIES BY SAMPLE COUNT:\n")
        for _, row in accession_df.head(10).iterrows():
            f.write(f"  {row['species']}: {row['sample_count']} samples\n")
        
        f.write("\nNEXT STEPS:\n")
        f.write("1. Review species_list_from_data.txt\n")
        f.write("2. Manually find accessions for species marked as 'MANUAL_LOOKUP_NEEDED'\n")
        f.write("3. Run phylogenetic analysis with your actual experimental species\n")
        f.write("4. Compare phylogenetic context with your temperature calibration data\n")
    
    print(f"✓ Summary report saved to: {output_file}")

def main(csv_file="culture_mesocosm_combined_rev_030425.csv", email="rattanasriampaipong.r@gmail.com"):
    """Main extraction pipeline"""
    
    print("EXTRACTING SPECIES FROM TEXAS EXPERIMENTAL DATA")
    print("="*55)
    print()
    
    # Load data
    df = load_and_examine_data(csv_file)
    
    # Extract species
    species_df = extract_unique_species(df)
    
    # Clean names
    cleaned_df = clean_species_names(species_df)
    
    if len(cleaned_df) == 0:
        print("❌ No valid species names found in the data")
        return
    
    # Search NCBI
    print(f"Top species in your data (by sample count):")
    for i, (_, row) in enumerate(cleaned_df.head(10).iterrows(), 1):
        print(f"  {i}. {row['cleaned_name']} ({row['sample_count']} samples)")
    print()
    
    accession_df = search_ncbi_accessions(cleaned_df, email=email)
    
    # Create files
    species_file = create_species_list_file(accession_df)
    create_summary_report(df, cleaned_df, accession_df)
    
    print("\n" + "="*55)
    print("EXTRACTION COMPLETE!")
    print("="*55)
    print(f"✓ Species list: species_list_from_data.txt")
    print(f"✓ Report: species_extraction_report.txt")
    print()
    print("Next: Run phylogenetic analysis with your species:")
    print("  ./build_custom_tree.sh -s species_list_from_data.txt")
    
    return species_file, accession_df

if __name__ == "__main__":
    species_file, results = main()
