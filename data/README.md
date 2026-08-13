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
