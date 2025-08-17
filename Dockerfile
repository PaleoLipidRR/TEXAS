# syntax=docker/dockerfile:1.7

########## Stage 1: builder (root only) ##########
FROM mambaorg/micromamba:1.5.10-bookworm AS builder
SHELL ["/bin/bash", "-lc"]
ENV MAMBA_DOCKERFILE_ACTIVATE=1
USER root

ARG CMDSTAN_VERSION=2.36.0

# System build dependencies for CmdStan and other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gfortran make wget tar git \
 && rm -rf /var/lib/apt/lists/*

COPY --chown=micromamba:micromamba conda-lock.yml /app/
COPY --chown=micromamba:micromamba . /app/
WORKDIR /app

# 1. Create the environment from the lock file (this will be fast)
RUN micromamba create -n texas-env -f conda-lock.yml

# 2. Install your local package into the new environment
RUN micromamba run -n texas-env pip install --no-build-isolation --no-deps -e . \
 && micromamba clean -a -y

# ---- Build CmdStan under /opt/cmdstan ----
# This still needs to be done manually as it's a special build step
RUN mkdir -p /opt/cmdstan \
 && cd /opt/cmdstan \
 && wget -q https://github.com/stan-dev/cmdstan/releases/download/v${CMDSTAN_VERSION}/cmdstan-${CMDSTAN_VERSION}.tar.gz \
 && tar -xzf cmdstan-${CMDSTAN_VERSION}.tar.gz \
 && rm cmdstan-${CMDSTAN_VERSION}.tar.gz \
 && cd cmdstan-${CMDSTAN_VERSION} \
 && make TBB_CXX_TYPE=gcc build -j4

########## Stage 2: final (non-root runtime) ##########
FROM mambaorg/micromamba:1.5.10-bookworm
USER root

# Install only runtime system libraries needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgfortran5 git \
    # Add these libraries for graphics and plotting
    libglib2.0-0 libsm6 libxrender1 libfreetype6 libpng16-16 \
 && rm -rf /var/lib/apt/lists/*

# Create runtime user and working dir
RUN useradd -ms /bin/bash micromamba \
 && install -d -o micromamba -g micromamba /home/micromamba/app
WORKDIR /home/micromamba/app

# Copy the entire conda environment and the compiled CmdStan from the builder
COPY --link --from=builder --chown=micromamba:micromamba /opt/conda /opt/conda
COPY --link --from=builder --chown=micromamba:micromamba /opt/cmdstan /opt/cmdstan
COPY --link --from=builder --chown=micromamba:micromamba /app /home/micromamba/app

USER micromamba

# Set Environment Variables
ENV MAMBA_DOCKERFILE_ACTIVATE=1
ENV MAMBA_DEFAULT_ENV=texas-env
ENV MAMBA_ROOT_PREFIX=/opt/conda
ENV MAMBA_EXE=/bin/micromamba
ENV PATH="/opt/conda/envs/texas-env/bin:$PATH"
ENV CMDSTAN=/opt/cmdstan/cmdstan-2.36.0
ENV PATH="$CMDSTAN/bin:$PATH"

# ---- FIXES FOR RUNTIME ERRORS ----
# 1. Point PROJ to its data directory to fix geospatial library errors
ENV PROJ_LIB=/opt/conda/envs/texas-env/share/proj
# 2. Add the project's source code to Python's path to fix ModuleNotFoundError
ENV PYTHONPATH=/home/micromamba/app
# 3. Point ESMF to its make file to fix xesmf import error
ENV ESMFMKFILE=/opt/conda/envs/texas-env/lib/esmf.mk

CMD ["bash"]
