// ===============================================================================
// invT_gen_logi_fixed_multiv_marginal_unconstrained.stan
//
// PURPOSE: Bayesian paleotemperature reconstruction with non-thermal corrections
//          (GDGT-2/3 ratio and/or NO3), parallelized via Stan's reduce_sum.
//          Multivariate counterpart of invT_gen_logi_fixed_univ_marginal_unconstrained.stan.
//
// APPROACH - same marginal (log-sum-exp) strategy as the univariate model:
//   For each sample n, average the Normal likelihood over M calibration draws:
//     p(RI_n | T_n) ~= (1/M) Sum_m Normal(RI_n | f(T_n; theta_m) + corrections_m, sigma_m)
//
// PARALLELIZATION via reduce_sum:
//   The outer loop over N samples is the bottleneck. reduce_sum splits those N
//   observations into chunks processed on separate CPU threads (within-chain
//   parallelism). The grainsize data variable controls chunk size:
//     grainsize = 1  -> maximum parallelism (best with many cores)
//     grainsize = N  -> no parallelism (single-threaded, same as plain loop)
//   Requires compilation with STAN_THREADS=True and threads_per_chain > 1.
//
// KEY DESIGN: prior is INSIDE ll_chunk, not in the model block.
//   reduce_sum distributes work by splitting the N-element index array.
//   Because the prior p(T_n | prior_mu_t_n) depends on n, it must also be
//   computed inside ll_chunk so each chunk handles its own subset of samples.
//   The total log-probability is the sum across all chunks - mathematically
//   identical to computing prior + likelihood in a single non-parallel loop.
//
// TEMPERATURE CONSTRAINT: "unconstrained" variant - no lower bound on t_est.
// ===============================================================================

functions {
  // --- ll_chunk: log-probability for a chunk of N observations --------------
  // Called by reduce_sum for each parallel chunk of indices [start, end].
  //
  // Arguments:
  //   slice_indices - subarray of {1, 2, ..., N} for this chunk (used by
  //                   reduce_sum to determine which observations to process;
  //                   the function uses start/end to slice shared vectors)
  //   start, end    - first and last observation indices in this chunk
  //   (remaining)   - shared data passed through from the model block
  //
  // Returns: sum of (prior + likelihood) log-probabilities for this chunk.

  real ll_chunk(array[] int slice_indices,
                int start, int end,
                vector proxyObs,
                vector t_est, vector prior_mu_t, real prior_sigma_t,
                int use_gd, int use_no3,
                vector gd, vector no3, real no3_cutoff,
                vector t0, vector k, vector b, vector v,
                vector beta_gd, vector beta_no3, vector sigma) {

    int M = rows(t0);
    real lp = 0;
    int n_chunk = end - start + 1;

    // Extract the subset of vectors relevant to this chunk.
    // segment(v, start, length) returns v[start : start+length-1].
    vector[n_chunk] t_seg    = segment(t_est,      start, n_chunk);
    vector[n_chunk] mu_seg   = segment(prior_mu_t, start, n_chunk);
    vector[n_chunk] gd_seg   = segment(gd,         start, n_chunk);
    vector[n_chunk] n3_seg   = segment(no3,        start, n_chunk);
    vector[n_chunk] y_seg    = segment(proxyObs,   start, n_chunk);

    // Prior contribution for this chunk: T_n ~ Normal(prior_mu_t_n, prior_sigma_t)
    lp += normal_lpdf(t_seg | mu_seg, prior_sigma_t);

    // Likelihood contribution: marginalize over M calibration draws for each n.
    for (i in 1:n_chunk) {
      vector[M] llk;  // Log-likelihood under each of the M calibration draws

      for (m in 1:M) {
        // Base thermal term (Eq. 1): Richards curve evaluated at T = t_seg[i].
        // Start with lower asymptote b[m], then add the sigmoid term.
        real lin = b[m];  // Will accumulate: b + corrections + sigmoid

        // Ecology correction beta_{G2/3} * gdgt23ratio (Eq. 6)
        if (use_gd == 1)
          lin += beta_gd[m] * gd_seg[i];

        // NO3 correction beta_{NO3} * log10(NO3) (Eq. 7) - applied conditionally.
        // logno3 = 0 when NO3 is outside the valid range, so no correction applied.
        if (use_no3 == 1) {
          real logno3 = 0.0;
          if (n3_seg[i] > 0.0 && n3_seg[i] < no3_cutoff)
            logno3 = log10(n3_seg[i] + 1e-9);  // small offset avoids log(0)
          lin += beta_no3[m] * logno3;
        }

        // Complete the Richards curve:
        //   mu = b[m] + corrections + (1 - b[m]) / (1 + exp(-k*(T - T0)))^(1/nu)
        // Note: 'lin' already holds b[m] + corrections from above.
        real mu = lin + (1 - b[m])
            / pow(1 + exp(-k[m] * (t_seg[i] - t0[m])), 1.0 / v[m]);

        // Log-likelihood of the observed RI under this calibration draw.
        llk[m] = normal_lpdf(y_seg[i] | mu, sigma[m]);
      }

      // Monte Carlo marginalization: log[(1/M) Sum_m exp(llk_m)] = log_sum_exp - log(M)
      lp += log_sum_exp(llk) - log(M);
    }
    return lp;
  }
}

