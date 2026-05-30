# TEXAS Documentation

This directory is the source for the TEXAS documentation site, built with
[Jupyter Book](https://jupyterbook.org/) (Sphinx). It is a **single unified
book** containing the guide pages, the auto-generated API reference, the
explainers, and the interactive tutorial.

## Building the docs locally

```bash
# From the repo root
conda activate texas-env
pip install -e .            # autodoc imports TEXAS to read docstrings
pip install "jupyter-book<2"   # v1 (Sphinx) — the book uses the jb-book format
jupyter-book build docs/
```

Then open `docs/_build/html/index.html` in your browser.

> The optional map-figure deps (cartopy, regionmask) are **mocked** during the
> build (`autodoc_mock_imports` in `_config.yml`), so a core install is enough.

## Structure

| File | Contents |
|------|----------|
| `_config.yml` | Jupyter Book / Sphinx config (theme, autodoc, branding) |
| `_toc.yml` | Table of contents — the site navigation |
| `_static/` | `custom.css` branding + `texas_logo.svg` colorblock wordmark |
| `index.md` | Landing / Quickstart |
| `installation.md`, `troubleshooting.md` | Guide pages |
| `api.md` | API reference — Sphinx `autodoc` from NumPy/Google docstrings |
| `tutorial/` | Interactive Jupyter Book tutorial (Modules 1–5) |
| `PSM.md`, `stan_explanation.md`, `stan_models_explanation_v2.md` | Explainers |
| `marginalization_explainer.md`, `reduce_sum_for_geologists.md` | Stan internals, plain-language |
| `Prior_Choice_Normal_vs_Cauchy.md`, `ckdtree_nearest_ocean_explainer.md` | Method notes |

## Deployment

`.github/workflows/docs.yml` builds the book and publishes
`docs/_build/html/` to the `gh-pages` branch on every push to `main` that
touches `docs/**` or `src/TEXAS/**`. Live at
<https://paleolipidrr.github.io/TEXAS/> (tutorial at `.../tutorial/`).

## Branding

Palette and the colorblock **TEXAS** wordmark are derived from the AGU25
PP33D-1102 poster. Edit `_static/custom.css` (CSS variables at the top) to
adjust colors; `_static/texas_logo.svg` is the header logo.
