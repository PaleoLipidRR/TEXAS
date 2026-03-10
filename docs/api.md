# API Reference

## TEXAS

Top-level exports: high-level prediction API, Stan sampler, I/O helpers, logistic
curve functions, ensemble generation, diagnostics, and plotting utilities.

::: TEXAS
    options:
      show_root_heading: false
      members: true
      filters:
        - "^_"      # drop private names

## stan sub-package

Stan compiler, sampler, I/O layer, and inverse-temperature orchestration.

::: TEXAS.stan
    options:
      show_root_heading: false
      members: true

## data sub-package

Input data builders, data filters, and Mahalanobis screening utilities.

::: TEXAS.data
    options:
      show_root_heading: false
      members: true

## models sub-package

Pure-Python logistic and generalized-logistic functions, multivariate variants,
and classical (non-Bayesian) TEX86 calibrations.

::: TEXAS.models
    options:
      show_root_heading: false
      members: true

## ensemble sub-package

Posterior ensemble generation (`generate_ensemble`, `generate_ensemble_auto`) and
automatic model/parameter detection from posterior attributes.

::: TEXAS.ensemble
    options:
      show_root_heading: false
      members: true

## plotting sub-package

Range utilities (sample-based, density-based, suffix-specific, dataset-specific)
and prior distribution visualization.

::: TEXAS.plotting
    options:
      show_root_heading: false
      members: true

## diagnostics

Sampler diagnostic summary (divergences, R-hat, ESS, E-BFMI) and tabular summary
helpers.

::: TEXAS.diagnostics
    options:
      show_root_heading: false
      members: true
