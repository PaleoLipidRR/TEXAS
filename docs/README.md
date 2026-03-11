# TEXAS Documentation

This directory contains the MkDocs source for the TEXAS package documentation.

## Building the docs locally

```bash
# From the repo root
conda activate texas-env
pip install mkdocs mkdocs-material mkdocstrings[python]
mkdocs serve
```

Then open `http://127.0.0.1:8000` in your browser.

## Structure

| File | Contents |
|------|----------|
| `index.md` | Landing page |
| `PSM.md` | Proxy system model description |
| `api.md` | Auto-generated API reference (mkdocstrings) |
| `stan_models_explanation.md` | Stan model overview |
| `stan_models_explanation_v2.md` | Detailed annotated Stan walkthrough |
| `marginalization_explainer.md` | Marginalization over parameter draws |
| `reduce_sum_for_geologists.md` | Plain-language guide to `reduce_sum` parallelization |
| `stan_reduce_sum_notes.md` | Technical Stan `reduce_sum` notes |
| `Prior_Choice_Normal_vs_Cauchy.md` | Prior sensitivity discussion |
| `stan_explanation.md` | General Stan background |

## MkDocs config

See `mkdocs.yml` in this directory for the full site navigation and plugin settings.
