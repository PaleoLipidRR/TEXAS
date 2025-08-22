# Why Marginalization Improves Inverse TEXAS Sampling

This note explains why the new **marginal parameterization** of the inverse TEXAS models runs *much faster* and produces *cleaner posteriors* compared to the original "full latent" formulation. The goal is to make this clear for a scientific audience, without assuming a background in Bayesian computation.

---

## 1. The Two Approaches

### (A) Original "Full Latent" Approach
- For each data point `n` (e.g., a core-top sample), and each forward-model draw `m` (the ensemble), we introduced an **explicit latent parameter**:

  ```
  t_est[n, m]
  ```

- That means:
  - Number of unknowns grows with both the **number of samples (N)** and **the ensemble size (M)**.
  - For N ≈ 1,200 and M ≈ 100, that’s ~120,000 latent parameters.

- The model then combines all of these latents into the likelihood.

---

### (B) Marginalized Approach
- Instead of sampling `t_est[n, m]` for every ensemble draw, we only keep a **single latent parameter per sample**:

  ```
  t_est[n]
  ```

- We then compute the likelihood by **marginalizing over the ensemble**:

  ```
  log p(data[n] | t_est[n]) = log( 1/M * Σ p(data[n] | t_est[n], params_m) )
  ```

- This uses the `log_sum_exp` trick in Stan, which is stable and efficient.

- Result:
  - Only N ≈ 1,200 latent parameters (independent of M).
  - The ensemble variability is still accounted for, but without exploding the parameter space.

---

## 2. Side-by-Side Stan Sketch

Here’s the essential difference, shown in simplified pseudo-Stan code:

### Full Latent Version
```stan
parameters {
  matrix[N, M] t_est;   // each sample × ensemble
}

model {
  for (m in 1:M) {
    vector[N] mu_scaledRI = logistic_fn(t_est[, m], params[m]);
    scaledRI ~ normal(mu_scaledRI, sigma[m]);
  }
}
```

### Marginalized Version
```stan
parameters {
  vector[N] t_est;      // only one per sample
}

model {
  for (n in 1:N) {
    vector[M] log_lik_m;
    for (m in 1:M) {
      real mu_scaledRI = logistic_fn(t_est[n], params[m]);
      log_lik_m[m] = normal_lpdf(scaledRI[n] | mu_scaledRI, sigma[m]);
    }
    // Marginalize using log-sum-exp
    target += log_sum_exp(log_lik_m) - log(M);
  }
}
```

**Key change:**  
Instead of sampling `t_est[n, m]` for all ensemble members, we sample only `t_est[n]` and analytically average over ensemble members.

---

## 3. Why Marginalization is Better

### 3.1 Fewer Parameters
- Full latent model: ~120,000 parameters.
- Marginal model: ~1,200 parameters.
- **Sampling speed scales badly with dimensionality.** By removing 100× more unknowns, the sampler spends far less time per iteration.

### 3.2 Better Posterior Geometry
- In the full latent model, `t_est[n, m]` are strongly correlated across `m`.  
- The sampler has to "wiggle" through a very tangled space.
- Marginalization **collapses these correlations analytically**, so the sampler only needs to explore the temperature dimension.

### 3.3 Cleaner Effective Sample Size (ESS)
- ESS measures how many "independent" samples you get out of MCMC.  
- With fewer parameters and smoother geometry, marginal models give **higher ESS per unit time**.
- This means your credible intervals stabilize faster.

---

## 4. Practical Impact

- **Speed**:  
  With marginalization, warmup and sampling progress much faster. For example, reaching iteration 1/700 may take ~2 minutes, compared to much slower in the full latent case.

- **Stability**:  
  Fewer divergences, better adaptation of step sizes, and cleaner R̂ diagnostics.

- **Scalability**:  
  You can now afford larger ensembles (M=100, 200, …) without blowing up the parameter space.

---

## 5. Analogy (for non-statisticians)

Think of this like averaging weather forecasts:

- **Full latent model**: You ask 100 forecasters for 1,200 cities, and try to track **every single opinion separately**. That’s 120,000 numbers bouncing around.
- **Marginalized model**: You only track the **city-level temperature** (1,200 numbers), and average the forecasts mathematically in the likelihood. You still capture uncertainty from forecasters, but you don’t waste time simulating each one.

---

## 6. Key Takeaway

Marginalization trades a slightly more complex likelihood calculation for a **massive reduction in sampling complexity**.  

- The science is the same (we still respect ensemble variability).  
- But computationally, the marginalized model is leaner, faster, and more robust.

This is why the new inverse TEXAS marginal models are now the recommended default.
