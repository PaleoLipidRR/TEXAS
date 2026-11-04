# Installation

**To use TEXAS on your own data, install the package from PyPI with pip or uv.** That
is all most users need, and the four default calibrations come with it. You do not need
to clone the repository, or to download `uv.lock` or `pyproject.toml`: those files only
work inside a full checkout, for people forking the repository or running the manuscript
notebooks.

| You want to | Use | CmdStan |
|---|---|---|
| **Reconstruct temperatures from your own data** | **[Option A — pip or uv](#option-a--pip-or-uv-recommended)** | one command |
| Try TEXAS without installing anything | [Google Colab](https://colab.research.google.com/github/PaleoLipidRR/TEXAS/blob/main/notebooks/quickstart_demo.ipynb) | one call in the notebook |
| Fork the repository, or run the manuscript notebooks | [Option B — uv from a clone](#option-b--uv-from-a-clone) or [Option C — Docker](#option-c--docker) | one command / bundled |
| Work in conda, with exact pinned versions | [Option D — conda-lock](#option-d--conda-lock-exact-reproducible-environment) or [Option E — conda from source](#option-e--conda-from-source-development) | bundled |

> **CmdStan is never a Python package.** Every Stan model compiles to a native binary, so pip and uv users install the CmdStan C++ toolchain once in a separate step (and, on a bare machine, a C++ compiler). See [CmdStan: install, discovery, and verification](#cmdstan-install-discovery-and-verification).

---

## Option A — pip or uv (recommended)

Installs the released package from PyPI into a virtual environment.

`````{warning}
Do not run `pip install` against the system Python. Modern Debian/Ubuntu systems mark the system Python as externally managed (PEP 668) and will refuse the install. Always install into a virtual environment first.
`````

````````{tab-set}
```````{tab-item} Linux / macOS / Windows (WSL2)


Run from a bash terminal. For Windows, open your WSL2 terminal (not PowerShell or CMD).

**Step 1 — create and activate an isolated environment:**

```bash
python -m venv .venv        # any Python >= 3.10
source .venv/bin/activate
```

**Step 2 — install TEXAS:**

```bash
pip install texas-psm
```

**Step 3 — install CmdStan** (required before *sampling*; the one-call helper
installs the tested version and verifies it):

```bash
texas-install-cmdstan          # or, in Python: TEXAS.install_cmdstan()
```

Prefer to manage it manually? The equivalent low-level call is
`TBB_CXX_TYPE=gcc python -c "import cmdstanpy; cmdstanpy.install_cmdstan(version='2.36.0')"`.
```````
```````{tab-item} Windows (native Anaconda Prompt)


Run all commands from the **Anaconda Prompt** (not PowerShell or CMD).

**Step 1 — create and activate an environment:**

```bat
conda create -n texas-env python=3.10 pip
conda activate texas-env
```

**Step 2 — install CmdStan via conda-forge** (pre-built — no compiler needed):

```bat
conda install -c conda-forge cmdstan=2.36.0
```

**Step 3 — install TEXAS:**

```bat
pip install texas-psm
```

`````{admonition} Windows-specific pitfalls
:class: warning

- Do **not** install `m2w64-toolchain` — it conflicts with the conda-forge `cmdstan` package.
- Do **not** use `TBB_CXX_TYPE=gcc` — that is Linux/macOS syntax and will fail in CMD.
- Do **not** run `cmdstanpy.install_cmdstan()` — the conda-forge package is pre-compiled; calling `install_cmdstan()` will try to compile from source and fail.
`````
```````
```````{tab-item} Google Colab


```ipython
!pip install texas-psm
import TEXAS
TEXAS.install_cmdstan()      # installs CmdStan to /root/.cmdstan and verifies
```

Colab runtimes are **ephemeral** — `/root/.cmdstan` is wiped when the runtime
resets or disconnects, so re-run `TEXAS.install_cmdstan()` once per new session.
It compiles CmdStan (~2–5 min) using Colab's preinstalled `g++`/`make`, and sets
`TBB_CXX_TYPE=gcc` for you.
```````
````````

### Using uv instead of pip

[uv](https://docs.astral.sh/uv/) is a fast, drop-in replacement for `pip` and `venv`. TEXAS and its core dependencies are on PyPI, so no extra configuration is needed.

**Standalone environment:**

```bash
uv venv                       # create .venv/ with an isolated interpreter
source .venv/bin/activate
uv pip install texas-psm      # add extras as needed, e.g. "texas-psm[plotting]"
texas-install-cmdstan
```

**As a dependency of your own uv project:**

```bash
uv add texas-psm              # or: uv add "texas-psm[plotting]"
uv run texas-install-cmdstan
```

Your project gets its own `uv.lock`. TEXAS's `uv.lock` is not used here, and downloading it on its own does not work: it records TEXAS as an editable install, so `uv sync` needs the source tree beside it.

`````{admonition} Optional extras
:class: note

- `texas-psm[plotting]` (ultraplot, cmocean) and `texas-psm[maps]` (cartopy, regionmask, pykrige, joblib) install cleanly from PyPI.
- The `regrid` extra installs `xesmf` from PyPI, but **`esmpy` (the ESMF bindings xesmf needs at runtime) is not on PyPI** — install it from conda-forge: `conda install -c conda-forge esmpy`. (esmpy is deliberately kept out of the extra: a non-PyPI package in *any* extra makes `uv lock` fail for the whole project.) For heavy regridding, prefer the conda environment (Option E). Without esmpy, `regrid_curvilinear_to_latlon` falls back to its pure-scipy backend.
`````

### CmdStan: install, discovery, and verification

CmdStan is the Stan C++ toolchain. It is **never a Python package** — pip/uv install
`cmdstanpy` (the Python bindings), but the compiler itself is a separate directory
(`cmdstan-X.Y.Z/`) containing `bin/stanc` and a `Makefile`. Every Stan model compiles
to a native binary the first time it runs, so a working CmdStan **and** a C++ compiler
must both be present.

#### The one-call install (pip / uv users)

After `pip install texas-psm` (or `uv add texas-psm`), the simplest way to get CmdStan is:

```python
import TEXAS
TEXAS.install_cmdstan()      # installs the tested version, verifies, and reports READY
```

Or from any shell (PowerShell, CMD, bash, zsh):

```bash
texas-install-cmdstan        # add --version X.Y.Z or --overwrite as needed
```

This installs the version TEXAS is tested against into `~/.cmdstan/`, points TEXAS at it,
runs the [`texas-doctor`](#verify-the-whole-toolchain) check, and — unlike a bare
`cmdstanpy.install_cmdstan()` — **repairs a broken/partial install in place** (see
[Troubleshooting](troubleshooting.md#cmdstan-directory-exists-but-the-compiler-binaries-are-missing-or-unusable)).
It is a no-op if a working CmdStan already resolves, and it steps aside for conda-managed
installs. On Windows it also installs the RTools C++ compiler as part of the call. TEXAS
never installs CmdStan automatically — you always call this yourself.

The manual routes below (`cmdstanpy.install_cmdstan()`, conda-forge `cmdstan`) remain fully
supported; use them if you prefer to manage the version yourself.

#### Where CmdStan lives

| Install route | CmdStan location | `CMDSTAN` set for you? |
|---|---|---|
| Docker / conda-lock / conda `cmdstan` | inside the conda env (`$CONDA_PREFIX/…`) | ✅ by the env's activation script |
| `cmdstanpy.install_cmdstan()` | `~/.cmdstan/cmdstan-<version>/` (Windows: `C:\Users\<you>\.cmdstan\…`) | ❌ discovered by TEXAS, but you can set it |
| Manual download | wherever you unpacked it | ❌ set `CMDSTAN` yourself |

#### How TEXAS discovers it

`TEXAS.utils.paths.find_cmdstan()` searches, in order, and stops at the first directory
that contains a runnable `bin/stanc` (`stanc.exe` on Windows):

| Priority | Location | Typical source |
|---|---|---|
| 1 | `CMDSTAN` environment variable | conda activation, or set manually |
| 2 | `$CONDA_PREFIX/bin/cmdstan` | interactively-activated conda/mamba env |
| 3 | `<python prefix>/bin/cmdstan` | Docker/mamba where PATH was set but no activation script ran |
| 4 | highest `cmdstan-*` in `/opt/cmdstan/`, `~/.cmdstan/`, `/usr/local/cmdstan/` | `install_cmdstan()` default (`~/.cmdstan/`) |
| 5 | whatever `cmdstanpy` is already configured to use | prior `set_cmdstan_path()` |

`set_cmdstan_path()` is always called on the winning path so cmdstanpy stays consistent.
Any version **≥ 2.23.0** is accepted (2.23.0 introduced `reduce_sum`); across the
well-known directories the **highest** installed version wins. If `CMDSTAN` is set but its
`bin/stanc` is missing or unusable, TEXAS emits a `UserWarning` and continues down the
list. If nothing is found, a `RuntimeError` is raised with install instructions.

#### Setting `CMDSTAN` manually

Use this to pin a specific install (e.g. the one `install_cmdstan()` created) instead of
whatever conda manages. Set it **before** importing TEXAS.

````````{tab-set}
```````{tab-item} PowerShell (Windows)


```powershell
# current session
$env:CMDSTAN = "$HOME\.cmdstan\cmdstan-2.36.0"
# persist across sessions
setx CMDSTAN "$HOME\.cmdstan\cmdstan-2.36.0"   # reopen the terminal to pick it up
# confirm
echo $env:CMDSTAN
```
```````
```````{tab-item} bash / zsh (Linux, macOS, WSL2)


```bash
# current session
export CMDSTAN=~/.cmdstan/cmdstan-2.36.0
# persist: add the same line to ~/.bashrc or ~/.zshrc
# confirm
echo "$CMDSTAN"
```
```````
```````{tab-item} CMD / Anaconda Prompt (Windows)


```bat
set CMDSTAN=%USERPROFILE%\.cmdstan\cmdstan-2.36.0
echo %CMDSTAN%
```
```````
````````

#### Verify the whole toolchain

One command checks cmdstanpy, the CmdStan path/version, a C++ compiler, and the cache
directories — and tells you exactly what is missing. It runs on every platform and shell
(PowerShell, CMD, bash, zsh):

```bash
texas-doctor            # or:  python -c "import TEXAS; TEXAS.doctor()"
```

A healthy machine prints `Stan sampling: READY`. If not, the report names the failure —
including the case where `CMDSTAN` points at a directory whose `bin/stanc` was never built
— and prints the exact fix for your platform. See
[Troubleshooting → CmdStan](troubleshooting.md#cmdstan-not-found) for the failure modes.

---

## Forking the repository or running the notebooks

The options below all start from a clone, because they use files the PyPI package does not ship: the lock files, the notebooks and the Docker configuration. Editable installs matter here, so local code changes take effect. For the full list of what the manuscript notebooks need, see [Reproducing the manuscript notebooks](#reproducing-the-manuscript-notebooks-on-a-new-machine).

## Option B — uv from a clone

`uv.lock` pins every dependency, and `uv sync` installs them into a project `.venv` with TEXAS itself in editable mode:

```bash
git clone https://github.com/PaleoLipidRR/TEXAS.git    # or your fork
cd TEXAS
git lfs install && git lfs pull    # the training data and SI tables are LFS objects
uv sync --all-extras               # creates .venv/ with everything, incl. Jupyter + notebook deps
uv run texas-install-cmdstan
```

Then select `.venv/bin/python` as your notebook kernel (VS Code auto-detects it; for a named Jupyter kernel run `uv run python -m ipykernel install --user --name texas-uv`).

`````{admonition} Which sync command?
:class: tip

- `uv sync` — core runtime only (no Jupyter). Cannot serve a notebook kernel.
- `uv sync --extra dev` — adds Jupyter/ipykernel + the notebook analysis deps (scikit-learn, seaborn, openpyxl, pyarrow).
- `uv sync --all-extras` — the above **plus** plotting (ultraplot, cmocean), maps (cartopy, regionmask, pykrige, joblib), and regrid (xesmf). Recommended for the SI notebooks.
`````

---

## Option C — Docker

Docker bundles CmdStan, all Python dependencies, and the Stan compiler into a single image. No environment setup required.

**Accounts you need before starting:**

| Service | Required? | Notes |
|---|---|---|
| [Docker account](https://app.docker.com/signup) | ✅ Free account | Required to download and run Docker Desktop on Windows and macOS |
| GitHub | ❌ No | Cloning and pulling the pre-built image are both anonymous |
| Zenodo | ❌ No | Downloading posteriors is anonymous |

`````{admonition} Linux users
:class: note

Docker Engine on Linux does not require a Docker account — install it directly via `apt` without signing in.
`````

### Step 1 — Install Docker

````````{tab-set}
```````{tab-item} Linux


Install Docker Engine and the Compose plugin:

```bash
# Ubuntu / Debian
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

Add your user to the `docker` group so you can run Docker without `sudo`:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

Verify the install:

```bash
docker info
docker compose version
```
```````
```````{tab-item} Windows (WSL2)


TEXAS runs inside WSL2 (Windows Subsystem for Linux). Docker Desktop manages the bridge between Windows and WSL2.

**1 — Install WSL2** (skip if already installed):

Open PowerShell as Administrator and run:

```powershell
wsl --install
```

Restart your PC when prompted. This installs Ubuntu by default.

**2 — Install Docker Desktop:**

Download and install [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/).

During setup, ensure **"Use the WSL 2 based engine"** is selected.

**3 — Enable WSL2 integration:**

Open Docker Desktop → **Settings → Resources → WSL Integration**
→ enable integration for your distro (e.g. Ubuntu).

**4 — Verify from WSL2 terminal:**

Open your WSL2 distro (Ubuntu) and run:

```bash
docker info
docker compose version
```

If these fail, restart Docker Desktop and try again.
```````
```````{tab-item} macOS


Download and install [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/).

- **Apple Silicon (M1/M2/M3)**: choose the **Apple Silicon** installer.
- **Intel**: choose the **Intel chip** installer.

After installing, launch Docker Desktop from Applications and wait for it to show **"Docker Desktop is running"** in the menu bar.

Verify:

```bash
docker info
docker compose version
```

`````{admonition} Apple Silicon performance
:class: warning

The pre-built image is `linux/amd64`. On Apple Silicon it runs under QEMU emulation — Stan compilation and sampling will be noticeably slower. For repeated use, [Option A (pip or uv)](#option-a--pip-or-uv-recommended) with a native arm64 conda environment is faster.
`````

`````{admonition} macOS — Docker permissions prompt
:class: note

On first run, macOS may ask whether Docker Desktop can access your Documents or Downloads folder. Click **Allow**. If you dismiss it, the volume mount will silently fail and JupyterLab will show an empty file browser — re-run `./run.sh` and allow access when prompted.
`````
```````
````````

---

### Step 2 — Clone the repository

`````{admonition} New to git?
:class: note

`git clone` downloads a copy of the TEXAS code to your own computer — think of it like downloading a folder. You cannot accidentally break or modify the original repository. Everything runs locally on your machine.
`````

A shallow clone (`--depth 1`) is recommended — it downloads only the current state of the code without the full commit history, saving several GB of disk space.

````````{tab-set}
```````{tab-item} Linux


```bash
git clone --depth 1 https://github.com/PaleoLipidRR/TEXAS.git
cd TEXAS
chmod +x run.sh
```
```````
```````{tab-item} Windows (WSL2)


Open your WSL2 terminal (e.g. Ubuntu) and run:

```bash
git clone --depth 1 https://github.com/PaleoLipidRR/TEXAS.git
cd TEXAS
chmod +x run.sh
```

`````{note}
Clone inside the WSL2 filesystem (e.g. `~/Documents/GitHub/`) — **not** on the Windows filesystem (`/mnt/c/...`). Cloning into `/mnt/c/` causes slow I/O and file permission issues inside the container.
`````
```````
```````{tab-item} macOS


```bash
git clone --depth 1 https://github.com/PaleoLipidRR/TEXAS.git
cd TEXAS
chmod +x run.sh
```
```````
````````

---

### Step 3 — Launch

Run the interactive launcher:

```bash
./run.sh
```

You will be prompted to:

| Prompt | Recommended answer |
|---|---|
| Which profile? | `full` — JupyterLab with Stan |
| Mount Google Drive / OneDrive? | `y` if your data is there, otherwise `n` |
| Pull pre-built image from GHCR? | `Y` — downloads ~2–3 GB, no build required |

Once the image is pulled and the container starts, open **http://localhost:8890** in your browser.

`````{admonition} Port 8890, not 8888
:class: warning

`run.sh` uses port **8890** to avoid conflicts with any native JupyterLab or Anaconda installation that may already be running on port 8888 — common on Windows and macOS with Anaconda installed. The JupyterLab startup log will print `http://127.0.0.1:8890/lab` — use that URL.
`````

`````{admonition} Windows/WSL2 — kernel selector on first open
:class: note

When you open a notebook for the first time in the Docker container, JupyterLab may show a kernel name like `SI_code00_PreProcessing.ipynb (3bf86915)` in the kernel selection dialog instead of "Python 3". This is a leftover preference saved inside the `.ipynb` file from a previous session on a different machine. Click the dropdown, select **Python 3 (ipykernel)**, and click **Select** — it will work normally after that.
`````

`````{admonition} Disk space — plan for ~3.5 GB total
:class: tip

| Component | Size | Location |
|---|---|---|
| Git clone (tracked files) | ~624 MB | Where you cloned |
| Docker image — base OS + system libs | ~300 MB | Docker's internal storage |
| Docker image — conda env (Python stack + JupyterLab) | ~1.2 GB | Docker's internal storage |
| Docker image — CmdStan 2.36.0 (compiled C++ toolchain) | ~400 MB | Docker's internal storage |
| Posteriors downloaded from Zenodo | ~315 MB | `data/cache/` inside the clone |
| **Total** | **~2.8–3.5 GB** | |

The Docker image is stored in Docker's internal storage — **not** inside the cloned repo folder. On Windows, Docker Desktop uses a VHDX virtual disk that grows over time. To reclaim space later: Docker Desktop → **Troubleshoot → Clean / Purge data**, or run:
```bash
docker image rm ghcr.io/paleolipidrr/texas:latest
```
Subsequent launches after the first pull start in seconds — no re-download needed.
`````

---

### Downloading posteriors

The forward calibration posteriors (`.nc` files, ~560 MB) are stored on Zenodo and are not included in the Docker image or the repository. Download them once inside JupyterLab:

```python
import TEXAS
TEXAS.download_all()
```

This saves posteriors to `data/cache/TEXAS_posterior_cache/` inside the cloned repo, which is bind-mounted into the container — so they persist across sessions.

To check exactly where files were saved, or to list downloaded posteriors:

```python
from TEXAS.utils.paths import POSTERIOR_CACHE_DIR, SPREADSHEETS_DIR

print("Posteriors:", POSTERIOR_CACHE_DIR)
print("Training data:", SPREADSHEETS_DIR)

# List all downloaded posteriors
list(POSTERIOR_CACHE_DIR.glob("*.nc"))
```

---

## Option D — conda-lock (exact reproducible environment)

For the most reproducible setup outside of Docker, use the pre-solved conda-lock files published alongside this repository. Run these commands from a clone. Every package version and checksum is pinned — the environment will be identical on any machine of the same platform. CmdStan is bundled on all platforms — no separate install step needed.

`````{admonition} Windows — CmdStan version
:class: note

CmdStan 2.35.0 is included on Windows (the latest version compatible with `esmf` on Windows). Linux and macOS get 2.36.0. The minor version difference has no effect on TEXAS.
`````

**With `conda-lock` (multi-platform lock file — recommended):**

````````{tab-set}
```````{tab-item} Linux


```bash
conda install -c conda-forge conda-lock
conda-lock install -n texas-env conda-lock.yml
conda activate texas-env
pip install -e .
```
```````
```````{tab-item} Windows (WSL2)


Run from WSL2 terminal:

```bash
conda install -c conda-forge conda-lock
conda-lock install -n texas-env conda-lock.yml
conda activate texas-env
pip install -e .
```
```````
```````{tab-item} macOS (Apple Silicon)


```bash
conda install -c conda-forge conda-lock
conda-lock install -n texas-env conda-lock.yml   # uses conda-osx-arm64.lock
conda activate texas-env
pip install -e .
```
```````
```````{tab-item} macOS (Intel)


```bash
conda install -c conda-forge conda-lock
conda-lock install -n texas-env conda-lock.yml   # uses conda-osx-64.lock
conda activate texas-env
pip install -e .
```
```````
````````

**Without `conda-lock` (platform-specific explicit file — works with plain conda):**

```bash
# Pick the file for your platform
conda create -n texas-env --file conda-linux-64.lock    # Linux x86_64
conda create -n texas-env --file conda-osx-arm64.lock   # macOS Apple Silicon
conda create -n texas-env --file conda-osx-64.lock      # macOS Intel
conda create -n texas-env --file conda-win-64.lock      # Windows

conda activate texas-env
pip install -e .
```

---

## Option E — conda from source (development)

```bash
git clone --depth 1 https://github.com/PaleoLipidRR/TEXAS.git
cd TEXAS
conda env create -f environment.yml
conda activate texas-env
pip install -e .          # editable install — required for development
```

> **Always use `pip install -e .`** (editable mode). A plain `pip install .` or `pip install texas-psm` puts a static copy in site-packages: `STAN_MODELS_DIR` will point there (no pre-compiled binaries), and any local code changes will be silently ignored by the running kernel. After cloning, or any time you find the wrong package version is active, re-run `pip install -e .` and restart your Jupyter kernel.

The conda environment sets `CMDSTAN` automatically to the bundled CmdStan. To use a
different install (e.g. one from `cmdstanpy.install_cmdstan()`), set `CMDSTAN` yourself —
see [Setting `CMDSTAN` manually](#setting-cmdstan-manually) for PowerShell / bash / CMD
syntax — then run `texas-doctor` to confirm it resolved.

---

## Reproducing the manuscript notebooks on a new machine

The SI notebooks (`notebooks/manuscripts/SI_code00`–`SI_code03`) need more than the package: the
Stan toolchain, cached posteriors, and some external climatology/model data. Full
checklist:

### 1. Code + environment

```bash
git clone https://github.com/PaleoLipidRR/TEXAS.git
cd TEXAS
```

- **uv:** `uv sync --all-extras` (Option B). Newer stack (matplotlib 3.10, numpy 2,
  ultraplot 2.x); the notebooks use the updated plotting syntax it needs.
- **Docker:** `docker compose up` (Option C). Everything is bundled.
- **conda:** `conda env create -f environment.yml && conda activate texas-env && pip
  install -e .` (Option E). This pins `matplotlib>=3.9,<3.11` and `python=3.10`, the
  versions the notebooks were authored against.

### 2. CmdStan + environment check

Install CmdStan — Docker and conda bundle it; uv users get it in one call:

```bash
texas-install-cmdstan     # or, in Python: TEXAS.install_cmdstan()
```

Then verify everything at once:

```bash
texas-doctor      # or: python -c "import TEXAS; TEXAS.doctor()"
```

It reports cmdstanpy, the CmdStan path/version, a C++ compiler, and the cache dirs, and
prints `Stan sampling: READY` when the machine is set up.

### 3. Posteriors + training data (Zenodo)

```python
import TEXAS
TEXAS.download_all()          # forward posteriors + training CSVs → data/cache/, data/spreadsheets/
```

### 4. External data (WOA23 + model fields) — manual, public sources

`data/external/` is gitignored, so these do **not** come with the clone:

- **Regridded model fields and plate model** — the Tierney et al. (2022) and Zhu et al.
  (2019) netCDFs and the paleoDEMS plate model, read by `SI_code03` for Fig. 12. They are
  being added to the Zenodo data record; until then that figure cannot be regenerated from
  public files alone.
- **WOA23 climatology** — World Ocean Atlas 2023, decadal average `decav91C0`,
  **temperature** and **nitrate**, 0.25° grid (files like `woa23_decav91C0_t00_04.nc`,
  `woa23_decav91C0_n00_04.nc`). Download from NOAA NCEI
  (<https://www.ncei.noaa.gov/products/world-ocean-atlas>) and place them so the notebook
  paths resolve (see step 5): `…/WOA23/decav91C0/temperature/` and `…/nitrate/`.

### 5. Set the two path variables

Each notebook's setup cell defines `local_github_path` and `local_onedrive_path`. Point
them at your clone and at wherever you placed the WOA23 / external datasets:

```python
from pathlib import Path
local_github_path   = Path.home() / "Documents/GitHub/TEXAS"   # your clone
local_onedrive_path = Path.home() / "data/texas-external"      # where you put WOA23 etc.
```

Under Docker these default to `/home/micromamba/app` and `/mnt/onedrive`; on a bare
machine adjust as above.

### 6. Run

Select the `.venv` (uv) or `texas-env` (conda) kernel and run top-to-bottom.
