# syntax=docker/dockerfile:1.7

########## Stage 1: builder (root only) ##########
FROM mambaorg/micromamba:1.5.8-bullseye AS builder
SHELL ["/bin/bash", "-lc"]
ENV MAMBA_DOCKERFILE_ACTIVATE=1
WORKDIR /app
USER root

ARG CMDSTAN_VERSION=2.36.0

# Build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gfortran make wget tar git \
    libglib2.0-0 libsm6 libxrender1 pkg-config \
    fonts-texgyre \
 && rm -rf /var/lib/apt/lists/*

# Conda env (root-owned here; ownership fixed at COPY time)
RUN micromamba install -y -n base -c conda-forge --strict-channel-priority \
    python=3.10 pip \
    "matplotlib=3.4.*" "proplot=0.9.7" "setuptools<81" cmocean \
    numpy pandas xarray dask distributed zarr scipy scikit-learn seaborn \
    jupyterlab ipywidgets jupyterlab_widgets ipympl tqdm \
    geopy plotly shapely cartopy "pyproj<3.6" \
    duckdb pyarrow sqlalchemy pydantic anywidget ipylab pygwalker \
    cmdstanpy typing-extensions libstdcxx-ng libgcc-ng freetype libpng \
    netcdf4 h5netcdf cftime openpyxl \
    geopandas rtree fiona gdal pyogrio mapclassify \
 && micromamba clean -a -y

# Build CmdStan under /opt/cmdstan
RUN mkdir -p /opt/cmdstan \
 && cd /opt/cmdstan \
 && wget -q https://github.com/stan-dev/cmdstan/releases/download/v${CMDSTAN_VERSION}/cmdstan-${CMDSTAN_VERSION}.tar.gz \
 && tar -xzf cmdstan-${CMDSTAN_VERSION}.tar.gz \
 && rm cmdstan-${CMDSTAN_VERSION}.tar.gz \
 && cd cmdstan-${CMDSTAN_VERSION} \
 && make TBB_CXX_TYPE=gcc build -j4


########## Stage 2: final (non-root runtime) ##########
FROM mambaorg/micromamba:1.5.8-bullseye
USER root

# Runtime libs only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxrender1 pkg-config libgfortran5 git\
 && rm -rf /var/lib/apt/lists/*

# Make sure conda libs win over system libs
ENV LD_LIBRARY_PATH=/opt/conda/lib:$LD_LIBRARY_PATH

# Create runtime user and working dir in home (writable)
RUN useradd -ms /bin/bash micromamba \
 && install -d -o micromamba -g micromamba /home/micromamba/app
WORKDIR /home/micromamba/app

# Copy env + cmdstan with correct ownership (fast; no chown -R)
COPY --link --from=builder --chown=micromamba:micromamba /opt/conda /opt/conda
COPY --link --from=builder --chown=micromamba:micromamba /opt/cmdstan /opt/cmdstan

USER micromamba

# CmdStan env
ENV CMDSTAN=/opt/cmdstan/cmdstan-2.36.0
ENV PATH="$CMDSTAN/bin:$PATH"
ENV PIP_NO_CACHE_DIR=1

# Copy in just what's needed to install first (better cache)
COPY --chown=micromamba:micromamba pyproject.toml .
# If your build reads README.md, uncomment the next line:
# COPY --chown=micromamba:micromamba README.md .

COPY --chown=micromamba:micromamba TEXAS/ ./TEXAS/

# Install inside the conda env (no login shell)
RUN micromamba run -n base python -m pip install --no-deps -e . \
 && micromamba run -n base python -m pip install --no-deps baysplinepy baysparpy \
 && rm -rf ~/.cache/pip

# Bring in the rest last to maximize cache hits
COPY --chown=micromamba:micromamba . .

CMD ["bash"]
