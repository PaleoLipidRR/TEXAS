# syntax=docker/dockerfile:1.7

########## Stage 1: builder (root only) ##########
FROM mambaorg/micromamba:1.5.10-bookworm AS builder
SHELL ["/bin/bash", "-lc"]
ENV MAMBA_DOCKERFILE_ACTIVATE=1
USER root

ARG CMDSTAN_VERSION=2.36.0

# System build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gfortran make wget tar git \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN useradd -ms /bin/bash micromamba

# Copy lock file and create env
COPY --chown=micromamba:micromamba conda-lock.yml .
RUN micromamba create -n texas-env -f conda-lock.yml && micromamba clean -a -y

# Step 1: Install PyPI packages first
RUN micromamba run -n texas-env pip install --no-cache-dir baysplinepy baysparpy pygwalker pykrige

# Step 2: Copy the TEXAS package (pyproject.toml + src together so pip can resolve the project)
COPY --chown=micromamba:micromamba pyproject.toml /home/micromamba/texas-pkg/
COPY --chown=micromamba:micromamba ./src/TEXAS /home/micromamba/texas-pkg/src/TEXAS

# Step 3: Install TEXAS (regular install — editable makes no sense in an image)
RUN micromamba run -n texas-env pip install --no-cache-dir /home/micromamba/texas-pkg

# ---- Build CmdStan ----
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

# Runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgfortran5 git sudo \
    libglib2.0-0 libsm6 libxrender1 libfreetype6 libpng16-16 \
    ocl-icd-libopencl1 clinfo \
 && rm -rf /var/lib/apt/lists/*

# Create runtime user and working directories
RUN useradd -ms /bin/bash micromamba \
 && mkdir -p /home/micromamba/app/src \
 && chown -R micromamba:micromamba /home/micromamba/app

# Allow passwordless sudo
RUN echo "micromamba ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/micromamba-nopasswd

WORKDIR /home/micromamba/app

# Copy environment, CmdStan, and source code
COPY --from=builder --chown=micromamba:micromamba /opt/conda /opt/conda
COPY --from=builder --chown=micromamba:micromamba /opt/cmdstan /opt/cmdstan

USER micromamba

# Environment variables
ENV MAMBA_DOCKERFILE_ACTIVATE=1
ENV MAMBA_DEFAULT_ENV=texas-env
ENV MAMBA_ROOT_PREFIX=/opt/conda
ENV MAMBA_EXE=/bin/micromamba
ENV PATH="/opt/conda/envs/texas-env/bin:$PATH"
ENV CMDSTAN=/opt/cmdstan/cmdstan-2.36.0
ENV PATH="$CMDSTAN/bin:$PATH"

# Runtime fixes
ENV PROJ_LIB=/opt/conda/envs/texas-env/share/proj
ENV ESMFMKFILE=/opt/conda/envs/texas-env/lib/esmf.mk

CMD ["bash"]
