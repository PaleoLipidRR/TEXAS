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