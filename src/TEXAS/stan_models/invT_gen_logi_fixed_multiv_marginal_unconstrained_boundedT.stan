// ═══════════════════════════════════════════════════════════════════════════════
// invT_gen_logi_fixed_multiv_marginal_unconstrained_boundedT.stan
//
// PURPOSE: Inverse (paleotemperature) counterpart of the BOUNDED-T forward model
//          gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT.stan.
//
// WHY THIS FILE HAS TO EXIST
//   Every other invT_* model applies the non-thermal corrections additively on the
//   RESPONSE:
//       mu = b + beta_G23*g23 + beta_NO3*log10(no3) + (1-b)/(1+exp(-k(T-T0)))^(1/v)
//   The bounded-T forward model instead moves them INSIDE the logistic, as a shift
//   of the inflection point:
//       T0_eff = T0 + gamma_G23*g23 + gamma_NO3*log10(no3)
//       mu     = b + (1-b)/(1+exp(-k(T - T0_eff)))^(1/v)
//   Those are different likelihoods. Feeding a bounded-T posterior into the
//   additive inverse would silently reconstruct temperatures under a model that was
//   never fitted — so the inverse must be reparameterized to match.
//
// WHAT IS UNCHANGED from invT_gen_logi_fixed_multiv_marginal_unconstrained.stan:
//   the marginal (log-sum-exp) strategy over M calibration draws, the reduce_sum
//   parallelization, the per-sample Normal prior on T computed inside ll_chunk,
//   the NO3 gating rule, and the "unconstrained" treatment of t_est (no lower
//   bound). Only the mean function differs, and only in where the predictors enter.
//
// WHAT CHANGES IN THE DATA BLOCK:
//   beta_G23 / beta_NO3  ->  gamma_G23 / gamma_NO3
//   Same shape (length M, one value per forward-posterior draw), different units:
//   gamma is degC per unit predictor, not Scaled-RI units per unit predictor.
//   Pass zeros for a predictor that is switched off, exactly as before.
//
// A USEFUL PROPERTY: because the predictors shift T0 rather than mu, the inverse
//   is better behaved than the additive one. In the additive model a large
//   correction can push mu outside [b, 1], where the inverse does not exist; here
//   mu stays in (b, 1) for every finite gamma, so the only samples without a
//   solution are those whose proxy genuinely falls outside the curve's range.
//
// NOTE ON VARIANTS: the truncated-prior and hard-constraint flavours differ from
//   this file only in the prior/parameter declaration for t_est (a lower bound, or
//   a truncated normal_lpdf). Copy this mean function into those if they are needed.
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
        // ─── THE ONE STRUCTURAL DIFFERENCE FROM THE ADDITIVE MODEL ───────────
        // Predictors shift the inflection point, not the response. Read it as:
        // "this community structure / nutrient level makes the curve turn over at
        // a different temperature", rather than "it offsets the index".
        real t0_eff = t0[m];

        // Ecology correction: gamma_{G2/3} degC per unit gdgt23ratio.
        if (use_gd == 1)
          t0_eff += gamma_gd[m] * gd_seg[i];

        // NO3 correction: gamma_{NO3} degC per log10 unit, applied conditionally.
        // logno3 = 0 when NO3 is outside the valid range, so no correction applied
        // — identical gating to the additive model, so the same samples are
        // corrected in both.
        if (use_no3 == 1) {
          real logno3 = 0.0;
          if (n3_seg[i] > 0.0 && n3_seg[i] < no3_cutoff)
            logno3 = log10(n3_seg[i] + 1e-9);  // small offset avoids log(0)
          t0_eff += gamma_no3[m] * logno3;
        }

        // The Richards curve, evaluated against the shifted inflection point.
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
