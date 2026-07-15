# Installation

TEXAS can be run via Docker (recommended) or installed directly with pip, [uv](#using-uv-instead-of-pip), or conda.

| Option | Best for | CmdStan handled for you? |
|---|---|---|
| **A — Docker** | Zero setup; reproducible; no Python/Stan toolchain to manage | ✅ bundled in the image |
| **B — conda-lock** | Exact pinned reproducibility outside Docker | ✅ bundled on all platforms |
| **C — pip / uv** | Lightweight installs into an existing Python/venv workflow | ❌ one extra step (see below) |
| **D — from source** | Development (editable install) | ❌ conda-managed or manual |

> **CmdStan is never a Python package.** Options A and B bundle it; options C and D require one extra step to install the CmdStan C++ toolchain (and, on a bare machine, a C++ compiler). This is a property of Stan itself — every model compiles to a native binary — not a limitation of pip or uv. See [CmdStan: install, discovery, and verification](#cmdstan-install-discovery-and-verification).

---

## Option A — Docker (recommended)

Docker bundles CmdStan, all Python dependencies, and the Stan compiler into a single image. No environment setup required.

**Accounts you need before starting:**

| Service | Required? | Notes |
|---|---|---|
| [Docker account](https://app.docker.com/signup) | ✅ Free account | Required to download and run Docker Desktop on Windows and macOS |
| GitHub | ❌ No | Cloning and pulling the pre-built image are both anonymous |
| Zenodo | ❌ No | Downloading posteriors is anonymous |

!!! note "Linux users"
    Docker Engine on Linux does not require a Docker account — install it directly via `apt` without signing in.

### Step 1 — Install Docker

=== "Linux"

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

=== "Windows (WSL2)"

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

=== "macOS"

    Download and install [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/).

    - **Apple Silicon (M1/M2/M3)**: choose the **Apple Silicon** installer.
    - **Intel**: choose the **Intel chip** installer.

    After installing, launch Docker Desktop from Applications and wait for it to show **"Docker Desktop is running"** in the menu bar.

    Verify:

    ```bash
    docker info
    docker compose version
    ```

    !!! warning "Apple Silicon performance"
        The pre-built image is `linux/amd64`. On Apple Silicon it runs under QEMU emulation — Stan compilation and sampling will be noticeably slower. For repeated use, [Option C (pip + conda)](#option-c-conda-lock-exact-reproducible-environment) with a native arm64 conda environment is faster.

    !!! note "macOS — Docker permissions prompt"
        On first run, macOS may ask whether Docker Desktop can access your Documents or Downloads folder. Click **Allow**. If you dismiss it, the volume mount will silently fail and JupyterLab will show an empty file browser — re-run `./run.sh` and allow access when prompted.

---

### Step 2 — Clone the repository

!!! note "New to git?"
    `git clone` downloads a copy of the TEXAS code to your own computer — think of it like downloading a folder. You cannot accidentally break or modify the original repository. Everything runs locally on your machine.

A shallow clone (`--depth 1`) is recommended — it downloads only the current state of the code without the full commit history, saving several GB of disk space.

=== "Linux"

    ```bash
    git clone --depth 1 https://github.com/PaleoLipidRR/TEXAS.git
    cd TEXAS
    chmod +x run.sh
    ```

=== "Windows (WSL2)"

    Open your WSL2 terminal (e.g. Ubuntu) and run:

    ```bash
    git clone --depth 1 https://github.com/PaleoLipidRR/TEXAS.git
    cd TEXAS
    chmod +x run.sh
    ```

    !!! note
        Clone inside the WSL2 filesystem (e.g. `~/Documents/GitHub/`) — **not** on the Windows filesystem (`/mnt/c/...`). Cloning into `/mnt/c/` causes slow I/O and file permission issues inside the container.

=== "macOS"

    ```bash
    git clone --depth 1 https://github.com/PaleoLipidRR/TEXAS.git
    cd TEXAS
    chmod +x run.sh
    ```

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

!!! warning "Port 8890, not 8888"
    `run.sh` uses port **8890** to avoid conflicts with any native JupyterLab or Anaconda installation that may already be running on port 8888 — common on Windows and macOS with Anaconda installed. The JupyterLab startup log will print `http://127.0.0.1:8890/lab` — use that URL.

!!! note "Windows/WSL2 — kernel selector on first open"
    When you open a notebook for the first time in the Docker container, JupyterLab may show a kernel name like `SI_code1_PreProcessing_finalized.ipynb (3bf86915)` in the kernel selection dialog instead of "Python 3". This is a leftover preference saved inside the `.ipynb` file from a previous session on a different machine. Click the dropdown, select **Python 3 (ipykernel)**, and click **Select** — it will work normally after that.

!!! tip "Disk space — plan for ~3.5 GB total"
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

## Option B — conda-lock (exact reproducible environment)

For the most reproducible setup outside of Docker, use the pre-solved conda-lock files published alongside this repository. Every package version and checksum is pinned — the environment will be identical on any machine of the same platform. CmdStan is bundled on all platforms — no separate install step needed.

!!! note "Windows — CmdStan version"
    CmdStan 2.35.0 is included on Windows (the latest version compatible with `esmf` on Windows). Linux and macOS get 2.36.0. The minor version difference has no effect on TEXAS.

**With `conda-lock` (multi-platform lock file — recommended):**

=== "Linux"

    ```bash
    conda install -c conda-forge conda-lock
    conda-lock install -n texas-env conda-lock.yml
    conda activate texas-env
    pip install texas-psm
    ```

=== "Windows (WSL2)"

    Run from WSL2 terminal:

    ```bash
    conda install -c conda-forge conda-lock
    conda-lock install -n texas-env conda-lock.yml
    conda activate texas-env
    pip install texas-psm
    ```

=== "macOS (Apple Silicon)"

    ```bash
    conda install -c conda-forge conda-lock
    conda-lock install -n texas-env conda-lock.yml   # uses conda-osx-arm64.lock
    conda activate texas-env
    pip install texas-psm
    ```

=== "macOS (Intel)"

    ```bash
    conda install -c conda-forge conda-lock
    conda-lock install -n texas-env conda-lock.yml   # uses conda-osx-64.lock
    conda activate texas-env
    pip install texas-psm
    ```

**Without `conda-lock` (platform-specific explicit file — works with plain conda):**

```bash
# Pick the file for your platform
conda create -n texas-env --file conda-linux-64.lock    # Linux x86_64
conda create -n texas-env --file conda-osx-arm64.lock   # macOS Apple Silicon
conda create -n texas-env --file conda-osx-64.lock      # macOS Intel
conda create -n texas-env --file conda-win-64.lock      # Windows

conda activate texas-env
pip install texas-psm
```

---

## Option C — pip install (Python users)

!!! warning
    Do not run `pip install` against the system Python. Modern Debian/Ubuntu systems mark the system Python as externally managed (PEP 668) and will refuse the install. Always install into a virtual environment first.

=== "Linux / macOS / Windows (WSL2)"

    Run from a bash terminal. For Windows, open your WSL2 terminal (not PowerShell or CMD).

    **Step 1 — create and activate an isolated environment:**

    ```bash
    conda create -n texas-env python=3.10 pip
    conda activate texas-env
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

=== "Windows (native Anaconda Prompt)"

    Run all commands from the **Anaconda Prompt** (not PowerShell or CMD).

    **Step 1 — create and activate an environment:**

    ```cmd
    conda create -n texas-env python=3.10 pip
    conda activate texas-env
    ```

    **Step 2 — install CmdStan via conda-forge** (pre-built — no compiler needed):

    ```cmd
    conda install -c conda-forge cmdstan=2.36.0
    ```

    **Step 3 — install TEXAS:**

    ```cmd
    pip install texas-psm
    ```

    !!! warning "Windows-specific pitfalls"
        - Do **not** install `m2w64-toolchain` — it conflicts with the conda-forge `cmdstan` package.
        - Do **not** use `TBB_CXX_TYPE=gcc` — that is Linux/macOS syntax and will fail in CMD.
        - Do **not** run `cmdstanpy.install_cmdstan()` — the conda-forge package is pre-compiled; calling `install_cmdstan()` will try to compile from source and fail.

=== "Google Colab"

    ```python
    !pip install texas-psm
    import TEXAS
    TEXAS.install_cmdstan()      # installs CmdStan to /root/.cmdstan and verifies
    ```

    Colab runtimes are **ephemeral** — `/root/.cmdstan` is wiped when the runtime
    resets or disconnects, so re-run `TEXAS.install_cmdstan()` once per new session.
    It compiles CmdStan (~2–5 min) using Colab's preinstalled `g++`/`make`, and sets
    `TBB_CXX_TYPE=gcc` for you.

### Using uv instead of pip

[uv](https://docs.astral.sh/uv/) is a fast, drop-in replacement for `pip`/`venv`. TEXAS and all of its core dependencies are published on PyPI, so uv installs it with no extra configuration.

**Standalone environment:**

```bash
uv venv                       # create .venv/ with an isolated interpreter
source .venv/bin/activate
uv pip install cmdstanpy
python -c "import cmdstanpy; cmdstanpy.install_cmdstan(version='2.36.0')"
uv pip install texas-psm      # add extras as needed, e.g. "texas-psm[plotting]"
```

**As a dependency of a uv-managed project:**

```bash
uv add texas-psm              # or: uv add "texas-psm[plotting]"
```

**Cloning the repo (contributor / notebook workflow):**

To develop TEXAS or run the manuscript notebooks (`notebooks/manuscripts/SI_code*.ipynb`) from a checkout, let uv own a project `.venv`:

```bash
git clone --depth 1 https://github.com/PaleoLipidRR/TEXAS.git
cd TEXAS
uv sync --all-extras          # creates .venv/ and installs everything, incl. Jupyter + notebook deps
```

Then select `.venv/bin/python` as your notebook kernel (VS Code auto-detects it; for a named Jupyter kernel run `uv run python -m ipykernel install --user --name texas-uv`).

!!! tip "Which sync command?"
    - `uv sync` — core runtime only (no Jupyter). Cannot serve a notebook kernel.
    - `uv sync --extra dev` — adds Jupyter/ipykernel + the notebook analysis deps (scikit-learn, statsmodels, seaborn, openpyxl, odrpack).
    - `uv sync --all-extras` — the above **plus** plotting (ultraplot), maps (cartopy, regionmask), and regrid (geopandas, xesmf). Recommended for the SI notebooks.

!!! note "Python 3.12"
    uv on Python 3.12 is supported: the project pins a `[tool.uv]` override so `pyproj` resolves to a version with a 3.12 wheel (the `regrid` extra's `pyproj<3.6` cap has no 3.12 wheel and would otherwise force a source build). No action needed on your part.

!!! note "Optional extras under uv"
    - `texas-psm[plotting]` (ultraplot) and `texas-psm[maps]` (cartopy, regionmask) install cleanly from PyPI.
    - The `regrid` extra installs `xesmf` and the rest of the geo stack from PyPI, but **`esmpy` (the ESMF bindings xesmf needs at runtime) is not on PyPI** — install it from conda-forge: `conda install -c conda-forge esmpy`. (esmpy is deliberately kept out of the extra: a non-PyPI package in *any* extra makes `uv lock` fail for the whole project.) For heavy regridding, prefer the conda environment (Option D).
    - CmdStan is **not** a Python package — install it once via `cmdstanpy.install_cmdstan()` or conda-forge `cmdstan`, exactly as for the pip route above.

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

=== "PowerShell (Windows)"

    ```powershell
    # current session
    $env:CMDSTAN = "$HOME\.cmdstan\cmdstan-2.36.0"
    # persist across sessions
    setx CMDSTAN "$HOME\.cmdstan\cmdstan-2.36.0"   # reopen the terminal to pick it up
    # confirm
    echo $env:CMDSTAN
    ```

=== "bash / zsh (Linux, macOS, WSL2)"

    ```bash
    # current session
    export CMDSTAN=~/.cmdstan/cmdstan-2.36.0
    # persist: add the same line to ~/.bashrc or ~/.zshrc
    # confirm
    echo "$CMDSTAN"
    ```

=== "CMD / Anaconda Prompt (Windows)"

    ```cmd
    set CMDSTAN=%USERPROFILE%\.cmdstan\cmdstan-2.36.0
    echo %CMDSTAN%
    ```

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

## Option D — conda from source (development)

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

The SI notebooks (`notebooks/manuscripts/SI_code1–3`) need more than the package: the
Stan toolchain, cached posteriors, and some external climatology/model data. Full
checklist:

### 1. Code + environment

```bash
git clone https://github.com/PaleoLipidRR/TEXAS.git
cd TEXAS
```

- **conda (recommended for the notebooks — the tested stack):** `conda env create -f
  environment.yml && conda activate texas-env && pip install -e .`. This pins
  `matplotlib<3.5` and `python=3.10`, the versions the notebooks were authored against.
- **uv (lightweight):** `uv sync --all-extras`. Newer stack (matplotlib 3.10, numpy 2,
  ultraplot 2.x) — a few notebook plotting idioms need the updated syntax the notebooks
  now use.

### 2. CmdStan + environment check

Install CmdStan — Options A/B bundle it; pip/uv users get it in one call:

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

The `data/external/` folder (paleoDEMS plate model, Tierney22 / Zhu19 netCDFs) travels
with the clone. Two datasets do **not** and must be fetched separately:

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

Select the `texas-env` (conda) or `.venv` (uv) kernel and run top-to-bottom.
