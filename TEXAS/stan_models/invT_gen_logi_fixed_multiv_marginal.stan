// invT_gen_logi_fixed_multiv_marginal.stan  (L fixed = 1)

functions {
  real ll_chunk(int start, int end,
                vector subset_scaledRI,
                vector t_est, vector prior_mu_t, real prior_sigma_t,
                int use_gd, int use_no3,
                vector gd, vector no3, real no3_cutoff,
                vector t0, vector k, vector b, vector Q, vector v,
                vector beta_gd, vector beta_no3, vector sigma) {
    int M = rows(t0);
    real lp = 0;

    // prior contribution for this chunk
    lp += normal_lpdf(t_est[start:end] | prior_mu_t[start:end], prior_sigma_t);

    // likelihood contribution
    for (n in start:end) {
      vector[M] llk;
      for (m in 1:M) {
        real lin = b[m];
        if (use_gd == 1)  lin += beta_gd[m]  * gd[n];
        if (use_no3 == 1) {
          real logno3 = 0.0;
          if (no3[n] > 0.0 && no3[n] < no3_cutoff) {
            logno3 = log10(no3[n] + 1e-9);
          }
          lin += beta_no3[m] * logno3;
        }
        real mu = lin + (1 - b[m]) / pow(1 + Q[m] * exp(-k[m] * (t_est[n] - t0[m])), 1.0 / v[m]);
        llk[m] = normal_lpdf(subset_scaledRI[n] | mu, sigma[m]);
      }
      lp += log_sum_exp(llk) - log(M);
    }
    return lp;
  }
}

data {
  int<lower=1> N;
  int<lower=1> M;
  vector[N] scaledRI;
  vector[N] prior_mu_t;
  real<lower=0> prior_sigma_t;

  // Optional predictors
  int<lower=0,upper=1> use_gdgt23ratio;
  int<lower=0,upper=1> use_no3;
  vector[N] gdgt23ratio;
  vector[N] no3;
  real<lower=0> no3_cutoff;

  // Forward posterior draws
  vector[M] t0;
  vector[M] k;
  vector[M] b;
  vector[M] Q;
  vector[M] v;
  vector[M] beta0_gdgt23ratio;  // zeros if unused
  vector[M] beta0_no3;          // zeros if unused
  vector[M] sigma_scaledRI;

  int<lower=1> grainsize;
}

parameters {
  vector[N] t_est;
}

model {
  target += reduce_sum(
    ll_chunk, scaledRI, grainsize,
    t_est, prior_mu_t, prior_sigma_t,
    use_gdgt23ratio, use_no3, gdgt23ratio, no3, no3_cutoff,
    t0, k, b, Q, v,
    beta0_gdgt23ratio, beta0_no3, sigma_scaledRI
  );
}
