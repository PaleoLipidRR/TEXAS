# Installation

TEXAS can be run via Docker (recommended) or installed directly with pip or conda.

---

## Option A — Docker (recommended)

Docker bundles CmdStan, all Python dependencies, and the Stan compiler into a single image. No environment setup required.

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

---

### Step 2 — Clone the repository

A shallow clone is recommended — it downloads only the current state of the code without the full commit history (~1.3 GB of files vs. several GB with history).

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

Once the image is pulled and the container starts, open **http://localhost:8888** in your browser.

!!! tip "First run"
    The initial pull (~2–3 GB) takes a few minutes depending on your connection. Subsequent runs start in seconds — the image is cached locally.

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
