# Archive

Nothing here is deleted and nothing here ships in the wheel. Each sub-archive
answers a different question about the project's history.

| directory | what it holds | why it is not in the live tree |
|---|---|---|
| `submission-2026-04/` | The initial submission: 8 Stan models, 2 SI notebooks, 32 figures | Superseded by the revision. The additive (beta-on-mu) model here is still the revision's comparison arm, and its posteriors remain downloadable, so the code that reads them is live even though the model is not. |
| `pre-submission/stan_models/` | 15 development models, plus 4 pre-annotated variants under `pre_annotated/` | Never submitted. They declare parameters the project has since dropped (`Q_crtp`, `sigma_scaledRI_crtp`), which is why `tests/test_streamlit_params.py` deliberately does not scan this tree. |
| `exploratory/gridT-inversion/` | The gridded-inversion explainer, its two write-ups and six figures | Explored during the revision and left out of the resubmission. Provenance, not reviewer evidence. |
| `presentations/` | `IMOG_presentation.ipynb` | A conference talk, not part of the analysis. |

## Running an archived Stan model

`pyproject.toml` globs `stan_models/*.stan` non-recursively, so nothing under
`archive/` reaches the wheel. To run an archived model from a source checkout,
pass an absolute path — `StanCompiler.resolve_stan_path()` passes absolute paths
straight through:

```python
from pathlib import Path
from TEXAS import get_posterior

stan_file = Path("archive/submission-2026-04/stan_models/"
                 "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv.stan").resolve()
post, diag = get_posterior(data, "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv",
                           temptype="SST", proxy_name="scaledRI",
                           stan_file=str(stan_file))
```

There is no `model_dir=` route through `get_posterior()`; it builds a
`StanCompiler()` with no arguments.

The `submission-2026-04/` models also still resolve by plain stem through
`resolve_stan_path()`'s archive fallback (`STAN_ARCHIVE_DIR` points only at
`archive/submission-2026-04/stan_models`), which is inert in a wheel install
because `archive/` is not packaged. The 15 `pre-submission/stan_models/`
models (and their 4 `pre_annotated/` variants) are **not** covered by that
fallback and are reachable only by absolute path, as shown above.
