# Data

The `data/` folder is the bridge between Zenodo and the code.
Everything downloads into it; notebooks and the package API read from it;
the Docker container bind-mounts it from your host machine.

```
Zenodo data record (DOI: https://doi.org/10.5281/zenodo.20032542)
  ├── posteriors (.nc)   ──→  download_posteriors()    ──→  data/cache/TEXAS_posterior_cache/
  └── training CSVs      ──→  download_training_data() ──→  data/spreadsheets/
                                       ↑
                         Docker bind-mounts data/ from host
                         → inside container, paths are identical
                         → notebooks just work
```

---

## What you need depends on what you want to do

| Goal | Files needed | How to get them |
|------|-------------|-----------------|
| Inverse temperature reconstruction only | Forward posteriors (`.nc`) | `TEXAS.download_posteriors()` |
| Run SI analysis notebooks from scratch | Training CSVs + posteriors | `TEXAS.download_training_data()` + `TEXAS.download_posteriors()` |
| Reproduce preprocessing (SI_code1) | Training CSVs | `TEXAS.download_training_data()` |

---

## Downloading with Python (recommended)

```python
import TEXAS

# Download forward calibration posteriors (~280 MB total)
TEXAS.download_posteriors()

# Download GDGT training CSVs (needed only to re-run SI notebooks)
TEXAS.download_training_data()
```

Both functions are idempotent — running them again skips files already on disk.
Use `force=True` to re-download.

---

## Docker / Dev Container users

Run the download commands **on your host machine** before starting the container:

```python
# On your host (outside Docker):
import TEXAS
TEXAS.download_posteriors()
TEXAS.download_training_data()
```

The container bind-mounts `data/` from the host (`docker-compose.yml`),
so the files you downloaded are automatically available inside JupyterLab
at the same relative paths the notebooks expect — no path changes needed.

---

## Colab / pip-installed users

```python
# Mount Google Drive first if your data lives there:
from google.colab import drive
drive.mount("/content/drive")

import os
os.environ["TEXAS_DATA_DIR"] = "/content/drive/MyDrive/texas_data"
os.environ["TEXAS_CACHE_DIR"] = "/content/drive/MyDrive/texas_cache"

import TEXAS
TEXAS.download_posteriors()       # downloads to TEXAS_CACHE_DIR
TEXAS.download_training_data()    # downloads to TEXAS_DATA_DIR/spreadsheets/
```

Or download to the default locations (ephemeral Colab disk, lost on session end):
```python
import TEXAS
TEXAS.download_posteriors()
```

---

## Directory layout

```
data/
├── cache/
│   ├── TEXAS_posterior_cache/     ← forward calibration posteriors (.nc)
│   └── TEXAS_invT_posterior_cache/ ← inverse temperature posteriors (.nc)
├── spreadsheets/                  ← GDGT training CSVs (download from Zenodo)
└── external/                      ← third-party reference datasets (see below)
```

---

## External datasets (needed for full SI reproducibility)

These are not hosted on the TEXAS Zenodo record — download them separately:

