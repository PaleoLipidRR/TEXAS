# TEXAS Project

... (Your project description) ...

---

## ⚙️ Installation & Setup

This project uses the Stan modeling language via `cmdstanpy`. To ensure a compatible and reproducible environment, please follow these steps.

**Prerequisites**: You must have [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or Anaconda installed.

## OPTION 1: Docker Image
### 1. Install Docker: 
Follow the instructions at docker.com.

### 2. Build the Image: From the project's root directory, run:
```bash
docker build -t texas-package .
```

### 3. Run the Container: To start an interactive session inside the pre-configured environment, run:
```bash
docker run -it -v "$(pwd)":/app texas-package bash
```

You are now inside the container with CmdStan and TEXAS ready to use.

---------------------------------------------------------------

## OPTION 2
### 1. Clone the Repository

First, clone this repository to your local machine:
```bash
git clone [https://github.com/PaleoLipidRR/TEXAS.git](https://github.com/PaleoLipidRR/TEXAS.git)
cd TEXAS
```

### 2. Create the Conda Environment
Use the provided environment.yml file to create a Conda environment with all the necessary compilers and Python packages.
```bash
conda env create -f environment.yml
```

### 3. Activate the Environment
Activate the new environment. You will need to do this every time you work on the project.
```bash
conda activate texas-env
```

### 4. Install the CmdStan Toolchain (Crucial Step)
Now, we need to build the CmdStan C++ toolchain. The Conda C++ compiler requires a special flag to be set for this one-time installation. Run the following command exactly as written:
Activate the new environment. You will need to do this every time you work on the project.
```bash
TBB_CXX_TYPE=gcc python -c "import cmdstanpy; cmdstanpy.install_cmdstan()"
```
This command might take several minutes to run as it compiles Stan. You only need to do this once per machine.

### 5. Verify the Installation
You're all set! You can now launch Jupyter Lab and run the notebooks to reproduce the analysis.
```bash
jupyter lab
```

Development Environment Setup
This project uses a Docker-based development container to ensure a consistent and reproducible environment. All required software, libraries, and tools are defined within the container.

Prerequisites
Before you begin, make sure you have the following installed on your local machine:

Git

Docker Desktop (or Docker Engine on Linux)

Visual Studio Code

The Dev Containers extension for VS Code.

(Optional for GPU): A compatible NVIDIA GPU with up-to-date drivers and the NVIDIA Container Toolkit.

Getting Started
Clone the Repository

Bash

git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
Open in VS Code
Open the cloned project folder in VS Code.

Bash

code .
Reopen in Container
VS Code will detect the .devcontainer folder and a notification will appear in the bottom-right corner.

Click the "Reopen in Container" button.

Build the Environment
The first time you open the container, Docker will build the image from the Dockerfile. This will take several minutes as it downloads, installs, and compiles all dependencies (Python, Stan, etc.). Subsequent launches will be much faster thanks to Docker's caching.

Working in the Container
Once the container is running, you will be in a fully configured environment.

Terminal: You can open a terminal in VS Code (Terminal > New Terminal). It should automatically activate the texas-env conda environment. If not, you can activate it manually:

Bash

micromamba activate texas-env
Jupyter Notebooks: You can open and run .ipynb files directly. VS Code will use the Python interpreter from the texas-env environment.

Hardware Configuration (CPU vs. GPU)
You can easily switch between CPU-only and GPU-accelerated modes by making a small change to the project's configuration.

Using a GPU (Recommended)
To enable GPU support for running Stan models with OpenCL, edit the .devcontainer/devcontainer.json file and ensure the runArgs section includes the --gpus all flag:

JSON

  "runArgs": [
    "--init",
    "--shm-size=8g",
    "--gpus", "all"
  ],
Running on a CPU-Only Machine
If your machine does not have a compatible NVIDIA GPU, simply comment out or remove the --gpus all lines from .devcontainer/devcontainer.json before building the container:

JSON

  "runArgs": [
    "--init",
    "--shm-size=8g"
    //"--gpus", "all"
  ],
The container will start normally, and your Stan models will run on the CPU.