data {
    // --- Proxy observations ---------------------------------------------------
    int<lower=1> N;                    // Number of sediment samples
    vector[N] proxyObs;                // Observed scaled Ring Index (in [0,1])

    // --- Prior on paleotemperature ---------------------------------------------
    vector[N] prior_mu_t;              // Prior mean temperature per sample (degC)
    real<lower=0> prior_sigma_t;       // Prior SD, shared across samples (degC)

    // --- Optional non-thermal predictors --------------------------------------
    int<lower=0, upper=1> use_gdgt23ratio;
    int<lower=0, upper=1> use_no3;
    vector[N] gdgt23ratio;
    vector[N] no3;
    real<lower=0> no3_cutoff;

    // --- Forward calibration posterior - M draws (all same-index) -------------
    // Each vector has length M. Row m is one complete self-consistent draw
    // from the forward posterior: {T0_m, k_m, b_m, nu_m, beta_m, sigma_m}.
    // All indexed by [m] in the inner loop to preserve parameter correlations.
    int<lower=1> M;
    vector[M] t0;
    vector[M] k;
    vector[M] b;
    vector[M] v;
    vector[M] beta_G23;        // beta_{G2/3} per draw (zeros if unused)
    vector[M] beta_NO3;        // beta_{NO3} per draw (zeros if unused)
    vector[M] sigma_proxyObs;  // Residual calibration noise per draw

    // --- Parallelism control ---------------------------------------------------
    // grainsize: approximate number of samples per parallel chunk.
    // Set to 1 for maximum parallelism; set to N to disable (single thread).
    int<lower=1> grainsize;
}

parameters {
    // One temperature per sample - the ONLY parameter in this model.
    // "Unconstrained" means no physical lower bound imposed on t_est.
    vector[N] t_est;
}

model {
    // Create an index array {1, 2, ..., N} that reduce_sum uses to partition
    // the N observations into chunks for parallel processing.
    array[N] int indices = linspaced_int_array(N, 1, N);

    // Dispatch parallel computation across chunks.
    // reduce_sum calls ll_chunk once per chunk and sums the results.
    // The prior and likelihood are both computed inside ll_chunk.
    target += reduce_sum(
        ll_chunk, indices, grainsize,
        proxyObs, t_est, prior_mu_t, prior_sigma_t,
        use_gdgt23ratio, use_no3, gdgt23ratio, no3, no3_cutoff,
        t0, k, b, v,
        beta_G23, beta_NO3, sigma_proxyObs
    );
}
