#!/usr/bin/env python3
"""
Validate and update archaeal species selection for GDGT phylogenetic analysis
Helps identify missing key species and suggests additions
"""

import pandas as pd
from Bio import Entrez
import time

class GDGTSpeciesValidator:
    def __init__(self, email):
        self.email = email
        Entrez.email = email
        
        # Current species in your analysis
        self.current_species = {
            'Nitrosopumilus_maritimus': {
                'accession': 'NR_102904.1',
                'group': 'Thaumarchaeota',
                'gdgt_type': 'Isoprenoid GDGTs (TEX86)',
                'habitat': 'Marine pelagic',
                'importance': 'Major TEX86 producer',
                'temp_range': '4-30°C'
            },
            'Methanobrevibacter_smithii': {
                'accession': 'NR_044796.1',
                'group': 'Euryarchaeota',
                'gdgt_type': 'Limited GDGTs',
                'habitat': 'Human gut',
                'importance': 'Methanogen representative',
                'temp_range': '37°C'
            },
            'Methanosarcina_barkeri': {
                'accession': 'NR_028163.1',
                'group': 'Euryarchaeota',
                'gdgt_type': 'Some GDGTs',
                'habitat': 'Freshwater sediments',
                'importance': 'Versatile methanogen',
                'temp_range': '15-50°C'
            },
            'Pyrococcus_furiosus': {
                'accession': 'NR_029144.1',
                'group': 'Euryarchaeota',
                'gdgt_type': 'Branched GDGTs',
                'habitat': 'Hydrothermal vents',
                'importance': 'Hyperthermophile',
                'temp_range': '70-103°C'
            },
            'Sulfolobus_solfataricus': {
                'accession': 'NR_028164.1',
                'group': 'Crenarchaeota',
                'gdgt_type': 'Branched GDGTs',
                'habitat': 'Volcanic hot springs',
                'importance': 'Thermoacidophile',
                'temp_range': '60-95°C'
            }
        }
        
        # Comprehensive list of GDGT-producing archaea from literature
        self.recommended_species = {
            # Thaumarchaeota - Major TEX86 producers
            'Nitrosopumilus_maritimus': 'NR_102904.1',  # Already included
            'Candidatus_Nitrosopelagicus_brevis': 'NR_118077.1',  # Pelagic AOA
            'Nitrososphaera_viennensis': 'NR_109709.1',  # Soil AOA
            'Candidatus_Nitrososphaera_gargensis': 'NR_102915.1',  # Hot spring AOA
            'Candidatus_Nitrosotenuis_chungbukensis': 'NR_134774.1',  # Freshwater AOA
            
            # Euryarchaeota - Diverse GDGT producers
            'Methanobrevibacter_smithii': 'NR_044796.1',  # Already included
            'Methanosarcina_barkeri': 'NR_028163.1',  # Already included  
            'Methanocaldococcus_jannaschii': 'NR_074173.1',  # Hyperthermophile
            'Thermococcus_kodakarensis': 'NR_074233.1',  # Hyperthermophile
            'Archaeoglobus_fulgidus': 'NR_074254.1',  # Sulfate reducer
            'Methanothermobacter_thermautotrophicus': 'NR_074177.1',  # Thermophile
            
            # Crenarchaeota - Branched GDGT producers
            'Sulfolobus_solfataricus': 'NR_028164.1',  # Already included
            'Pyrococcus_furiosus': 'NR_029144.1',  # Already included (actually Euryarchaeota)
            'Thermoproteus_tenax': 'NR_074152.1',  # Hyperthermophile
            'Caldalkalibacillus_thermarum': 'NR_074268.1',  # Thermophile
            'Thermosphaera_aggregans': 'NR_074260.1',  # Hyperthermophile
            
            # Korarchaeota - Rare, deep-branching
            'Candidatus_Korarchaeum_cryptofilum': 'NR_074235.1',  # Deep branching
            
            # Aigarchaeota - Recently discovered GDGT producers  
            'Candidatus_Caldalkalibacillus_thermarum': 'NR_074268.1',  # Hot spring
        }
    
    def assess_current_coverage(self):
        """Assess how well current species represent GDGT diversity"""
        print("CURRENT SPECIES COVERAGE ASSESSMENT")
        print("=" * 50)
        
        # Group analysis
        groups = {}
        for species, info in self.current_species.items():
            group = info['group']
            if group not in groups:
                groups[group] = []
            groups[group].append(species)
        
        print("Taxonomic Group Coverage:")
        for group, species_list in groups.items():
            print(f"  {group}: {len(species_list)} species")
            for sp in species_list:
                print(f"    - {sp.replace('_', ' ')}")
        
        # GDGT type analysis
        gdgt_types = {}
        for species, info in self.current_species.items():
            gdgt_type = info['gdgt_type']
            if gdgt_type not in gdgt_types:
                gdgt_types[gdgt_type] = []
            gdgt_types[gdgt_type].append(species)
        
        print(f"\nGDGT Production Type Coverage:")
        for gdgt_type, species_list in gdgt_types.items():
            print(f"  {gdgt_type}: {len(species_list)} species")
        
        # Temperature range analysis
        print(f"\nTemperature Range Coverage:")
        for species, info in self.current_species.items():
            print(f"  {species.replace('_', ' ')}: {info['temp_range']}")
        
        return groups, gdgt_types
    
    def identify_gaps(self):
        """Identify important missing species"""
        print("\nGAP ANALYSIS - MISSING IMPORTANT SPECIES")
        print("=" * 50)
        
        gaps = {
            'Thaumarchaeota': [
                ('Candidatus_Nitrosopelagicus_brevis', 'Major marine TEX86 producer'),
                ('Nitrososphaera_viennensis', 'Soil AOA, different habitat'),
                ('Candidatus_Nitrososphaera_gargensis', 'Thermophilic AOA'),
            ],
            'Euryarchaeota_thermophiles': [
                ('Methanocaldococcus_jannaschii', 'Hyperthermophile, deep-sea'),
                ('Thermococcus_kodakarensis', 'Model hyperthermophile'),
                ('Archaeoglobus_fulgidus', 'Sulfate-reducing thermophile'),
            ],
            'Crenarchaeota_expanded': [
                ('Thermoproteus_tenax', 'Different thermophile lineage'),
                ('Thermosphaera_aggregans', 'Hyperthermophile'),
            ],
            'Deep_branching': [
                ('Candidatus_Korarchaeum_cryptofilum', 'Deep-branching archaea'),
            ]
        }
        
        for category, species_list in gaps.items():
            print(f"\n{category.replace('_', ' ').title()}:")
            for species, reason in species_list:
                print(f"  - {species.replace('_', ' ')}: {reason}")
        
        return gaps
    
    def suggest_priority_additions(self):
        """Suggest priority species to add based on scientific importance"""
        print("\nPRIORITY ADDITIONS FOR TEXAS GDGT PROJECT")
        print("=" * 50)
        
        priority_species = [
            {
                'species': 'Candidatus_Nitrosopelagicus_brevis',
                'accession': 'NR_118077.1',
                'priority': 'HIGH',
                'reason': 'Major marine TEX86 producer, complements N. maritimus',
                'gdgt_relevance': 'Primary isoprenoid GDGT producer'
            },
            {
                'species': 'Nitrososphaera_viennensis', 
                'accession': 'NR_109709.1',
                'priority': 'HIGH',
                'reason': 'Soil AOA, different ecological niche than marine AOA',
                'gdgt_relevance': 'Terrestrial GDGT signals'
            },
            {
                'species': 'Thermococcus_kodakarensis',
                'accession': 'NR_074233.1', 
                'priority': 'MEDIUM',
                'reason': 'Well-studied hyperthermophile, model organism',
                'gdgt_relevance': 'High-temperature GDGT production'
            },
            {
                'species': 'Archaeoglobus_fulgidus',
                'accession': 'NR_074254.1',
                'priority': 'MEDIUM', 
                'reason': 'Different metabolism (sulfate reduction), thermophile',
                'gdgt_relevance': 'Branched GDGT production'
            },
            {
                'species': 'Candidatus_Korarchaeum_cryptofilum',
                'accession': 'NR_074235.1',
                'priority': 'LOW',
                'reason': 'Deep-branching archaea, evolutionary perspective',
                'gdgt_relevance': 'Ancestral GDGT characteristics'
            }
        ]
        
        for species_info in priority_species:
            print(f"\n{species_info['priority']} PRIORITY: {species_info['species'].replace('_', ' ')}")
            print(f"  Accession: {species_info['accession']}")
            print(f"  Reason: {species_info['reason']}")
            print(f"  GDGT Relevance: {species_info['gdgt_relevance']}")
        
        return priority_species
    
    def check_accession_validity(self, accession_list):
        """Check if NCBI accession numbers are still valid"""
        print(f"\nVALIDATING NCBI ACCESSION NUMBERS")
        print("=" * 50)
        
        valid_accessions = {}
        invalid_accessions = []
        
        for species, accession in accession_list.items():
            try:
                print(f"Checking {species} ({accession})...")
                handle = Entrez.esummary(db="nucleotide", id=accession)
                record = Entrez.read(handle)[0]
                handle.close()
                
                if 'error' in record:
                    invalid_accessions.append((species, accession, record['error']))
                    print(f"  ✗ INVALID: {record['error']}")
                else:
                    valid_accessions[species] = accession
                    title = record.get('Title', 'No title')[:60]
                    print(f"  ✓ VALID: {title}...")
                
                # Be nice to NCBI servers
                time.sleep(0.5)
                
            except Exception as e:
                invalid_accessions.append((species, accession, str(e)))
                print(f"  ✗ ERROR: {e}")
        
        if invalid_accessions:
            print(f"\nINVALID ACCESSIONS FOUND:")
            for species, acc, error in invalid_accessions:
                print(f"  {species}: {acc} - {error}")
        
        return valid_accessions, invalid_accessions
    
    def generate_updated_species_list(self, additions=None):
        """Generate updated species list for the bash script"""
        if additions is None:
            additions = []
        
        print(f"\nGENERATING UPDATED SPECIES LIST")
        print("=" * 50)
        
        # Combine current species with additions
        updated_species = self.current_species.copy()
        
        for addition in additions:
            species_name = addition['species']
            accession = addition['accession']
            updated_species[species_name] = {
                'accession': accession,
                'group': addition.get('group', 'Unknown'),
                'gdgt_type': addition.get('gdgt_type', 'Unknown'),
                'habitat': addition.get('habitat', 'Unknown'),
                'importance': addition.get('reason', 'Added species'),
                'temp_range': addition.get('temp_range', 'Unknown')
            }
        
        # Generate bash script format
        print("UPDATED BASH SCRIPT SPECIES DECLARATION:")
        print("declare -A SPECIES=(")
        for species, info in updated_species.items():
            if species != 'Escherichia_coli':  # Handle outgroup separately
                print(f'    ["{species}"]="{info["accession"]}"')
        print(f'    ["Escherichia_coli"]="NR_024570.1"  # Bacterial outgroup')
        print(")")
        
        return updated_species
    
    def create_species_selection_report(self):
        """Create a comprehensive report on species selection"""
        report = []
        report.append("ARCHAEAL SPECIES SELECTION REPORT FOR TEXAS GDGT PROJECT")
        report.append("=" * 60)
        report.append(f"Generated: {pd.Timestamp.now()}")
        report.append(f"Email: {self.email}")
        report.append("")
        
        # Current coverage
        groups, gdgt_types = self.assess_current_coverage()
        
        # Gaps
        gaps = self.identify_gaps()
        
        # Priority additions
        priorities = self.suggest_priority_additions()
        
        # Save to file
        report_text = "\n".join(report)
        with open("species_selection_report.txt", "w") as f:
            f.write(report_text)
        
        return report_text

def main():
    """Example usage"""
    email = "rattanasriampaipong.r@gmail.com"  # Replace with your email
    
    validator = GDGTSpeciesValidator(email)
    
    # Assess current coverage
    validator.assess_current_coverage()
    
    # Identify gaps
    validator.identify_gaps() 
    
    # Get priority additions
    priorities = validator.suggest_priority_additions()
    
    # Check accession validity for current species
    current_accessions = {sp: info['accession'] for sp, info in validator.current_species.items()}
    valid, invalid = validator.check_accession_validity(current_accessions)
    
    # Generate updated list with high priority additions
    high_priority = [p for p in priorities if p['priority'] == 'HIGH']
    updated_species = validator.generate_updated_species_list(high_priority)
    
    # Create comprehensive report
    validator.create_species_selection_report()
    
    print(f"\n" + "="*60)
    print("RECOMMENDATIONS FOR YOUR TEXAS PROJECT:")
    print("="*60)
    print("1. Consider adding high-priority species for better GDGT coverage")
    print("2. Update your bash script with the new species declaration")
    print("3. Re-run phylogenetic analysis with expanded species set")
    print("4. Validate that new tree better represents GDGT diversity")

if __name__ == "__main__":
    main()
