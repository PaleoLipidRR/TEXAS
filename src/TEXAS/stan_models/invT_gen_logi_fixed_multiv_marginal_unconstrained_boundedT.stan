// ═══════════════════════════════════════════════════════════════════════════════
// invT_gen_logi_fixed_multiv_marginal_unconstrained_boundedT.stan
//
// PURPOSE: Bayesian paleotemperature reconstruction from observed Scaled Ring
//          Index values, with non-thermal predictors (G2/3 ratio, NO3) entering
//          as a shift of the calibration curve's location parameter.
//          This is the inverse of the forward calibration
//          gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT.stan, and it
//          must be paired with a posterior from that model.
//
// ─── THE MEAN FUNCTION ────────────────────────────────────────────────────────
//   T0_eff = T0 + gamma_G23*g23 + gamma_NO3*log10(no3)
//   mu     = b + (1-b) / (1 + exp(-k*(T - T0_eff)))^(1/v)
//
//   Because the predictors shift T0 rather than mu, mu stays inside (b, 1) for
//   every finite gamma. The inverse therefore exists everywhere except for
//   samples whose observed proxy genuinely falls outside the curve's range.
//
//   T0 is the curve's LOCATION parameter, not its inflection point; the steepest
//   response sits at T0 - ln(v)/k.
//
// ─── APPROACH: marginal (direct sampling) ─────────────────────────────────────
//   The forward calibration leaves uncertainty in the curve parameters
//   theta = {T0, k, b, v, gamma_G23, gamma_NO3, sigma}. This model marginalizes
//   over it rather than re-estimating it: for each sample n the Normal
//   likelihood is averaged over M draws from the forward posterior,
//
//     p(RI_n | T_n) ~= (1/M) Sum_m Normal(RI_n | mu(T_n; theta_m), sigma_m)
//
//   evaluated as a log-sum-exp. The only free parameters here are the N
//   temperatures t_est.
//
// CRITICAL: ALL PARAMETERS MUST USE THE SAME DRAW INDEX m. Mixing indices across
//   parameters would break their posterior correlations and inflate calibration
//   uncertainty. build_invT_inputData() enforces this on the Python side.
//
// ─── DATA BLOCK ───────────────────────────────────────────────────────────────
//   gamma_G23 and gamma_NO3 are each length M, one value per forward-posterior
//   draw, in degC per unit predictor (degC per log10 unit for NO3). Pass zeros
//   for a predictor that is switched off. The NO3 term applies only where the
//   observed value falls inside (0, no3_cutoff).
//
// ─── PARALLELIZATION via reduce_sum ───────────────────────────────────────────
//   The outer loop over N samples is the bottleneck; reduce_sum splits it into
//   chunks processed on separate CPU threads. grainsize = 1 gives maximum
//   parallelism, grainsize = N gives none. Requires STAN_THREADS=True and
//   threads_per_chain > 1.
//
//   The per-sample Normal prior on T is computed INSIDE ll_chunk, not in the
//   model block: because p(T_n | prior_mu_t_n) depends on n, each chunk must
//   contribute the prior for its own subset. Summing across chunks is
//   mathematically identical to a single non-parallel loop.
//
// ─── TEMPERATURE CONSTRAINT: "unconstrained" ──────────────────────────────────
//   t_est has no lower bound, so reconstructions may fall below the seawater
//   freezing point where the data drive them there.
// ═══════════════════════════════════════════════════════════════════════════════

