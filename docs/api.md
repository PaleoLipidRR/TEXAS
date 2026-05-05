# API Reference

## Quick reference

| Function | Description |
|---|---|
| [`compute_scaledRI`](#compute-scaled-ring-index) | Compute Scaled RI (RI₀₋₃ by default) from six isoGDGT abundances |
| [`predict_proxy_from_T`](#predict-proxy-from-t) | Forward: temperature → proxy percentiles (pure Python) |
| [`predict_T_from_proxyObs`](#predict-t-from-proxy-observations) | Inverse: proxy → temperature with full uncertainty (runs Stan) |
| [`download_posteriors`](#download-posteriors) | Download forward posteriors from Zenodo |
| [`download_training_data`](#download-training-data) | Download training CSVs + CMEMS NO₃ field |
| [`list_posteriors`](#list-posteriors) | Print and return `.nc` stems in the local cache |
| [`build_fwd_data`](#build-forward-data) | Build validated Stan data dict for forward calibration |
| [`get_posterior`](#get-posterior) | Run forward calibration Stan sampling |
| [`save_posterior`](#save-posterior) | Persist forward posterior as compressed NetCDF |
| [`load_posterior`](#load-posterior) | Load a forward or invT posterior from the cache |
| [`summarize_sampler_diagnostics`](#sampler-diagnostics) | Divergences, R-hat, ESS, E-BFMI |

---

## Prediction

### Compute Scaled Ring Index

::: TEXAS.predict.compute_scaledRI
    options:
      show_root_heading: false
      show_source: true

---

### Predict proxy from T

::: TEXAS.predict.predict_proxy_from_T
    options:
      show_root_heading: false
      show_source: true

---

### Predict T from proxy observations

::: TEXAS.predict.predict_T_from_proxyObs
    options:
      show_root_heading: false
      show_source: true

---

## Download and cache

### Download posteriors

::: TEXAS.utils.download.download_posteriors
    options:
      show_root_heading: false
      show_source: true

---

### Download all

::: TEXAS.utils.download.download_all
    options:
      show_root_heading: false
      show_source: true

---

### Download training data

::: TEXAS.utils.download.download_training_data
    options:
      show_root_heading: false
      show_source: true

---

### List posteriors

::: TEXAS.stan.io.list_posteriors
    options:
      show_root_heading: false
      show_source: true

---

### Set cache directory

::: TEXAS.utils.paths.set_cache_dir
    options:
      show_root_heading: false
      show_source: true

---

## Data builders

### Build forward data

::: TEXAS.data.builder.build_fwd_data
    options:
      show_root_heading: false
      show_source: true

---

### Build invT input data

::: TEXAS.data.builder.build_invT_inputData
    options:
      show_root_heading: false
      show_source: true

---

### WOA23 NO₃ lookup

::: TEXAS.data.ocean_lookup.lookup_no3_from_woa
    options:
      show_root_heading: false
      show_source: true

---

## Forward calibration

### Get posterior

::: TEXAS.stan.sampler.get_posterior
    options:
      show_root_heading: false
      show_source: true

---

### Save posterior

::: TEXAS.stan.io.save_posterior
    options:
      show_root_heading: false
      show_source: true

---

### Load posterior

::: TEXAS.stan.io.load_posterior
    options:
      show_root_heading: false
      show_source: true

---

## Ensemble

### Generate ensemble (auto)

::: TEXAS.ensemble.generator.generate_ensemble_auto
    options:
      show_root_heading: false
      show_source: true

---

### Detect model and params

::: TEXAS.ensemble.detection.detect_model_and_params
    options:
      show_root_heading: false
      show_source: true

---

## Diagnostics

### Sampler diagnostics

::: TEXAS.diagnostics.summarize_sampler_diagnostics
    options:
      show_root_heading: false
      show_source: true

---

### Summary table

::: TEXAS.diagnostics.create_summary_table
    options:
      show_root_heading: false
      show_source: true

---

## Plotting

### Plot prior distributions

::: TEXAS.plotting.prior_plot.plot_prior_distributions
    options:
      show_root_heading: false
      show_source: true
