# TEXAS: Bayesian Variance Partitioning — Claude Code Guide

## Project context

This task adds Bayesian analogs to the frequentist ΔR² variance partitioning that currently
exists as a function inside a Jupyter notebook. The goal is to quantify the contributions of
`G23` (GDGT-2/GDGT-3 ratio, tracking WCA/WCB ecotype depth habitat) and surface `NO3`
(nutrient stress) to the temperature-only baseline model, using posterior draws from Stan
rather than OLS decomposition.

The manuscript is **TEXAS** (*TetraEther indeX of Ammonia oxidizerS*), targeting AGU
*Paleoceanography and Paleoclimatology*. Key collaborator: Jessica Tierney.

---

## Model structure

The TEXAS forward model (`Fwd`) predicts **Scaled RI** from a generalized logistic
(Richards's curve / sigmoid) function:

```
Scaled_RI = L_lo + (L_hi - L_lo) / (1 + exp(-k * (T - T0)))^(1/nu)
```

with three predictor cases, nested:

| Case | Predictors | Description |
|------|-----------|-------------|
| Case 3 (baseline) | T only | Temperature-only sigmoid |
| Case 4 | T + G23 | Adds GDGT-2/3 ecotype depth term |
| Case 5 (full) | T + G23 + NO3 | Adds nutrient stress term |

**Critical distinction — do not conflate:**
- `G23` tracks depth-habitat shifts between WCA and WCB ecotypes
- `NO3` captures nutrient stress effects on GDGT ring cycling
These are mechanistically orthogonal and statistically independent (ρ ≈ 0).

The inverse model (`InvT`) runs the same structure but predicts **temperature** from
Scaled RI + ancillary predictors.

**Top-layer posterior parameters (from current Stan run, coretop level):**

| Parameter | Median | SD |
|-----------|--------|----|
| T₀ | 35.9 | 3.3 |
| b (L_hi asymptote) | 0.42 | 0.09 |
| k (steepness) | 0.24 | 0.08 |
| ν (asymmetry) | 2.7 | 1.3 |

Verify these against actual Stan CSV output before using them in any report — known
numerical discrepancies exist between figure and appendix values pending reconciliation.

---

## File layout (expected repo structure)

```
texas/
├── stan/
│   ├── texas_fwd.stan          # Forward model (Scaled RI ~ T + G23 + NO3)
│   ├── texas_invT.stan         # Inverse model (T ~ Scaled RI + G23 + NO3)
│   └── texas_fwd_Tonly.stan    # Temperature-only baseline (Case 3)
├── data/
│   ├── coretop_draws.parquet   # Stan posterior draws (Parquet preferred over CSV)
│   └── coretop_data.parquet    # Coretop dataset (n=1513), includes T, G23, NO3, ScaledRI
├── figures/
└── [existing notebook].ipynb   # Contains the existing frequentist VP function — ask Ronnie
                                 # for the exact notebook name before proceeding
```

**Before starting:** ask Ronnie for the exact notebook filename that contains the existing
frequentist `run_variance_partitioning()` function. Do not assume the filename. Use
`jupyter nbconvert --to script` if you need to inspect the notebook cell contents from
the terminal without launching Jupyter.

Adapt all other paths to match actual layout. Check with `ls` before assuming filenames.

---

## Task 1 — Add `generated quantities` to the Stan forward model

In `texas_fwd.stan`, add a `generated quantities` block that computes per-draw Bayesian R²
for three counterfactual sub-models. The key is zeroing out beta coefficients to isolate
predictor contributions:

```stan
generated quantities {

  // ---- per-observation predictions under three sub-models ----
  vector[N] mu_full;    // T + G23 + NO3 (full model)
  vector[N] mu_TG23;   // T + G23 only
  vector[N] mu_Tonly;  // T only (Case 3 baseline)

  for (n in 1:N) {
    real eta_full  = sigmoid_fn(T[n], G23[n], NO3[n],  beta_G23, beta_NO3,  T0, k, nu, L_lo, L_hi);
    real eta_TG23  = sigmoid_fn(T[n], G23[n], 0.0,     beta_G23, 0.0,       T0, k, nu, L_lo, L_hi);
    real eta_Tonly = sigmoid_fn(T[n], 0.0,    0.0,     0.0,      0.0,       T0, k, nu, L_lo, L_hi);
    mu_full[n]  = eta_full;
    mu_TG23[n]  = eta_TG23;
    mu_Tonly[n] = eta_Tonly;
  }

  // ---- Bayesian R² per draw (Gelman et al. 2019) ----
  real var_mu_full  = variance(mu_full);
  real var_mu_TG23  = variance(mu_TG23);
  real var_mu_Tonly = variance(mu_Tonly);
  real sigma2       = sigma^2;

  real R2_full  = var_mu_full  / (var_mu_full  + sigma2);
  real R2_TG23  = var_mu_TG23  / (var_mu_TG23  + sigma2);
  real R2_Tonly = var_mu_Tonly / (var_mu_Tonly + sigma2);

  // ---- delta-R² contributions ----
  real deltaR2_G23  = R2_TG23 - R2_Tonly;   // unique contribution of G23
  real deltaR2_NO3  = R2_full - R2_TG23;    // unique contribution of NO3
  real deltaR2_both = R2_full - R2_Tonly;   // joint contribution
}
```

**Notes:**
- Adapt `sigmoid_fn` to match your actual Stan function signature
- `beta_G23` and `beta_NO3` must be declared in `parameters` or `transformed parameters`
- `sigma` is the observation-level residual SD

---

## Task 2 — Add `run_bayesian_variance_partitioning()` to the existing notebook

Locate the notebook cell containing `run_variance_partitioning()` and add a new cell
immediately after it with the Bayesian analog. Do **not** create a standalone `.py` file —
keep everything in the same notebook. The new function should:

1. Load posterior draws from Parquet (use `pd.read_parquet`)
2. Extract columns: `deltaR2_G23`, `deltaR2_NO3`, `deltaR2_both`, `R2_full`, `R2_Tonly`
3. Compute posterior median + 90% credible interval for each quantity
4. Reuse the sig-fig helpers (`_fmt_r2`, `_n_decimals`) already defined in the notebook —
   do not duplicate them
5. Return a `dict` structured to match the existing frequentist output for easy side-by-side
   comparison in tables

Skeleton:

```python
def run_bayesian_variance_partitioning(draws_path: str) -> dict:
    """
    Bayesian analog to run_variance_partitioning().

    Loads Stan posterior draws and computes posterior distributions of
    delta-R² contributions from G23 and NO3 relative to the T-only baseline.

    Parameters
    ----------
    draws_path : str
        Path to Parquet file of Stan posterior draws. Must contain columns:
        deltaR2_G23, deltaR2_NO3, deltaR2_both, R2_full, R2_Tonly.

    Returns
    -------
    dict with keys:
        R2_full, R2_Tonly, deltaR2_G23, deltaR2_NO3, deltaR2_both
        Each value is a dict: {median, lo90, hi90, formatted}
    """
    import pandas as pd
    import numpy as np

    draws = pd.read_parquet(draws_path)
    results = {}

    for col in ["R2_full", "R2_Tonly", "deltaR2_G23", "deltaR2_NO3", "deltaR2_both"]:
        vals = draws[col].values
        med  = np.median(vals)
        lo   = np.percentile(vals, 5)
        hi   = np.percentile(vals, 95)
        results[col] = {
            "median": med,
            "lo90":   lo,
            "hi90":   hi,
            "formatted": _fmt_r2(med),   # reuse existing helper
        }

    return results
```

---

## Task 3 — InvT: posterior predictive SD reduction

For the inverse model, the relevant quantity is **not R²** but the reduction in posterior
predictive uncertainty on temperature when G23 and NO3 are included. Compute per coretop site:

```python
def compute_invT_uncertainty_reduction(draws_path: str, data_path: str) -> pd.DataFrame:
    """
    For each coretop site, compare posterior predictive SD on T under:
      (a) T-only model inputs
      (b) Full model inputs (T + G23 + NO3)

    The reduction  sigma_Tonly - sigma_full  quantifies the contribution of
    G23 and NO3 to narrowing paleotemperature credible intervals.
    """
    ...
```

Return a DataFrame with columns:
`site_id`, `sigma_Tonly`, `sigma_full`, `sigma_reduction`, `pct_reduction`

Visualize as a violin plot (proplot) split by ocean basin, overlaid with per-site scatter.

---

## Task 4 — LOO-IC model comparison (optional but recommended for supplement)

Using `arviz`:

```python
import arviz as az

idata_full  = az.from_cmdstanpy(fit_full,  log_likelihood="log_lik")
idata_TG23  = az.from_cmdstanpy(fit_TG23,  log_likelihood="log_lik")
idata_Tonly = az.from_cmdstanpy(fit_Tonly, log_likelihood="log_lik")

comparison = az.compare(
    {"full": idata_full, "T+G23": idata_TG23, "T_only": idata_Tonly},
    ic="loo", scale="deviance"
)
print(comparison)
```

Report ΔLOO-IC with SE. This goes in the supplementary, not main text.

---

## Output targets

| Deliverable | Location | Notes |
|-------------|----------|-------|
| Updated `texas_fwd.stan` | `stan/texas_fwd.stan` | `generated quantities` block added |
| New cells in existing VP notebook | existing notebook | Bayesian functions added after frequentist VP cell |
| Updated existing notebook | repo root | All VP work (frequentist + Bayesian) in one place |
| Posterior ΔR² summary table | printed / CSV | Median + 90% CI, matching frequentist table format |
| InvT σ-reduction violin plot | `figures/` | proplot, C_TEAL/#1D9E75 + C_CORAL/#D85A30 palette |

---

## Coding conventions

- **Stan:** CmdStanPy; verify chains with `fit.diagnose()` before extracting draws
- **Python:** pandas, numpy, scipy; proplot 0.9.7 for figures
- **Color palette:** C_TEAL = `#1D9E75`, C_CORAL = `#D85A30`, C_PUR = `#7F77DD`
- **Parquet over CSV** for all Stan draw files (dtype preservation)
- **Figures:** save with `bbox_inches='tight'` + `fig.subplots_adjust(bottom=0.25)`
- **NetCDF writes:** use context managers to avoid xarray `CachingFileManager` file-lock conflicts
- **Sig-fig helpers:** reuse `_fmt_r2`, `_fmt_rmse`, `_fmt_coef` already defined in the existing notebook — do not reimplement or move to a separate file
- **No wholesale rewrites:** prefer targeted `str_replace`-style patches to existing files

### Filesystem caution
If the repo is on a **network-mounted filesystem**, run `kinit` before any Stan sampling
to avoid Kerberos ticket expiry (exit code 127, "Key has expired"). Alternatively, copy
the repo to local disk before running chains.

---

## Bayesian vs. frequentist reporting — manuscript rule

Per manuscript convention:
- **Posterior medians + credible intervals** → main text and figures
- **F-statistics, frequentist ΔR², LOO-IC** → supplementary or clearly labeled tables

Do not mix frequentist and Bayesian R² values in the same sentence without explicit labeling.

---

## Key references

- Gelman, A., Goodrich, B., Gabry, J., & Vehtari, A. (2019). R-squared for Bayesian
  regression models. *The American Statistician*, 73(3), 307–309.
  → Defines Bayesian R² used here
- Rattanasriampaipong et al. (2022) — BAYSPAR benchmark
- Tierney & Tingley (2014, 2018) — BAYSPAR / BAYSPLINE framework
- Vehtari, A., Gelman, A., & Gabry, J. (2017). Practical Bayesian model evaluation using
  leave-one-out cross-validation and WAIC. *Statistics and Computing*, 27(5), 1413–1432.
  → LOO-IC methodology

---

*Generated to guide Claude Code implementation of Bayesian variance partitioning for the
TEXAS manuscript. Verify all parameter values and file paths against actual model runs
before use in manuscript text.*