functions {
  // ─── ll_chunk: log-probability for a chunk of N observations ──────────────
  // Called by reduce_sum for each parallel chunk of indices [start, end].
  //
  // Arguments:
  //   slice_indices — subarray of {1, 2, …, N} for this chunk (used by
  //                   reduce_sum to determine which observations to process;
  //                   the function uses start/end to slice shared vectors)
  //   start, end    — first and last observation indices in this chunk
  //   (remaining)   — shared data passed through from the model block
  //
  // Returns: sum of (prior + likelihood) log-probabilities for this chunk.

  real ll_chunk(array[] int slice_indices,
                int start, int end,
                vector proxyObs,
                vector t_est, vector prior_mu_t, real prior_sigma_t,
                int use_gd, int use_no3,
                vector gd, vector no3, real no3_cutoff,
                vector t0, vector k, vector b, vector v,
                vector gamma_gd, vector gamma_no3, vector sigma) {

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
        // The predictors shift the curve's location, not the response. Read it
        // as: "this community structure / nutrient level makes the curve turn
        // over at a different temperature", rather than "it offsets the index".
        real t0_eff = t0[m];

        // Ecology correction: gamma_{G2/3} degC per unit gdgt23ratio.
        if (use_gd == 1)
          t0_eff += gamma_gd[m] * gd_seg[i];

        // NO3 correction: gamma_{NO3} degC per log10 unit, applied conditionally.
        // logno3 = 0 when NO3 is outside the valid range, so no correction is
        // applied — the same gate the forward calibration was fitted under.
        if (use_no3 == 1) {
          real logno3 = 0.0;
          if (n3_seg[i] > 0.0 && n3_seg[i] < no3_cutoff)
            logno3 = log10(n3_seg[i] + 1e-9);  // small offset avoids log(0)
          t0_eff += gamma_no3[m] * logno3;
        }

        // The Richards curve, evaluated against the shifted location t0_eff.
        // Bounded in (b[m], 1) by construction for any finite t0_eff.
        real mu = b[m] + (1 - b[m])
            / pow(1 + exp(-k[m] * (t_seg[i] - t0_eff)), 1.0 / v[m]);

        // Log-likelihood of the observed RI under this calibration draw.
        llk[m] = normal_lpdf(y_seg[i] | mu, sigma[m]);
      }

      // Monte Carlo marginalization: log[(1/M) Σ_m exp(llk_m)] = log_sum_exp - log(M)
      lp += log_sum_exp(llk) - log(M);
    }
    return lp;
  }
}

data {
    // ─── Proxy observations ───────────────────────────────────────────────────
    int<lower=1> N;                    // Number of sediment samples
    vector[N] proxyObs;                // Observed scaled Ring Index (∈ [0,1])

    // ─── Prior on paleotemperature ─────────────────────────────────────────────
    vector[N] prior_mu_t;              // Prior mean temperature per sample (°C)
    real<lower=0> prior_sigma_t;       // Prior SD, shared across samples (°C)

    // ─── Optional non-thermal predictors ──────────────────────────────────────
    int<lower=0, upper=1> use_gdgt23ratio;
    int<lower=0, upper=1> use_no3;
    vector[N] gdgt23ratio;
    vector[N] no3;
    real<lower=0> no3_cutoff;          // MUST match the forward posterior's attrs

    // ─── Forward calibration posterior — M draws (all same-index) ─────────────
    // Each vector has length M. Row m is one complete self-consistent draw from
    // the BOUNDED-T forward posterior: {T₀_m, k_m, b_m, ν_m, γ_m, σ_m}.
    // All indexed by [m] in the inner loop to preserve parameter correlations.
    int<lower=1> M;
    vector[M] t0;
    vector[M] k;
    vector[M] b;
    vector[M] v;
    vector[M] gamma_G23;       // γ_{G₂/₃} per draw, °C per unit (zeros if unused)
    vector[M] gamma_NO3;       // γ_{NO₃} per draw, °C per log₁₀ unit (zeros if unused)
    vector[M] sigma_proxyObs;  // Residual calibration noise per draw

    // ─── Parallelism control ───────────────────────────────────────────────────
    // grainsize: approximate number of samples per parallel chunk.
    // Set to 1 for maximum parallelism; set to N to disable (single thread).
    int<lower=1> grainsize;
}

parameters {
    // One temperature per sample — the ONLY parameter in this model.
    // "Unconstrained" means no physical lower bound imposed on t_est.
    vector[N] t_est;
}

model {
    // Create an index array {1, 2, …, N} that reduce_sum uses to partition
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
        gamma_G23, gamma_NO3, sigma_proxyObs
    );
}