| Dataset | Source | Place in |
|---------|--------|----------|
| WOA23 temperature climatology | [NOAA World Ocean Atlas 2023](https://www.ncei.noaa.gov/products/world-ocean-atlas) | `data/external/` |
| Zhu et al. 2019 proxy data | [Pangaea](https://doi.org/10.1594/PANGAEA.899208) | `data/external/` |
| Tierney et al. 2022 proxy data | See manuscript data availability section | `data/external/` |

`data/external/` is gitignored (~310 MB).

---

## Zenodo record

**Data DOI**: https://doi.org/10.5281/zenodo.20032542

You can also download files manually from the Zenodo record page
and place them in the directories above.

---

## Where every file lives

97 data files left version control in the 2026-09-07 repo-hygiene pass (Tasks 7–8):
22 training files stayed tracked (re-included in `.gitignore`, arriving via LFS with
every clone), and 97 were untracked — 35 third-party originals and 6 TEXAS-derived
NetCDFs under `data/external/`, plus 56 superseded spreadsheets. The four tables
below cover all 119 files (22 + 97) so a fresh clone can tell, for any path a
notebook opens, whether it needs fetching and where from. Files with no known
public source are marked "author-only, not needed by any notebook" rather than
left blank — that phrase means exactly what it says: nobody has to go find it.

The derived NetCDFs in table 3 that still need hosting will live on the TEXAS
Zenodo data record, DOI [10.5281/zenodo.22131367](https://doi.org/10.5281/zenodo.22131367),
once uploaded at the v1.0.0 release (tracked in `RESUME.md`, Phase C).

### 1. Tracked training data (22 files)

These arrive with a clone via LFS — no download step needed. "What reads it" was
found by grepping each basename across `notebooks/`, `src/`, `tests/`, `scripts/`,
and `streamlit_app/`; five files matched no live reader despite carrying reference
counts in the design spec's Appendix A.1 (see Task 9 report, Concerns).

| filename | what reads it | where to get it |
|---|---|---|
| `data/spreadsheets/combined_coretop_culture_mesocosm_rev20260210.csv` | `SI_code00_PreProcessing.ipynb`, `SI_code03_paleo_showcases.ipynb`, `notebooks/reviewer_response/SI_code04_model_comparison_cv.ipynb`, `notebooks/quickstart_extended.ipynb`; `scripts/build_calibration_domain.py`, `scripts/paper/add_retained_flag.py`, `scripts/prepare_resubmission_archive.py`; `TEXAS.utils.download` registry | in this repository (LFS) |
| `data/spreadsheets/culture_mesocosm_combined_rev_030425.csv` | not read by any current notebook or script found | in this repository (LFS) |
| `data/spreadsheets/culture_mesocosm_combined_rev_092325.xlsx` | `SI_code00_PreProcessing.ipynb` | in this repository (LFS) |
| `data/spreadsheets/ds01_updated_global_coretop_tex_revised_011226.csv` | `SI_code00_PreProcessing.ipynb` | in this repository (LFS) |
| `data/spreadsheets/ds03_processed_coretop_tex.csv` | not read by any current notebook or script found | in this repository (LFS) |
| `data/spreadsheets/ds_gridded_screened_global_compilation_finalized.csv` | `SI_code01_t0shift_variance_partitioning.ipynb`, `SI_code02_t0shift_TEXAS_analysis.ipynb`, `SI_code02a_model_param_sensitivity_test.ipynb`, `SI_code03_paleo_showcases.ipynb`; `scripts/paper/run_param_sensitivity.py`, `run_manuscript_refits.py`, `add_retained_flag.py`, `prepare_resubmission_archive.py`; `streamlit_app/pages/calibration_data.py`; `TEXAS.utils.download` registry | in this repository (LFS) |
| `data/spreadsheets/global_hydrothermal_vents.csv` | not read by any current notebook or script found | in this repository (LFS) |
| `data/spreadsheets/ols_tex_thermoT_thisStudy.pkl` | `SI_code03_paleo_showcases.ipynb` | in this repository (LFS) |
| `data/spreadsheets/revised_cultures_GDGT_github_March2025_RR.xlsx` | not read by any current notebook or script found | in this repository (LFS) |
| `data/spreadsheets/texmesocosms.csv` | not read by any current notebook or script found | in this repository (LFS) |
| `data/spreadsheets/published_data/Babila_SST_results_finalized_compiled.xlsx` | `SI_code03_paleo_showcases.ipynb` | in this repository (LFS) |
| `data/spreadsheets/published_data/ds07_TasmanSea_paleorecords.xlsx` | `SI_code03_paleo_showcases.ipynb` | in this repository (LFS) |
| `data/spreadsheets/published_data/Gaskell2022_pnas.2111332119.sd01.xlsx` | `SI_code03_paleo_showcases.ipynb` | in this repository (LFS) |
| `data/spreadsheets/published_data/ODP1259_d18O_planktic_Bornemann08_OBrien17compl.xlsx` | `SI_code03_paleo_showcases.ipynb` | in this repository (LFS) |
| `data/spreadsheets/published_data/PhanSST_v001_extendedRR_121025.csv` | `SI_code03_paleo_showcases.ipynb` | in this repository (LFS) |
| `data/spreadsheets/published_data/PhanTEX_GIG_df.csv` | `SI_code03_paleo_showcases.ipynb`, `scripts/paper/run_manuscript_refits.py` | in this repository (LFS) |
| `data/spreadsheets/published_data/PhanTEX_GIG_df.parquet` | `SI_code03_paleo_showcases.ipynb` | in this repository (LFS) |
| `data/spreadsheets/published_data/PhanTEX_v001_modified_032626.csv` | `SI_code03_paleo_showcases.ipynb`, `scripts/paper/run_manuscript_refits.py` | in this repository (LFS) |
| `data/spreadsheets/published_data/tran2025-u1482-bio-sst.txt` | `SI_code03_paleo_showcases.ipynb` | in this repository (LFS) |
| `data/spreadsheets/published_data/U1482_MgCa_SST.xlsx` | `SI_code03_paleo_showcases.ipynb` | in this repository (LFS) |
| `data/spreadsheets/published_data/Varma-etal_Co1010.csv` | `SI_code03_paleo_showcases.ipynb` | in this repository (LFS) |
| `data/spreadsheets/published_data/NICOPP_d15Nsed_database/nicopp-coretop-data.txt` | `SI_code03_paleo_showcases.ipynb` | in this repository (LFS) |

### 2. Third-party originals, not tracked (35 files under `data/external/`)

None of these are hosted on the TEXAS Zenodo record. Most are not read by any
finalized notebook — several are raw inputs to a regridding step that already
ran once and now lives commented-out in `SI_code03_paleo_showcases.ipynb`
(the output it produced is the TEXAS-derived NetCDF in table 3).

| filename | what reads it | where to get it |
|---|---|---|
| `data/external/ncfiles/calculated_ocean_properties.nc` | not read by any current notebook or script | author-only, not needed by any notebook (earlier copy of the WOA23-derived ocean-properties field superseded by `ds06_calculated_ocean_properties.nc`, table 3) |
| `data/external/ncfiles/calculated_ocean_properties_seasonal.nc` | not read by any current notebook or script | author-only, not needed by any notebook |
| `data/external/ncfiles/ds04_gridded_coretop_tex.nc` | not read by any current notebook or script | author-only, not needed by any notebook |
| `data/external/ncfiles/ds04_gridded_coretop_tex_scaledRI.nc` | not read by any current notebook or script | author-only, not needed by any notebook |
| `data/external/ncfiles/ds05_gridded_AOM_ds.nc` | not read by any current notebook or script | author-only, not needed by any notebook |
| `data/external/ncfiles/ds_gridded_coretop_tex_scaledRI_revised_081525.nc` | `archive/presentations/IMOG_presentation.ipynb` only (not a finalized notebook) | author-only, not needed by any finalized notebook |
| `data/external/ncfiles/ds_gridded_coretop_tex_scaledRI_revised_101425.nc` | not read by any current notebook or script | author-only, not needed by any notebook |
| `data/external/ncfiles/gistemp1200_GHCNv4_ERSSTv5.nc` | not read by any current notebook or script | [NASA GISS GISTEMP](https://data.giss.nasa.gov/gistemp/) (combined GHCNv4 land + ERSSTv5 ocean surface temperature) |
| `data/external/ncfiles/gridded_coretop_RI.nc` | not read by any current notebook or script | author-only, not needed by any notebook |
| `data/external/ncfiles/PETMDA_OCN_annual.nc` | input to a commented-out regridding cell in `SI_code03_paleo_showcases.ipynb` (not executed by default) | Tierney et al. 2022 PNAS PETMDA (see manuscript data-availability section); raw predecessor of the regridded file in table 3 |
| `data/external/ncfiles/Tierney22_PNAS_PETMDA/PETMDA_OCN_annual.nc` | same commented-out cell (duplicate copy) | same as above |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPETM01x.01.cam.h0.TS_TREFHT.2501-2600.climo.nc` | input to a commented-out regridding cell in `SI_code03_paleo_showcases.ipynb` (not executed by default) | Zhu et al. 2019 *Science* EoceneSim CESM output — [PANGAEA](https://doi.org/10.1594/PANGAEA.899208) |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPETM01x.01.pop.h.TEMP.2501-2600.climo.nc` | same | same |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPETM03x.02.cam.h0.TS_TREFHT.1901-2000.climo.nc` | same | same |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPETM03x.02.pop.h.TEMP.1901-2000.climo.nc` | same | same |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPETM06x.07.cam.h0.TS_TREFHT.1901-2000.climo.nc` | same | same |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPETM06x.07.pop.h.TEMP.1901-2000.climo.nc` | same | same |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPETM09x.01.cam.h0.TS_TREFHT.1901-2000.climo.nc` | same | same |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPETM09x.01.pop.h.TEMP.1901-2000.climo.nc` | same | same |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPI.01.cam.h0.TS_TREFHT.0400-0499.climo.nc` | same | same |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPI.01.pop.h.TEMP.0400-0499.climo.nc` | same | same |
| `data/external/paleoDEMS/PaleoDEMS_elevation_Scotese_Wright_2018.nc` | not read by any current notebook or script | Scotese and Wright (2018) paleo-DEM elevation reconstruction |
| `data/external/paleoDEMS/pyGplates_files/PaleoDEMS_global_plate_model/Global_EarthByte_230-0Ma_GK07_AREPS_Coastlines.gpmlz` | not read by any current notebook or script (not even in a commented-out line) | EarthByte/GPlates global plate model (same lineage as Müller et al. 2019); no confirmed direct link found in this repo |
| `data/external/paleoDEMS/pyGplates_files/PaleoDEMS_global_plate_model/Global_EarthByte_230-0Ma_GK07_AREPS.rot` | not read by any current notebook or script | same as above |
| `data/external/paleoDEMS/pyGplates_files/PaleoDEMS_global_plate_model/m06c9h_3id_forPgeog_19o_r1c.rot` | referenced only in a commented-out line in `SI_code03_paleo_showcases.ipynb` | author-only, not needed by any notebook |
| `data/external/paleoDEMS/pyGplates_files/PaleoDEMS_global_plate_model/Muller2019-Young2019-Cao2020_COBs.gpmlz` | **`SI_code03_paleo_showcases.ipynb`** (live, executed cell reconstructing PETM-age coastlines) | Müller et al. (2019) plate model (GPlates/EarthByte) |
| `data/external/paleoDEMS/pyGplates_files/PaleoDEMS_global_plate_model/Muller2019-Young2019-Cao2020_CombinedRotations.rot` | **`SI_code03_paleo_showcases.ipynb`** (live, same cell) | Müller et al. (2019) plate model (GPlates/EarthByte) |
| `data/external/paleoDEMS/pyGplates_files/PaleoDEMS_global_plate_model/PALEOMAP_PlatePolygons__forPgeog_v19o.gpml` | referenced only in a commented-out line in `SI_code03_paleo_showcases.ipynb` | author-only, not needed by any notebook |
| `data/external/shapefiles/Knolls.prj` | not read by any current notebook or script | author-only, not needed by any notebook |
| `data/external/shapefiles/Knolls.shp` | not read by any current notebook or script | author-only, not needed by any notebook |
| `data/external/shapefiles/Knolls.shx` | not read by any current notebook or script | author-only, not needed by any notebook |
| `data/external/shapefiles/Seamounts.dbf` | not read by any current notebook or script | author-only, not needed by any notebook |
| `data/external/shapefiles/Seamounts.prj` | not read by any current notebook or script | author-only, not needed by any notebook |
| `data/external/shapefiles/Seamounts.shp` | not read by any current notebook or script | author-only, not needed by any notebook |
| `data/external/shapefiles/Seamounts.shx` | not read by any current notebook or script | author-only, not needed by any notebook |

### 3. TEXAS-derived NetCDFs, not tracked (6 files)

These are outputs of this project's own preprocessing (WOA23-derived ocean
properties, and CESM simulation output regridded to a common grid) that
`SI_code00_PreProcessing.ipynb` and `SI_code03_paleo_showcases.ipynb` read back in.

| filename | what reads it | where to get it |
|---|---|---|
| `data/external/ncfiles/ds06_calculated_ocean_properties.nc` | `SI_code00_PreProcessing.ipynb`, `SI_code03_paleo_showcases.ipynb`, `notebooks/quickstart_extended.ipynb`, `src/TEXAS/data/ocean_lookup.py` (used at inference time by `predict_T_from_proxyObs`), `scripts/paper/run_manuscript_refits.py`, `scripts/prepare_resubmission_archive.py` | already served from the GRL paper's Zenodo record via `TRAINING_DATA_REGISTRY["ocean_prop_ds"]` (`TEXAS.download_ocean_properties()`); **no upload needed** |
| `data/external/ncfiles/Tierney22_PNAS_PETMDA/PETMDA_OCN_annual_regridded.nc` | `SI_code03_paleo_showcases.ipynb` | **upload to the Zenodo data record at v1.0.0** |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/fullDepth_regridded_iPETM/Zhu19_Science_EoceneSim_fullDepth_regridded_iPETM01x.nc` | `SI_code03_paleo_showcases.ipynb` | **upload to the Zenodo data record at v1.0.0** |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/fullDepth_regridded_iPETM/Zhu19_Science_EoceneSim_fullDepth_regridded_iPETM03x.nc` | `SI_code03_paleo_showcases.ipynb` | **upload to the Zenodo data record at v1.0.0** |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/fullDepth_regridded_iPETM/Zhu19_Science_EoceneSim_fullDepth_regridded_iPETM06x.nc` | `SI_code03_paleo_showcases.ipynb` | **upload to the Zenodo data record at v1.0.0** |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/fullDepth_regridded_iPETM/Zhu19_Science_EoceneSim_fullDepth_regridded_iPETM09x.nc` | `SI_code03_paleo_showcases.ipynb` | **upload to the Zenodo data record at v1.0.0** |

**Five of these files, totalling 16 MB, need the v1.0.0 upload** before a fresh
clone can run `SI_code00_PreProcessing.ipynb` and `SI_code03_paleo_showcases.ipynb`
end to end (see `RESUME.md`, Phase C). `ds04_gridded_coretop_tex_scaledRI.nc`
(table 2) and `calculated_ocean_properties_seasonal.nc` (table 2) are
deliberately dropped without an upload: per the repo-finalization design spec's
Appendix A.2, their only reader is the ignored, locally-gitignored
`notebooks/exploration/` directory, which does not exist in this working tree
and so is not part of any shipped notebook's dependency chain.

### 4. Superseded spreadsheets, not tracked (56 files)

Earlier revisions of the kept training files (table 1), plus published datasets
that no finalized notebook opens. None of these were found to be read by any
current notebook or script in `notebooks/`, `src/`, `tests/`, `scripts/`, or
`streamlit_app/`.

| filename | supersedes / relationship | where to get it |
|---|---|---|
| `data/raw/OPTiMAL_culmeso_v2.csv` | — | author-only, not needed by any notebook |
| `data/spreadsheets/bit_mixing_analysis.ods` | — | author-only, not needed by any notebook |
| `data/spreadsheets/bit_mixing_analysis.xlsx` | — | author-only, not needed by any notebook |
| `data/spreadsheets/combined_coretop_culture_mesocosm_rev20241015.csv` | earlier revision of kept `combined_coretop_culture_mesocosm_rev20260210.csv` | author-only, not needed by any notebook |
| `data/spreadsheets/combined_df_culmesocore_griddedRI.csv` | — | author-only, not needed by any notebook |
| `data/spreadsheets/combined_df_culmesocore_rawData.csv` | — | author-only, not needed by any notebook |
| `data/spreadsheets/compiled-regression-dataset.csv` | — | author-only, not needed by any notebook |
| `data/spreadsheets/culmeso_fgdgts.csv` | — | author-only, not needed by any notebook |
| `data/spreadsheets/culture_mesocosm_combined_rev_092325 - Copy.xlsx` | duplicate of kept `culture_mesocosm_combined_rev_092325.xlsx` | author-only, not needed by any notebook |
| `data/spreadsheets/culture_mesocosm_combined_rev_092325.csv` | csv export of kept `culture_mesocosm_combined_rev_092325.xlsx` | author-only, not needed by any notebook |
| `data/spreadsheets/ds01_updated_global_coretop_tex.csv` | earlier revision of kept `ds01_updated_global_coretop_tex_revised_011226.csv` | author-only, not needed by any notebook |
| `data/spreadsheets/ds02_manual_regionName_assignment.xlsx` | — | author-only, not needed by any notebook |
| `data/spreadsheets/ds_gridded_coretop_tex_scaledRI_revised_120325.csv` | earlier revision in the `ds_gridded_screened_global_compilation_finalized.csv` lineage | author-only, not needed by any notebook |
| `data/spreadsheets/Evans2018_lipid_comp_and_temp.csv` | — | author-only, not needed by any notebook |
| `data/spreadsheets/fitted_models/ols_tex_thermoT_thisStudy.pkl` | duplicate of kept `data/spreadsheets/ols_tex_thermoT_thisStudy.pkl` (the copy `SI_code03` actually opens) | author-only, not needed by any notebook |
| `data/spreadsheets/gridded_coretop_with_logi_predRI_T_2025-08-19.csv` | — | author-only, not needed by any notebook |
| `data/spreadsheets/gridded_coretop_with_logi_predRI_T_2025-08-20.csv` | — | author-only, not needed by any notebook |
| `data/spreadsheets/ODP959_data.csv` | — | author-only, not needed by any notebook |
| `data/spreadsheets/OPTiMAL_culmeso.csv` | — | author-only, not needed by any notebook |
| `data/spreadsheets/OPTiMAL_raw_coretop.csv` | — | author-only, not needed by any notebook |
| `data/spreadsheets/postprocessed_culture_data.csv` | — | author-only, not needed by any notebook |
| `data/spreadsheets/processed_coretop_data.csv` | — | author-only, not needed by any notebook |
| `data/spreadsheets/published_data/Babila2022_MgCa_SDB_PETM.xlsx` | — | author-only, not needed by any notebook |
| `data/spreadsheets/published_data/Babila_SST_results.csv` | earlier revision of kept `Babila_SST_results_finalized_compiled.xlsx` | author-only, not needed by any notebook |
| `data/spreadsheets/published_data/deutnat-vostok-noaa.txt` | — | NOAA NCEI Paleoclimatology (per filename convention; not confirmed by a direct URL in this repo) |
| `data/spreadsheets/published_data/Hingsley_etal_2.23_OG_GDD Global Distribution Dataset.xlsx` | — | author-only, not needed by any notebook |
| `data/spreadsheets/published_data/Huguet2006_ArabianSea_paleorecords/huguet2006-niop-c2_905_pc.csv` | export of the `.tab` record below | PANGAEA |
| `data/spreadsheets/published_data/Huguet2006_ArabianSea_paleorecords/huguet2006-niop-c2_905_pc.xlsx` | export of the `.tab` record below | PANGAEA |
| `data/spreadsheets/published_data/Huguet2006_ArabianSea_paleorecords/huguet2006-so42-74kl.csv` | export of the `.tab` record below | PANGAEA |
| `data/spreadsheets/published_data/Huguet2006_ArabianSea_paleorecords/huguet2006-so42-74kl.xlsx` | export of the `.tab` record below | PANGAEA |
| `data/spreadsheets/published_data/Huguet2006_ArabianSea_paleorecords/NIOP-C2_905_PC_SST.tab` | — | PANGAEA (`.tab` is PANGAEA's native export format) |
| `data/spreadsheets/published_data/Huguet2006_ArabianSea_paleorecords/SO42-74KL_SST.tab` | — | PANGAEA |
| `data/spreadsheets/published_data/Inglis2023_TEX_SDB_PETM.xlsx` | — | author-only, not needed by any notebook |
| `data/spreadsheets/published_data/lisiecki2005-d18o-stack-noaa.txt` | — | NOAA NCEI Paleoclimatology (LR04 stack; per filename convention) |
| `data/spreadsheets/published_data/Naafs-etal_peat-individual-global-gdgt.xlsx` | — | author-only, not needed by any notebook |
| `data/spreadsheets/published_data/NICOPP_d15Nsed_database/NICOPP_coretop_published_130307.mat` | companion file to kept `nicopp-coretop-data.txt` | author-only, not needed by any notebook |
| `data/spreadsheets/published_data/NICOPP_d15Nsed_database/nicopp-downcore-data.txt` | companion file to kept `nicopp-coretop-data.txt` | author-only, not needed by any notebook |
| `data/spreadsheets/published_data/NICOPP_d15Nsed_database/NICOPP_downcore_published_130307.mat` | companion file to kept `nicopp-coretop-data.txt` | author-only, not needed by any notebook |
| `data/spreadsheets/published_data/NICOPP_d15Nsed_database/Seafloor_coretop_samples.xls` | companion file to kept `nicopp-coretop-data.txt` | author-only, not needed by any notebook |
| `data/spreadsheets/published_data/PhanSST_v001.csv` | earlier revision of kept `PhanSST_v001_extendedRR_121025.csv` | PhanSST compilation |
| `data/spreadsheets/published_data/PhanTEX_v001_modified_021126.csv` | earlier revision of kept `PhanTEX_v001_modified_032626.csv` | PhanSST/PhanTEX compilation |
| `data/spreadsheets/published_data/PhanTEX_v001_modified_120325.csv` | earlier revision of kept `PhanTEX_v001_modified_032626.csv` | PhanSST/PhanTEX compilation |
| `data/spreadsheets/published_data/PhanTEX_v001_modified_121025.csv` | earlier revision of kept `PhanTEX_v001_modified_032626.csv` | PhanSST/PhanTEX compilation |
| `data/spreadsheets/published_data/SDB_Mgtemp_Gordon_Apr2022.xlsx` | — | author-only, not needed by any notebook |
| `data/spreadsheets/published_data/Seierstad2014_NGRIP_d18O_dataset.xlsx` | — | author-only, not needed by any notebook |
| `data/spreadsheets/published_data/TEXdatabase_v1.csv` | — | author-only, not needed by any notebook |
| `data/spreadsheets/published_data/tran2025-u1482-bio-sst.csv` | csv sibling of kept `tran2025-u1482-bio-sst.txt` | NOAA NCEI Paleoclimatology (confirmed URL in `SI_code03_paleo_showcases.ipynb`: `ncei.noaa.gov/pub/data/paleo/paleocean/indian_ocean/tran2025/`) |
| `data/spreadsheets/published_data/Weiyi23_EarthSystSciData_nitrification_database.xlsx` | — | author-only, not needed by any notebook |
| `data/spreadsheets/published_data/Zhu19_Science_proxies_aax1874_tables_s1_and_s2.xlsx` | — | PANGAEA (same record as the Zhu et al. 2019 EoceneSim files, table 2: `doi.org/10.1594/PANGAEA.899208`) |
| `data/spreadsheets/raw_coretop_fGDGTs.csv` | — | author-only, not needed by any notebook |
| `data/spreadsheets/reg_data_revised_122024.csv` | — | author-only, not needed by any notebook |
| `data/spreadsheets/revised_cultures_GDGT_github_RR2024.xlsx` | earlier revision of kept `revised_cultures_GDGT_github_March2025_RR.xlsx` | author-only, not needed by any notebook |
| `data/spreadsheets/SonneCoretopTexUk.xlsx` | — | author-only, not needed by any notebook |
| `data/spreadsheets/stan_practices/iris-data.csv` | — | classic Iris flower dataset (UCI ML repository), used only for local Stan practice; not needed by any notebook |
| `data/spreadsheets/Summary of methods for GDGT analysis.xlsx` | — | author-only, not needed by any notebook |
| `data/spreadsheets/TT15_coretop_data.csv` | — | author-only, not needed by any notebook |
