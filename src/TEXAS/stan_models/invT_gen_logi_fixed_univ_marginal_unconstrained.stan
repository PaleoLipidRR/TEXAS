// ===============================================================================
// invT_gen_logi_fixed_univ_marginal_unconstrained.stan
//
// PURPOSE: Bayesian paleotemperature reconstruction from observed Ring Index
//          values (univariate - thermal signal only). Given proxyObs
//          observations and a forward calibration posterior, infers the
//          posterior distribution of temperature for each sample.
//
// APPROACH - "Marginal" (direct sampling):
//   The forward calibration introduces uncertainty in the RI-T curve parameters
//   theta = {T0, k, b, nu, sigma}. We marginalize (integrate) over this uncertainty:
//
//     p(RI_obs | T) = integral p(RI_obs | T, theta) * p(theta | calib. data) dtheta
//                   ~= (1/M) Sum_{m=1}^{M}  Normal(RI_obs | f(T; theta_m), sigma_m)
//
//   where theta_m is the m-th draw from the forward calibration posterior.
//   This is a Monte Carlo approximation of the integral using M pre-sampled
//   calibration curves. The only free parameter in this Stan model is T.
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
// CRITICAL: ALL PARAMETERS MUST USE THE SAME DRAW INDEX m
//   {T0_m, k_m, b_m, nu_m, sigma_m} are all indexed by m in the inner loop.
//   Mixing indices across parameters would break their posterior correlations
//   and artificially inflate calibration uncertainty.
//   This constraint is enforced in build_invT_inputData() (Python side).
//
// TEMPERATURE CONSTRAINT: "unconstrained"
//   t_est has no lower bound, so reconstructions may fall below the seawater
//   freezing point where the data drive them there. Sibling files in this
//   directory impose a lower bound instead ("_hard_constraint") or place a
//   truncated-Normal prior on t_est ("_truncated_prior").
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
                vector t0, vector k, vector b, vector v,
                vector sigma) {

    int M = rows(t0);
    real lp = 0;
    int n_chunk = end - start + 1;

    // Extract the subset of vectors relevant to this chunk.
    // segment(v, start, length) returns v[start : start+length-1].
    vector[n_chunk] t_seg  = segment(t_est,      start, n_chunk);
    vector[n_chunk] mu_seg = segment(prior_mu_t, start, n_chunk);
    vector[n_chunk] y_seg  = segment(proxyObs,   start, n_chunk);

    // Prior contribution for this chunk: T_n ~ Normal(prior_mu_t_n, prior_sigma_t)
    lp += normal_lpdf(t_seg | mu_seg, prior_sigma_t);

    // Likelihood contribution: marginalize over M calibration draws for each n.
    for (i in 1:n_chunk) {
      vector[M] llk;  // Log-likelihood under each of the M calibration draws

      for (m in 1:M) {
        // Compute expected RI using the m-th calibration curve (Eq. 1).
        // ALL parameters use the same draw index [m] to preserve correlations.
        real mu = b[m] + (1 - b[m])
            / pow(1 + exp(-k[m] * (t_seg[i] - t0[m])), 1.0 / v[m]);

        // Log-likelihood: how well does this calibration curve explain RI_n?
        llk[m] = normal_lpdf(y_seg[i] | mu, sigma[m]);
      }

      // Monte Carlo marginalization: log[(1/M) Sum_m exp(llk_m)] = log_sum_exp - log(M)
      lp += log_sum_exp(llk) - log(M);
    }
    return lp;
  }
}

data {
    // --- Proxy observations to reconstruct ------------------------------------
    int<lower=1> N;            // Number of sediment samples (downcore or coretop)
    vector[N] proxyObs;        // Observed scaled Ring Index for each sample (in [0,1])

    // --- Prior on paleotemperature ---------------------------------------------
    // A normal prior T ~ Normal(prior_mu_t, prior_sigma_t) encodes any independent
    // knowledge about the expected temperature range (e.g., from site location,
    // foram assemblages, or Mg/Ca). Use prior_sigma_t = 10degC for a diffuse prior.
    vector[N] prior_mu_t;      // Prior mean temperature for each sample (degC)
    real prior_sigma_t;        // Prior SD (shared across all samples) (degC)

    // --- Forward calibration posterior - M draws of all curve parameters -------
    // Loaded from the forward calibration .nc file by build_invT_inputData().
    // Increasing M improves the integral approximation at the cost of O(N*M)
    // likelihood evaluations per HMC step. Typical range: M = 100-500.
    //
    // IMPORTANT: each vector below has length M. Row m contains ONE complete,
    // self-consistent parameter set from the forward posterior. Using all
    // parameters at index [m] preserves their joint correlations.
    int<lower=1> M;
    vector[M] t0;              // T0_m: reference temperature of each calibration draw (degC)
    vector[M] k;               // k_m: steepness
    vector[M] b;               // b_m: lower asymptote
    vector[M] v;               // nu_m: shape
    vector[M] sigma_proxyObs;  // sigma_m: residual calibration noise

    // --- Parallelism control ---------------------------------------------------
    // grainsize: approximate number of samples per parallel chunk.
    // Set to 1 for maximum parallelism; set to N to disable (single thread).
    int<lower=1> grainsize;
}

parameters {
    // --- Paleotemperature estimates -------------------------------------------
    // One temperature per sample - the ONLY parameter block in this model.
    // "Unconstrained" means no lower bound; Stan samples over all of R.
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
        t0, k, b, v, sigma_proxyObs
    );
}
