# syntax=docker/dockerfile:1.7

########## Stage 1: builder (root only) ##########
FROM mambaorg/micromamba:1.5.10-noble AS builder
SHELL ["/bin/bash", "-lc"]
ENV MAMBA_DOCKERFILE_ACTIVATE=1
USER root

# System build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN userdel -r ubuntu 2>/dev/null || true \
 && groupdel ubuntu 2>/dev/null || true \
 && useradd -ms /bin/bash micromamba

# Copy lock file and create env
COPY --chown=micromamba:micromamba conda-lock.yml .
RUN micromamba create -n texas-env -f conda-lock.yml && micromamba clean -a -y

# Step 1: Install PyPI packages first
RUN micromamba run -n texas-env pip install --no-cache-dir pygwalker pykrige odrpack ultraplot

# Step 2: Copy the TEXAS package (pyproject.toml + src together so pip can resolve the project)
COPY --chown=micromamba:micromamba pyproject.toml /home/micromamba/texas-pkg/
COPY --chown=micromamba:micromamba ./src/TEXAS /home/micromamba/texas-pkg/src/TEXAS

# Step 3: Install TEXAS (regular install — editable makes no sense in an image)
RUN micromamba run -n texas-env pip install --no-cache-dir /home/micromamba/texas-pkg

# Verify CmdStan is discoverable via the conda-lock-bundled package
RUN micromamba run -n texas-env python -c \
    "from TEXAS.utils.paths import find_cmdstan; p = find_cmdstan(); print('CmdStan OK:', p)"

########## Stage 2: final (non-root runtime) ##########
FROM mambaorg/micromamba:1.5.10-noble
USER root

# Runtime system dependencies (Ubuntu 24.04 Noble ships GCC 13 — compatible with conda TBB)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgfortran5 git sudo \
    libglib2.0-0 libsm6 libxrender1 libfreetype6 libpng16-16 \
    ocl-icd-libopencl1 clinfo \
 && rm -rf /var/lib/apt/lists/*

# Remove the ubuntu user that ubuntu:noble ships with (UID 1000) so that
# useradd assigns UID 1000 to micromamba.  Without this, micromamba lands at
# UID 1001 and updateRemoteUserUID fails silently because UID 1000 is taken,
# leaving the container user unable to write to bind-mounted workspace files.
RUN userdel -r ubuntu 2>/dev/null || true \
 && groupdel ubuntu 2>/dev/null || true \
 && useradd -ms /bin/bash micromamba \
 && mkdir -p /home/micromamba/app/src \
 && chown -R micromamba:micromamba /home/micromamba/app

# Allow passwordless sudo
RUN echo "micromamba ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/micromamba-nopasswd

WORKDIR /home/micromamba/app

# Copy conda environment (CmdStan is bundled inside via conda-lock)
COPY --from=builder --chown=micromamba:micromamba /opt/conda /opt/conda

USER micromamba

# Environment variables
ENV MAMBA_DOCKERFILE_ACTIVATE=1
ENV MAMBA_DEFAULT_ENV=texas-env
ENV MAMBA_ROOT_PREFIX=/opt/conda
ENV MAMBA_EXE=/bin/micromamba
ENV PATH="/opt/conda/envs/texas-env/bin:$PATH"

# Runtime fixes
ENV PROJ_LIB=/opt/conda/envs/texas-env/share/proj
ENV ESMFMKFILE=/opt/conda/envs/texas-env/lib/esmf.mk

CMD ["bash"]
