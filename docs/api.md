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

```{eval-rst}
.. autofunction:: TEXAS.predict.compute_scaledRI
```

### Predict proxy from T

```{eval-rst}
.. autofunction:: TEXAS.predict.predict_proxy_from_T
```

### Predict T from proxy observations

```{eval-rst}
.. autofunction:: TEXAS.predict.predict_T_from_proxyObs
```

---

## Download and cache

### Download posteriors

```{eval-rst}
.. autofunction:: TEXAS.utils.download.download_posteriors
```

### Download all

```{eval-rst}
.. autofunction:: TEXAS.utils.download.download_all
```

### Download training data

```{eval-rst}
.. autofunction:: TEXAS.utils.download.download_training_data
```

### List posteriors

```{eval-rst}
.. autofunction:: TEXAS.stan.io.list_posteriors
```

### Set cache directory

```{eval-rst}
.. autofunction:: TEXAS.utils.paths.set_cache_dir
```

---

## Data builders

### Build forward data

```{eval-rst}
.. autofunction:: TEXAS.data.builder.build_fwd_data
```

### Build invT input data

```{eval-rst}
.. autofunction:: TEXAS.data.builder.build_invT_inputData
```

### WOA23 NO₃ lookup

```{eval-rst}
.. autofunction:: TEXAS.data.ocean_lookup.lookup_no3_from_woa
```

---

## Forward calibration

### Get posterior

```{eval-rst}
.. autofunction:: TEXAS.stan.sampler.get_posterior
```

### Save posterior

```{eval-rst}
.. autofunction:: TEXAS.stan.io.save_posterior
```

### Load posterior

```{eval-rst}
.. autofunction:: TEXAS.stan.io.load_posterior
```

---

## Ensemble

### Generate ensemble (auto)

```{eval-rst}
.. autofunction:: TEXAS.ensemble.generator.generate_ensemble_auto
```

### Detect model and params

```{eval-rst}
.. autofunction:: TEXAS.ensemble.detection.detect_model_and_params
```

---

## Diagnostics

### Sampler diagnostics

```{eval-rst}
.. autofunction:: TEXAS.diagnostics.summarize_sampler_diagnostics
```

### Summary table

```{eval-rst}
.. autofunction:: TEXAS.diagnostics.create_summary_table
```

---

## Plotting

### Plot prior distributions

```{eval-rst}
.. autofunction:: TEXAS.plotting.prior_plot.plot_prior_distributions
```
