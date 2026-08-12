# Sampler budget

How many HMC iterations the TEXAS calibration actually needs, and how many the
*inverse* model needs — which turns out to be a different question with a
different answer.

The page below reports, for each model, the cheapest warmup/sampling budget that
clears four convergence gates, together with the evidence behind it: the full
grid of R̂ failures, the choice between gating on all parameters or on the
calibration parameters alone, and the inverse model's sweep over budget and *M*
scored against measured coretop SST.

Every number on it is read from the sweep's own output by
`docs/_scripts/build_sampler_budget.py`, so the page cannot drift from the run
the way a hand-written summary does.

```{raw} html
<p style="margin:1rem 0 0;">
  <a href="_static/sampler-budget.html" target="_blank" rel="noopener"><strong>Open the sampler budget report full-page →</strong></a>
</p>
<iframe src="_static/sampler-budget.html"
        title="TEXAS sampler budget — gates, grid and recommendations"
        style="width:100%;height:80vh;border:1px solid var(--pst-color-border,#ccc);border-radius:4px;margin-top:1rem;"
        loading="lazy"></iframe>
```

## Reproducing it

The sweep itself is `scripts/run_param_sensitivity.py`, which does the sampling
unattended and is resumable per fit:

```bash
python scripts/run_param_sensitivity.py all      # forward grid + proxy refits
python scripts/run_param_sensitivity.py part3    # inverse budget and M
python docs/_scripts/build_sampler_budget.py     # rebuild this page
```

`notebooks/manuscripts/SI_code2a_model_param_sensitivity_test.ipynb` runs the
same analysis interactively and draws the figures; a test fails if the two
configurations drift apart.

## Why the page ships with its data

`data/revision1/groupA/param_sensitivity/*.csv` is gitignored — the grid is
several MB of run output and does not belong in the repository. So the build
script keeps a compact `_static/sampler-budget.data.json` alongside the HTML,
holding exactly the numbers the page displays. Both are tracked, which means:

- the report is readable from any clone, with no data and no rebuild;
- `build_sampler_budget.py` reproduces it byte-for-byte from the snapshot on a
  machine that has never run the sweep;
- where the raw output *is* present, the script reads that instead and rewrites
  both files.

With neither source available the script leaves the committed page alone and
exits cleanly, so a docs deploy can never blank the report just because the data
lives on another machine.
