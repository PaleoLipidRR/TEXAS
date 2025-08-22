# Stan Modeling Notes

## 1. Order Difference Between Standard and Marginal Stan Models

In your **regular Stan model**, the order of operations inside the `model` block is:

1. **Prior on `t_est`**  
   Each column of `t_est` is constrained by the normal prior.

2. **Base logistic (or generalized logistic) model**  
   The fundamental forward model for scaled RI, usually of the form:  

   ```stan
   mu_scaledRI = (1.0 - b[m]) * inv_logit(k[m] * (t_est[, m] - t0[m])) + b[m];
   ```

   or in the generalized case with Q and v:  

   ```stan
   mu = b[m] + (1 - b[m]) / pow(1 + Q[m] * exp(-k[m] * (t_est[n] - t0[m])), 1.0 / v[m]);
   ```

3. **Optional predictors (corrections)**  
   - **GDGT-2/3 ratio** correction (linear term).  
   - **Nitrate** correction, with cutoff check (`0 < no3 < no3_cutoff`).  

   These are **added to the base logistic** prediction.

4. **Likelihood**  
   ```stan
   scaledRI ~ normal(mu_scaledRI, sigma_scaledRI[m]);
   ```

---

In your **marginal models** with `reduce_sum`, the structure looks a little different because of how **log-likelihood contributions are parallelized**:

1. `reduce_sum` delegates computation to a helper function (e.g., `ll_chunk`).  
2. Inside `ll_chunk`:  
   - Apply prior contribution for the `t_est` elements in that chunk.  
   - For each observation `n`, loop over ensemble members `m`.  
   - Compute base logistic, then add optional predictor corrections.  
   - Compute the likelihood contribution.  
   - Average across ensemble members using `log_sum_exp`.  
3. Return the summed contribution to the target log-probability.

So the **difference in order** is not mathematical—it’s **structural** due to parallelization.  
The linear corrections (GDGT23, NO₃) are grouped with the logistic calculation inside the `ll_chunk`, rather than after, because the marginalization step (`log_sum_exp`) needs the fully constructed likelihood for each ensemble member.

---

## 2. Understanding `reduce_sum` in Stan

### What it does
`reduce_sum` is Stan’s **map-reduce framework** for parallelizing likelihood calculations.  
It splits your data into **chunks**, evaluates the log-likelihood for each chunk (possibly in parallel across CPU cores), and then sums the results.

### Structure

```stan
target += reduce_sum(
    ll_function,              // the user-defined log-likelihood chunk function
    data_variable,            // array or vector to determine chunking
    grainsize,                // minimum chunk size
    shared_param1, ...        // shared parameters/data (passed to every chunk)
);
```

### Components

1. **`ll_function`**  
   A user-defined function that computes the **log-likelihood contribution for a subset of the data**.  
   Example signature:

   ```stan
   functions {
     real ll_chunk(int start, int end,
                   vector data_subset,
                   vector params, ...);
   }
   ```

   - `start` and `end` are automatically provided by `reduce_sum`.  
   - They indicate the indices of the chunk being processed.

2. **`data_variable`**  
   Used by Stan to determine how many chunks to make. For time series or regression, this is often the outcome variable.

3. **`grainsize`**  
   Controls how many data points go into each chunk.  
   - Larger `grainsize` = fewer chunks, less overhead, less parallelism.  
   - Smaller `grainsize` = more chunks, more overhead, more parallelism.

4. **Shared parameters**  
   Any other variables (parameters or data) needed to compute the likelihood are passed as additional arguments.

---

### Example Analogy for Non-Stan Folks

Imagine you have **1000 data points** and want to compute the likelihood. Normally you’d loop through all 1000 points sequentially.

With `reduce_sum`:
- Split data into **chunks** (e.g., 10 chunks of 100 points).  
- Each chunk is processed **independently** (and possibly in parallel).  
- Results from chunks are combined (reduced) into one sum.  

This makes Bayesian inference faster by distributing the work.

---

## Key Takeaways

- The **different order** in the marginal models (`reduce_sum`) isn’t a change in math, it’s a change in code structure needed for parallelization.  
- Optional predictor corrections (GDGT23, NO₃) are applied **inside** the chunk likelihood before marginalization.  
- `reduce_sum` is a **parallel map-reduce** system: split data, compute per-chunk likelihoods, then sum them up.

