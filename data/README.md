# Data

The `data/` folder is the bridge between Zenodo and the code.
Everything downloads into it; notebooks and the package API read from it;
the Docker container bind-mounts it from your host machine.

```
Zenodo data record (DOI: https://doi.org/10.5281/zenodo.19666744)
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
| Inverse temperature reconstruction only | Forward posteriors (`.nc`) | Nothing for the default calibrations — four posteriors ship with the package. Others: `TEXAS.download_posteriors()` |
| Run SI analysis notebooks from scratch | Training CSVs + posteriors | `TEXAS.download_training_data()` + `TEXAS.download_posteriors()` |
| Reproduce preprocessing (`SI_code00_PreProcessing`) | Training CSVs | `TEXAS.download_training_data()` |

---

## Downloading with Python (recommended)

```python
import TEXAS

# Download forward calibration posteriors (~475 MB total)
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
│   ├── TEXAS_invT_posterior_cache/ ← inverse temperature posteriors (.nc)
│   └── TEXAS_kriged_grids_cache/  ← kriged residual-map grids (.npz)
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

**Data DOI**: https://doi.org/10.5281/zenodo.19666744

This is the *concept DOI* — it always resolves to the newest deposited
version, and every Zenodo reference to "the data record" in this file uses
it. A dated, version-specific DOI (e.g. `zenodo.20032542`, the superseded
v0.2.0 deposit — see `src/TEXAS/utils/download.py`) is used only for a
particular frozen deposit, such as when pinning a download to files that
were never migrated to the current record; none of the links below need
that distinction.

You can also download files manually from the Zenodo record page
and place them in the directories above.

---

## Where every file lives

Use this section to find where a file comes from when a notebook can't find
it. Files fall into three groups:

1. **Training data** — included in the repository; nothing to download.
2. **Published datasets** — download from the original source (links below).
3. **Derived NetCDFs** — produced by the SI notebooks from published datasets
   (WOA23 and the group 2 downloads).

The regridded Tierney et al. (2022) PETMDA and Zhu et al. (2019) iPETM grids in
table 3 are **not** on the TEXAS Zenodo data record. We do not re-host published
datasets that this study used without significant reanalysis; these grids are
regridded copies of published model output, so obtain the originals from those
publications (table 2) and regenerate them.

### 1. Training data in the repository (22 files)

These come with the repository (via Git LFS), so no download is needed. A few
are not used by the current notebooks and are kept for reference.

| filename | what reads it | where to get it |
|---|---|---|
| `data/spreadsheets/combined_coretop_culture_mesocosm_rev20260210.csv` | `SI_code00_PreProcessing.ipynb`, `SI_code03_paleo_showcases.ipynb`, `notebooks/reviewer_response/SI_code04_model_comparison_cv.ipynb`, `notebooks/quickstart_extended.ipynb`; `scripts/build_calibration_domain.py`, `scripts/paper/add_retained_flag.py`, `scripts/prepare_resubmission_archive.py`; `TEXAS.utils.download` registry | in this repository (LFS) |
| `data/spreadsheets/culture_mesocosm_combined_rev_030425.csv` | not used by the current notebooks (kept for reference) | in this repository (LFS) |
| `data/spreadsheets/culture_mesocosm_combined_rev_092325.xlsx` | `SI_code00_PreProcessing.ipynb` | in this repository (LFS) |
| `data/spreadsheets/ds01_updated_global_coretop_tex_revised_011226.csv` | `SI_code00_PreProcessing.ipynb` | in this repository (LFS) |
| `data/spreadsheets/ds03_processed_coretop_tex.csv` | not used by the current notebooks (kept for reference) | in this repository (LFS) |
| `data/spreadsheets/ds_gridded_screened_global_compilation_finalized.csv` | `SI_code01_t0shift_variance_partitioning.ipynb`, `SI_code02_t0shift_TEXAS_analysis.ipynb`, `SI_code02a_model_param_sensitivity_test.ipynb`, `SI_code03_paleo_showcases.ipynb`; `scripts/paper/run_param_sensitivity.py`, `run_manuscript_refits.py`, `add_retained_flag.py`; `scripts/prepare_resubmission_archive.py`; `streamlit_app/pages/calibration_data.py`; `TEXAS.utils.download` registry | in this repository (LFS) |
| `data/spreadsheets/global_hydrothermal_vents.csv` | not used by the current notebooks (kept for reference) | in this repository (LFS) |
| `data/spreadsheets/ols_tex_thermoT_thisStudy.pkl` | `SI_code03_paleo_showcases.ipynb` | in this repository (LFS) |
| `data/spreadsheets/revised_cultures_GDGT_github_March2025_RR.xlsx` | not used by the current notebooks (kept for reference) | in this repository (LFS) |
| `data/spreadsheets/texmesocosms.csv` | not used by the current notebooks (kept for reference) | in this repository (LFS) |
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

