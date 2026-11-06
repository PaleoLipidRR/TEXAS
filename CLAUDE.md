# CLAUDE.md

> **What is this file?** It is a briefing for AI coding assistants such as
> [Claude Code](https://docs.anthropic.com/en/docs/claude-code), which read
> it automatically when they work in this repository. It summarizes how the
> project is laid out and which conventions to follow. Human contributors may
> find it a useful map too, but the user documentation lives at
> <https://paleolipidrr.github.io/TEXAS/> and contribution guidelines are in
> [CONTRIBUTING.md](CONTRIBUTING.md).

## What this project is

**TEXAS** (TetraEther indeX of Ammonia oxidizerS; package `texas-psm`, import
`TEXAS`) is a Bayesian proxy system model for TEX₈₆ / isoGDGT
paleothermometry, accompanying Rattanasriampaipong, Tierney, Elling & Inglis
(2026, *Paleoceanography and Paleoclimatology*). TEXAS is the *sensor* model
inside the TEXAS-PSM framework; the archive model is not implemented and the
observation model propagates analytical uncertainty only.

Two stages, both run in Stan:

1. **Forward calibration** — a hierarchical generalized-logistic (S-shaped)
   curve from temperature to **Scaled Ring Index** (Scaled RI). Optional
   nonthermal predictors, the GDGT-2/GDGT-3 ratio (G23) and nitrate (NO₃⁻),
   shift the curve's location T₀:
   `Scaled RI = b + (1 − b) / (1 + exp(−k (T − T₀_eff)))^(1/ν)`,
   `T₀_eff = T₀ + γ_G23·G23 + γ_NO3·log10(NO₃)` (NO₃ term only below the cutoff).
   Output: a posterior saved as a compressed NetCDF (`.nc`).
2. **Inverse reconstruction (invT)** — temperature from observed Scaled RI,
   averaging (marginalizing) over M draws of the forward posterior.

## Setup

```bash
conda env create -f environment.yml && conda activate texas-env
pip install -e ".[all]"        # always editable for development; extras: plotting, maps, regrid, dev, all
texas-install-cmdstan          # one-time CmdStan install (developed against 2.36.0)
texas-doctor                   # diagnose the toolchain if anything fails
```

`utils/paths.py::find_cmdstan()` looks for CmdStan via the `CMDSTAN` env var,
the active environment, then `~/.cmdstan/` and other standard locations.
TEXAS never installs CmdStan on its own.

## Common commands

```bash
pytest                          # full test suite (Stan-dependent tests skip without CmdStan)
ruff check .                    # lint; CI pins ruff 0.9.7
jupyter-book build docs/        # docs → docs/_build/html/ (needs jupyter-book<2)
python docs/_scripts/build_gdgt_to_temperature.py   # rebuild the browser walkthrough page
python docs/_scripts/build_callmap.py               # rebuild the call-map page
docker compose -f docker/docker-compose.yml --profile full up   # also: docs, demo, si
```

## Package layout (`src/TEXAS/`)

| Module | Purpose |
|---|---|
| `predict.py` | Public entry points: `predict_proxy_from_T` (forward, pure Python) and `predict_T_from_proxyObs` (inverse, runs Stan) |
| `stan/` | `compiler.py` (cached `CmdStanModel`s; rebuilds stale binaries), `sampler.py` (`get_posterior`, `sampler_invT_posterior`), `io.py` (save/load posteriors), `metadata.py`, `invT.py` |
| `data/` | `builder.py` (`build_fwd_data`, `build_invT_inputData`, `InvTConfig`), `screening.py` (Mahalanobis screening), `filter.py`, `ocean_lookup.py` (modern NO₃ lookup) |
| `models/` | Pure-Python logistic curves (`logistics.py`, `multivariate.py`) and classical TEX₈₆ calibrations (`calibration.py`) |
| `ensemble/` | Posterior ensembles and model detection from posterior attributes |
| `quality.py` | Per-sample quality flags returned as `result["flags"]` |
| `diagnostics.py` | Sampler diagnostics (divergences, R-hat, ESS, E-BFMI) |
| `utils/` | Paths and cache dirs, Zenodo downloads, case-id naming, CmdStan install/doctor |
| `constants.py` | Default calibrations, predictor keys, recommended CmdStan version |
| `bundled_posteriors/` | The four posteriors shipped in the wheel |

## Stan models

Seven `.stan` files ship in `src/TEXAS/stan_models/`: three forward models
(`gen_logi_fixed_culmeso`, `..._hier_crtp_univ_priorApprox`,
`..._hier_crtp_multiv_priorApprox_eiv_t0shift`), three marginal inverse models
(`invT_..._univ_...`, `invT_..._multiv_...`, `invT_..._multiv_..._t0shift`) and
`linear_model`. Superseded models live in `archive/` (see its README) and run
only by absolute path.

Model facts that are easy to get wrong:

- The asymmetry parameter Q is fixed to 1, so **T₀ is the location, not the
  inflection point**: the steepest response is at `T₀ − ln(ν)/k`, several °C
  below T₀. There is no single thermal sensitivity to quote.
- The EIV forward model adds per-site analytical error (`sd_proxyObs`, default
  0.03) in quadrature, so `sigma_proxyObs_crtp` is process noise only. Its
  prior scale needs `R2_thermal` from a thermal-only fit, passed as data.
- G23 and NO₃ are latent (errors-in-variables) in the forward fit. A
  calibration that uses a predictor refuses to invert without it; `no3=10`
  (above the cutoff) switches the nitrate term off.
- Stan files must stay pure ASCII (`tests/test_stan_ascii.py`).

Posterior variables carry a suffix naming the data they were fitted on:
`crtp` (coretop), `culmeso` (culture + mesocosm), `culmesocore`, `meso`, `cul`.

## Posterior names and caches

Posteriors use CESM-style **case ids**, e.g. `tx.GHEB.sst.sri03.G23-N1p0`:
project · compset · target temperature (`sst`, `thm`, `cul`) · proxy
(`sri03` = Scaled RI with crenarchaeol as 3 rings) · predictors (`G23`,
`N1p0` = NO₃ with cutoff 1.0, `p0` = none). The compset letters are curve
(`G` generalized logistic), training set (`H` hierarchical coretop, `C`
culture + mesocosm), estimator (`P` prior-approximation, `E` + EIV) and
predictor structure (`U` univariate, `A` additive, `B` T₀-shift). Older long
filenames and token spellings are still read; only the case-id form is written.

- Defaults (bundled): `tx.GHEB.{sst,thm}.sri03.G23-N1p0`; thermal-only
  fallback (bundled): `tx.GHPU.{sst,thm}.sri03.p0`. Others download from
  Zenodo (`TEXAS.download_posteriors()`).
- Caches are flat (`<case>.fwd.nc`) under `~/.texas/cache/` for pip installs
  or `data/cache/` in a source checkout; `data/cache/**` is gitignored.

## Documentation

`docs/` is one Jupyter Book (`_config.yml`, `_toc.yml`; only pages in the TOC
are built), deployed to <https://paleolipidrr.github.io/TEXAS/> on push to
`main`. The API page is Sphinx autodoc of the docstrings. Pages under
`docs/_static/` are generated: edit the templates in `docs/_scripts/` and
rebuild, never the built HTML; `tests/test_gdgt_to_temperature_page.py` fails
until the walkthrough page is rebuilt after a Stan or calibration change.

## Conventions

- Keep docs and comments consistent with the accepted paper (equation,
  section and figure numbers included).
- Write comments for paleoclimate scientists: plain words first, with the
  statistical term in parentheses where it helps, e.g. "averages
  (marginalizes) over the posterior draws".
- Describe current behavior; leave history to git and `CHANGELOG.md`.
- Notebooks: `notebooks/manuscripts/` (SI figure notebooks),
  `notebooks/quickstart_*.ipynb`, `notebooks/reviewer_response/`.
