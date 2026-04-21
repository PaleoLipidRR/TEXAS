# Installation

TEXAS can be run via Docker (recommended) or installed directly with pip or conda.

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

---

## Option B — pip install (Python users)

=== "Linux / macOS"

    **Step 1 — create and activate an isolated environment:**

    ```bash
    # conda (recommended)
    conda create -n texas-env python=3.10 pip
    conda activate texas-env

    # or plain venv
    python3 -m venv .venv && source .venv/bin/activate
    ```

    **Step 2 — install CmdStan** (required before importing TEXAS):

    ```bash
    pip install cmdstanpy
    TBB_CXX_TYPE=gcc python -c "import cmdstanpy; cmdstanpy.install_cmdstan(version='2.36.0')"
    ```

    **Step 3 — install TEXAS:**

    ```bash
    pip install texas-psm
    ```

=== "Windows (WSL2)"

    Run all commands from your WSL2 terminal (not PowerShell or CMD).

    **Step 1 — create and activate an environment:**

    ```bash
    conda create -n texas-env python=3.10 pip
    conda activate texas-env
    ```

    **Step 2 — install CmdStan:**

    ```bash
    pip install cmdstanpy
    TBB_CXX_TYPE=gcc python -c "import cmdstanpy; cmdstanpy.install_cmdstan(version='2.36.0')"
    ```

    **Step 3 — install TEXAS:**

    ```bash
    pip install texas-psm
    ```

=== "Windows (native Conda)"

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

---

## Option C — conda-lock (exact reproducible environment)

Installs every package at a pinned version using pre-solved lock files. CmdStan is included — no separate install step needed.

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

---

## Option D — conda from source (development)

```bash
git clone --depth 1 https://github.com/PaleoLipidRR/TEXAS.git
cd TEXAS
conda env create -f environment.yml
conda activate texas-env
pip install -e .
```

> **Always use `pip install -e .`** (editable mode). A plain `pip install .` puts a static copy in site-packages — local code changes will be ignored by the running kernel.