### 2. Published datasets to download (14 files under `data/external/`)

These are published datasets used by the SI notebooks. They are not hosted on
the TEXAS Zenodo record; download them from the sources listed. Several are only
needed to regenerate the regridded model grids in table 3, using the regridding
cell in `SI_code03_paleo_showcases.ipynb` (commented out by default).

| filename | what reads it | where to get it |
|---|---|---|
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
| `data/external/paleoDEMS/pyGplates_files/PaleoDEMS_global_plate_model/Muller2019-Young2019-Cao2020_COBs.gpmlz` | **`SI_code03_paleo_showcases.ipynb`** (live, executed cell reconstructing PETM-age coastlines) | Müller et al. (2019) plate model (GPlates/EarthByte) |
| `data/external/paleoDEMS/pyGplates_files/PaleoDEMS_global_plate_model/Muller2019-Young2019-Cao2020_CombinedRotations.rot` | **`SI_code03_paleo_showcases.ipynb`** (live, same cell) | Müller et al. (2019) plate model (GPlates/EarthByte) |

### 3. Derived NetCDFs (6 files)

These are outputs of this project's own preprocessing (WOA23-derived ocean
properties, and CESM simulation output regridded to a common grid) that
`SI_code00_PreProcessing.ipynb` and `SI_code03_paleo_showcases.ipynb` read back in.

| filename | what reads it | where to get it |
|---|---|---|
| `data/external/ncfiles/ds06_calculated_ocean_properties.nc` | `SI_code00_PreProcessing.ipynb`, `SI_code03_paleo_showcases.ipynb`, `notebooks/quickstart_extended.ipynb`, `src/TEXAS/data/ocean_lookup.py` (used at inference time by `predict_T_from_proxyObs`), `scripts/paper/run_manuscript_refits.py`, `scripts/prepare_resubmission_archive.py` | already served from the GRL paper's Zenodo record via `TRAINING_DATA_REGISTRY["ocean_prop_ds"]` (`TEXAS.download_ocean_properties()`); **no upload needed** |
| `data/external/ncfiles/Tierney22_PNAS_PETMDA/PETMDA_OCN_annual_regridded.nc` | `SI_code03_paleo_showcases.ipynb` | not re-hosted; regenerate from the original (table 2) with the regridding cell in `SI_code03_paleo_showcases.ipynb` |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/fullDepth_regridded_iPETM/Zhu19_Science_EoceneSim_fullDepth_regridded_iPETM01x.nc` | `SI_code03_paleo_showcases.ipynb` | not re-hosted; regenerate from the original (table 2) with the regridding cell in `SI_code03_paleo_showcases.ipynb` |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/fullDepth_regridded_iPETM/Zhu19_Science_EoceneSim_fullDepth_regridded_iPETM03x.nc` | `SI_code03_paleo_showcases.ipynb` | not re-hosted; regenerate from the original (table 2) with the regridding cell in `SI_code03_paleo_showcases.ipynb` |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/fullDepth_regridded_iPETM/Zhu19_Science_EoceneSim_fullDepth_regridded_iPETM06x.nc` | `SI_code03_paleo_showcases.ipynb` | not re-hosted; regenerate from the original (table 2) with the regridding cell in `SI_code03_paleo_showcases.ipynb` |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/fullDepth_regridded_iPETM/Zhu19_Science_EoceneSim_fullDepth_regridded_iPETM09x.nc` | `SI_code03_paleo_showcases.ipynb` | not re-hosted; regenerate from the original (table 2) with the regridding cell in `SI_code03_paleo_showcases.ipynb` |

**The five regridded grids (~13 MB) are not re-hosted**, because this study used
these published datasets without significant reanalysis (Tierney et al. 2022 PNAS PETMDA; Zhu et al. 2019
*Science* EoceneSim, [PANGAEA](https://doi.org/10.1594/PANGAEA.899208)). A fresh
clone therefore cannot run `SI_code03_paleo_showcases.ipynb` end to end until
you download the originals listed in table 2 and run that notebook's
(commented-out) regridding cell.
