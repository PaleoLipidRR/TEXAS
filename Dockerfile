# syntax=docker/dockerfile:1.7

########## Stage 1: builder (root only) ##########
# Newer image helps avoid older libsolv crashes
FROM mambaorg/micromamba:1.5.10-bookworm AS builder
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

# ---- Ensure python/pip in base (modify existing env; DON'T create) ----
RUN micromamba install -y -n base -c conda-forge --strict-channel-priority \
    python=3.10 pip \
 && micromamba clean -a -y

# ---- Core scientific stack ----
RUN micromamba install -y -n base -c conda-forge --strict-channel-priority \
    "matplotlib=3.4.*" "proplot=0.9.7" "setuptools<81" cmocean \
    numpy pandas scipy scikit-learn xarray dask distributed zarr \
    jupyterlab ipywidgets jupyterlab_widgets ipympl tqdm \
    duckdb pyarrow sqlalchemy pydantic typing-extensions \
    libstdcxx-ng libgcc-ng freetype libpng openpyxl \
 && micromamba clean -a -y

# ---- Geo stack (without GDAL/Fiona) ----
RUN micromamba install -y -n base -c conda-forge --strict-channel-priority \
    shapely cartopy "pyproj<3.6" \
    geopandas rtree pyogrio mapclassify \
    geopy plotly anywidget ipylab pygwalker \
 && micromamba clean -a -y

# ---- NetCDF/HDF + xesmf + pinned ESMF/MPI/HDF5/libnetcdf ----
RUN micromamba install -y -n base -c conda-forge --strict-channel-priority \
    netcdf4 h5netcdf cftime \
    xesmf esmpy=8.9.0 esmf=8.9.0 mpich=4.3.1 hdf5=1.14.6 libnetcdf=4.9.2 \
 && micromamba clean -a -y

# Fail fast if imports break
RUN micromamba run -n base python - <<'PY'
import esmpy, xesmf, numpy, xarray, geopandas, pyogrio
print("OK: esmpy", esmpy.__version__, "xesmf", xesmf.__version__)
PY

# ---- Build CmdStan under /opt/cmdstan ----
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

# Runtime libs only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxrender1 pkg-config libgfortran5 git \
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
ENV CMDSTAN=/opt/cmdsan/cmdstan-2.36.0
ENV PATH="$CMDSTAN/bin:$PATH"
ENV PIP_NO_CACHE_DIR=1

# Copy in just what's needed to install first (better cache)
COPY --chown=micromamba:micromamba pyproject.toml .
# COPY --chown=micromamba:micromamba README.md .   # if your build reads it

COPY --chown=micromamba:micromamba TEXAS/ ./TEXAS/

# Install inside the conda env (no login shell)
RUN micromamba run -n base python -m pip install --no-deps -e . \
 && micromamba run -n base python -m pip install --no-deps baysplinepy baysparpy \
 && rm -rf ~/.cache/pip

# Bring in the rest last to maximize cache hits
COPY --chown=micromamba:micromamba . .

CMD ["bash"]
