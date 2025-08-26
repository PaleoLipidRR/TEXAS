#!/usr/bin/env python3
from Bio import Entrez, SeqIO
import sys

Entrez.email = "rattanasriampaipong.r@gmail.com"

# Load species from file
species_data = {}
try:
    with open('/app/data/phylo/species_list.txt', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                parts = line.split(',')
                if len(parts) == 2:
                    species_data[parts[0]] = parts[1]
    print(f"Loaded {len(species_data)} species from species_list.txt")
except FileNotFoundError:
    print("species_list.txt not found, using default species")
    species_data = {
        "Nitrosopumilus_maritimus": "NR_102904.1",
        "Methanobrevibacter_smithii": "NR_044796.1", 
        "Methanosarcina_barkeri": "NR_028163.1",
        "Pyrococcus_furiosus": "NR_029144.1",
        "Sulfolobus_solfataricus": "NR_028164.1",
        "Escherichia_coli": "NR_024570.1"
    }

sequences = []
failed = []

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

if len(sequences) < 5:
    print(f"ERROR: Only downloaded {len(sequences)} sequences, need at least 5")
    sys.exit(1)

with open("sequences/archaeal_16S.fasta", 'w') as f:
    SeqIO.write(sequences, f, "fasta")

print(f"Successfully downloaded {len(sequences)} sequences")
if failed:
    print(f"Failed downloads: {', '.join(failed)}")
