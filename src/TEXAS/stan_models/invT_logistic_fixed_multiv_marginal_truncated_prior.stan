// ═══════════════════════════════════════════════════════════════════════════════
// invT_logistic_fixed_multiv_marginal_truncated_prior.stan
//
// PURPOSE: Bayesian paleotemperature reconstruction with non-thermal corrections
//          (GDGT-2/3 ratio and/or NO₃), parallelized via Stan's reduce_sum.
//          Standard logistic curve (Q = 1, ν = 1 fixed). Multivariate counterpart
//          of invT_logistic_fixed_univ_marginal_truncated_prior.stan.
//
// TEMPERATURE CONSTRAINT: "truncated_prior" variant
//   See invT_gen_logi_fixed_univ_marginal_truncated_prior.stan for the full
//   explanation of the inverse-CDF reparameterization.
//
// KEY DIFFERENCE from the hard_constraint multiv model:
//   ll_chunk does NOT include a prior — only the marginalized likelihood.
//   The prior is embedded in the q → t_est reparameterization.
// ═══════════════════════════════════════════════════════════════════════════════

functions {
  real ll_chunk(
      array[] int slice_indices,
      int start, int end,
      vector proxy_param,
      vector T,
      int use_gd, int use_no3,
      vector gd, vector no3, real no3_cutoff,
      vector t0, vector k, vector b,
      vector beta_gd, vector beta_no3,
      vector sigma
  ) {
    int M = rows(t0);
    int n_chunk = end - start + 1;
    real lp = 0;

    vector[n_chunk] y      = segment(proxy_param, start, n_chunk);
    vector[n_chunk] T_seg  = segment(T,        start, n_chunk);
    vector[n_chunk] gd_seg = segment(gd,       start, n_chunk);
    vector[n_chunk] n3_seg = segment(no3,      start, n_chunk);

    for (i in 1:n_chunk) {
      vector[M] llk;

      for (m in 1:M) {
        real lin = b[m];

        if (use_gd == 1)
          lin += beta_gd[m] * gd_seg[i];

        if (use_no3 == 1) {
          real logno3 = 0.0;
          if (n3_seg[i] > 0 && n3_seg[i] < no3_cutoff)
            logno3 = log10(n3_seg[i] + 1e-9);
          lin += beta_no3[m] * logno3;
        }

        // Standard logistic (Q=1, ν=1):
        real mu = lin + (1 - b[m]) / (1 + exp(-k[m] * (T_seg[i] - t0[m])));

        llk[m] = normal_lpdf(y[i] | mu, sigma[m]);
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
    // Note: no Q or v — standard logistic fixes Q=1, ν=1.
    vector[M] beta_G23;
    vector[M] beta_NO3;
    vector[M] sigma_proxy_param;

    int<lower=1> grainsize;

    real min_temp;
}

parameters {
    vector<lower=0, upper=1>[N] q;
}

transformed parameters {
    vector[N] t_est;
    for (n in 1:N) {
        real p_lower = normal_cdf(min_temp | prior_mu_t[n], prior_sigma_t);
        t_est[n] = prior_mu_t[n]
                 + prior_sigma_t * std_normal_qf(p_lower + (1.0 - p_lower) * q[n]);
    }
}

model {
    array[N] int indices = linspaced_int_array(N, 1, N);

    target += reduce_sum(
        ll_chunk, indices, grainsize,
        proxy_param, t_est,
        use_gdgt23ratio, use_no3, gdgt23ratio, no3, no3_cutoff,
        t0, k, b, beta_G23, beta_NO3, sigma_proxy_param
    );
}
