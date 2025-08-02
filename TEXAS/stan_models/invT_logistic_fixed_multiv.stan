data {
  int<lower=1> N;
  int<lower=1> M;

  vector[N] scaledRI;
  vector[N] prior_mu_t;
  real prior_sigma_t;

  vector[M] t0;
  vector[M] k;
  vector[M] b;
  vector[M] sigma_scaledRI;

  // optional predictors
  int<lower=0,upper=1> use_gdgt23ratio;
  vector[N] gdgt23ratio;
  vector[M] beta0_gdgt23ratio;

  int<lower=0,upper=1> use_no3;
  vector[N] no3;
  vector[M] beta0_no3;
  real no3_cutoff;
}

parameters {
  matrix[N, M] t_est;
}

model {
  for (m in 1:M) {
    // 1 Prior on each column of t_est
    t_est[, m] ~ normal(prior_mu_t, prior_sigma_t);

    // 2 Base logistic‐mix model, vectorized over n:
    vector[N] mu_scaledRI = (1.0 - b[m]) * inv_logit( k[m] * (t_est[, m] - t0[m]) ) + b[m];

    // 3 Optional GDGT23Ratio term
    if (use_gdgt23ratio == 1) {
      mu_scaledRI += beta0_gdgt23ratio[m] * gdgt23ratio;
    }

    // 4 Optional nitrate term (only where 0 < no3 < cutoff)
    if (use_no3 == 1) {
      vector[N] logno3;
      for (n in 1:N) {
        if (no3[n] > 0.0 && no3[n] < no3_cutoff)
          logno3[n] = log10(no3[n]);
        else
          logno3[n] = 0.0;
      }
      mu_scaledRI += beta0_no3[m] * logno3;
    }

    // 5 Likelihood
    scaledRI ~ normal(mu_scaledRI, sigma_scaledRI[m]);
  }
}
