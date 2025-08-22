# Stan Log-Probability Functions Explained

This document explains the key Stan functions used in the inverse temperature models, focusing on the `lp` (log-probability) calculations in both univariate and multivariate cases.

## Univariate Case: `invT_gen_logi_fixed_univ_marginal.stan`

### Key Variables and Logic

In the univariate model, the main log-probability calculation happens in the `model` block:

```stan
for (n in 1:N) {
  vector[M] lp;
  for (m in 1:M) {
    real mu = b[m] + (1 - b[m]) / pow(1 + Q[m] * exp(-k[m] * (t_est[n] - t0[m])), 1.0 / v[m]);
    lp[m] = normal_lpdf(scaledRI[n] | mu, sigma_scaledRI[m]);
  }
  target += log_sum_exp(lp) - log(M);
}
```

**What's happening:**

1. **`lp` vector**: For each observation `n`, creates a vector of length `M` (number of forward model ensemble members)

2. **Inner loop over `m`**: For each ensemble member:
   - **`mu`**: Calculates the expected scaledRI using the generalized logistic function:
     - `b[m]`: baseline/intercept for ensemble member m
     - The complex term: `(1 - b[m]) / pow(1 + Q[m] * exp(-k[m] * (t_est[n] - t0[m])), 1.0 / v[m])`
     - This represents the temperature-dependent component of the calibration
   - **`lp[m]`**: Calculates log-probability density of observing `scaledRI[n]` given the predicted `mu` and uncertainty `sigma_scaledRI[m]`

3. **`log_sum_exp(lp) - log(M)`**: 
   - **Ensemble averaging**: Since we have M different calibration curves (ensemble members), we need to average over them
   - `log_sum_exp(lp)` = log(exp(lp[1]) + exp(lp[2]) + ... + exp(lp[M]))
   - `- log(M)` converts the sum to an average: log(sum/M) = log(sum) - log(M)
   - This gives the log-probability averaged across all ensemble members

## Multivariate Case: `invT_gen_logi_fixed_multiv_marginal.stan`

### Key Differences

The multivariate model uses `reduce_sum` for parallelization and includes additional predictors. The core logic is in the `ll_chunk` function:

```stan
for (i in 1:n_chunk) {
  int n = start + i - 1;  // original index
  vector[M] llk;
  for (m in 1:M) {
    real lin = b[m];
    if (use_gd == 1)  lin += beta_gd[m] * gd_seg[i];
    if (use_no3 == 1) {
      real logno3 = 0.0;
      if (n3_seg[i] > 0.0 && n3_seg[i] < no3_cutoff) {
        logno3 = log10(n3_seg[i] + 1e-9);
      }
      lin += beta_no3[m] * logno3;
    }
    real mu = lin + (1 - b[m]) / pow(1 + Q[m] * exp(-k[m] * (t_seg[i] - t0[m])), 1.0 / v[m]);
    llk[m] = normal_lpdf(y_seg[i] | mu, sigma[m]);
  }
  lp += log_sum_exp(llk) - log(M);
}
```

**Key differences from univariate:**

1. **Additional predictors**: The `lin` term now includes:
   - **`b[m]`**: Still the baseline
   - **GDGT-2/3 ratio**: `beta_gd[m] * gd_seg[i]` (if `use_gd == 1`)
   - **Nitrate effect**: `beta_no3[m] * logno3` (if `use_no3 == 1`)

2. **Nitrate preprocessing**:
   ```stan
   real logno3 = 0.0;
   if (n3_seg[i] > 0.0 && n3_seg[i] < no3_cutoff) {
     logno3 = log10(n3_seg[i] + 1e-9);
   }
   ```
   - Only applies nitrate effect when nitrate is positive and below cutoff
   - Uses log10 transformation (common for nutrient effects)
   - Adds small constant (1e-9) to avoid log(0)

3. **Enhanced calibration equation**:
   ```stan
   real mu = lin + (1 - b[m]) / pow(1 + Q[m] * exp(-k[m] * (t_seg[i] - t0[m])), 1.0 / v[m]);
   ```
   - `lin` now contains the linear effects of additional predictors
   - The temperature-dependent term remains the same generalized logistic function

4. **Parallelization with `reduce_sum`**:
   - Splits the N observations into chunks for parallel processing
   - Each chunk processes a subset of observations
   - The `ll_chunk` function calculates log-probability for its assigned chunk
   - Stan automatically combines results from all chunks

## Summary of `lp` Logic

**Both models follow the same fundamental approach:**

1. **For each observation**: Calculate likelihood under each ensemble member's calibration
2. **Ensemble averaging**: Use `log_sum_exp(lp) - log(M)` to average likelihoods across ensemble members
3. **Accumulate**: Add to `target` (univariate) or `lp` (multivariate) for Stan's MCMC sampling

**The multivariate model extends this by:**
- Adding linear effects of environmental predictors (GDGT ratios, nitrate)
- Using parallel processing for computational efficiency
- Handling missing/extreme values in predictors (nitrate cutoff)

The `log_sum_exp` trick is crucial in both cases—it allows numerically stable averaging of probabilities in log space, which is essential when dealing with very small probability values that could cause underflow in linear space.