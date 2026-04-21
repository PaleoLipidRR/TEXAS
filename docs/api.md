# API Reference

## Top-level API

High-level functions for temperature prediction, posterior download, and data I/O.
These are the functions most users will call directly — no knowledge of the underlying
Stan models is required.

::: TEXAS
    options:
      show_root_heading: false
      members: true
      filters:
        - "^_"

## stan

Functions for running the Stan sampler, compiling Stan models, and saving/loading
posterior distributions. Use these if you need to re-run the forward calibration
or customize sampling parameters.

::: TEXAS.stan
    options:
      show_root_heading: false
      members: true

## data

Functions for building the data dictionaries passed to Stan, cleaning and filtering
GDGT datasets, and screening outliers via Mahalanobis distance.

::: TEXAS.data
    options:
      show_root_heading: false
      members: true

## models

Pure-Python implementations of the generalized logistic calibration curve,
multivariate variants (GDGT-2/3, NO₃ corrections), and classical (non-Bayesian)
TEX86 calibration equations for comparison.

::: TEXAS.models
    options:
      show_root_heading: false
      members: true

## ensemble

Functions for drawing calibration curve percentiles from a posterior distribution —
useful for visualizing the calibrated SST–RI relationship and its uncertainty envelope.

::: TEXAS.ensemble
    options:
      show_root_heading: false
      members: true

## plotting

Utilities for visualizing posterior distributions, prior choices, and calibration
uncertainty ranges.

::: TEXAS.plotting
    options:
      show_root_heading: false
      members: true

## diagnostics

Functions for assessing Stan sampler health: divergences, R-hat (convergence),
effective sample size (ESS), and E-BFMI (energy). Always check these after
running a forward calibration.

::: TEXAS.diagnostics
    options:
      show_root_heading: false
      members: true
