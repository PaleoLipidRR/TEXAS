# TEXAS

**TEX86 And ring-index Bayesian cAlibration Software**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/PaleoLipidRR/TEXAS/blob/main/LICENSE)

A Python package for **Bayesian GDGT–temperature calibration** using Stan.
TEXAS implements a two-stage workflow — forward calibration (Ring Index → temperature) followed
by inverse temperature reconstruction — via hierarchical generalized-logistic Stan models.

---

## Documentation

- [Proxy System Model description](PSM.md) — statistical framework and model equations
- [Stan model guide](stan_models_explanation_v2.md) — annotated walkthrough of the Stan models
- [API Reference](api.md) — full Python API documentation
- [Root README](https://github.com/PaleoLipidRR/TEXAS) — quickstart, installation, and usage examples

## Further reading

- [Marginalization explainer](marginalization_explainer.md) — why TEXAS marginalizes over parameter draws
- [reduce_sum for geologists](reduce_sum_for_geologists.md) — visual guide to Stan's parallel log-likelihood
- [Prior choice: Normal vs. Cauchy](Prior_Choice_Normal_vs_Cauchy.md) — prior sensitivity discussion
