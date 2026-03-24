// ═══════════════════════════════════════════════════════════════════════════════
// invT_gen_logi_fixed_multiv_marginal_unconstrained_no3ratio.stan
//
// PURPOSE: Bayesian paleotemperature reconstruction with non-thermal corrections
//          (GDGT-2/3 ratio and/or NO₃), parallelized via Stan's reduce_sum.
//
// DIFFERENCE FROM invT_gen_logi_fixed_multiv_marginal_unconstrained.stan:
//   The NO₃ correction uses log₁₀(NO₃ / no3_cutoff) instead of log₁₀(NO₃).
//   This centres the correction at zero exactly at the threshold, ensuring
//   continuity and a monotonic relationship between NO₃ and reconstructed T.
//   Must be paired with a forward posterior from a _no3ratio forward model.
//
// TEMPERATURE CONSTRAINT: "unconstrained" variant — no lower bound on t_est.
// ═══════════════════════════════════════════════════════════════════════════════

functions {
  real ll_chunk(array[] int slice_indices,
                int start, int end,
                vector proxy_param,
                vector t_est, vector prior_mu_t, real prior_sigma_t,
                int use_gd, int use_no3,
                vector gd, vector no3, real no3_cutoff,
                vector t0, vector k, vector b, vector v,
                vector beta_gd, vector beta_no3, vector sigma) {

    int M = rows(t0);
    real lp = 0;
    int n_chunk = end - start + 1;

    vector[n_chunk] t_seg    = segment(t_est,      start, n_chunk);
    vector[n_chunk] mu_seg   = segment(prior_mu_t, start, n_chunk);
    vector[n_chunk] gd_seg   = segment(gd,         start, n_chunk);
    vector[n_chunk] n3_seg   = segment(no3,        start, n_chunk);
    vector[n_chunk] y_seg    = segment(proxy_param,   start, n_chunk);

    // Prior contribution for this chunk: T_n ~ Normal(prior_mu_t_n, prior_sigma_t)
    lp += normal_lpdf(t_seg | mu_seg, prior_sigma_t);

    // Likelihood contribution: marginalize over M calibration draws for each n.
    for (i in 1:n_chunk) {
      vector[M] llk;

      for (m in 1:M) {
        real lin = b[m];

        // Ecology correction β_{G₂/₃} × gdgt23ratio (Eq. 6)
        if (use_gd == 1)
          lin += beta_gd[m] * gd_seg[i];

        // NO₃ correction β_{NO₃} × log₁₀(NO₃ / no3_cutoff) (Eq. 7c).
        // log₁₀(ratio) = 0 at the boundary; strictly negative below it.
        // No epsilon offset needed: the n3_seg[i] > 0 guard ensures valid input.
        if (use_no3 == 1) {
          real logno3ratio = 0.0;
          if (n3_seg[i] > 0.0 && n3_seg[i] < no3_cutoff)
            logno3ratio = log10(n3_seg[i] / no3_cutoff);
          lin += beta_no3[m] * logno3ratio;
        }

        real mu = lin + (1 - b[m])
            / pow(1 + exp(-k[m] * (t_seg[i] - t0[m])), 1.0 / v[m]);

        llk[m] = normal_lpdf(y_seg[i] | mu, sigma[m]);
      }

      lp += log_sum_exp(llk) - log(M);
    }
    return lp;
  }
}

data {
    int<lower=1> N;
    vector[N] proxy_param;

    vector[N] prior_mu_t;
    real<lower=0> prior_sigma_t;

    int<lower=0, upper=1> use_gdgt23ratio;
    int<lower=0, upper=1> use_no3;
    vector[N] gdgt23ratio;
    vector[N] no3;
    real<lower=0> no3_cutoff;

    int<lower=1> M;
    vector[M] t0;
    vector[M] k;
    vector[M] b;
    vector[M] v;
    vector[M] beta_G23;
    vector[M] beta_NO3;
    vector[M] sigma_proxy_param;

    int<lower=1> grainsize;
}

parameters {
    vector[N] t_est;
}

model {
    array[N] int indices = linspaced_int_array(N, 1, N);

    target += reduce_sum(
        ll_chunk, indices, grainsize,
        proxy_param, t_est, prior_mu_t, prior_sigma_t,
        use_gdgt23ratio, use_no3, gdgt23ratio, no3, no3_cutoff,
        t0, k, b, v,
        beta_G23, beta_NO3, sigma_proxy_param
    );
}
