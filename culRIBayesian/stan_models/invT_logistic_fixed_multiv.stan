// invT_logistic_fixed_multiv.stan (generalized)
data {
  int<lower=1> N;
  vector[N] scaledRI;
  vector[N] prior_mu_t;
  real prior_sigma_t;

  // generic posterior parameters
  int<lower=1> M;
  vector[M] t0;
  vector[M] k;
  vector[M] b;
  vector[M] sigma_scaledRI;

  // optional predictors
  vector[N] gdgt23ratio;
  vector[M] beta0_gdgt23ratio;
  int<lower=0, upper=1> use_gdgt23ratio;

  vector[N] no3;
  vector[M] beta0_no3;
  int<lower=0, upper=1> use_no3;
}

parameters {
  matrix[N, M] t_est;
}

model {
  for (m in 1:M) {
    col(t_est, m) ~ normal(prior_mu_t, prior_sigma_t);

    vector[N] mu_scaledRI = 
      (1 - b[m]) * inv_logit(k[m] * (col(t_est, m) - t0[m])) 
      + b[m];

    if (use_gdgt23ratio == 1)
      mu_scaledRI += beta0_gdgt23ratio[m] * gdgt23ratio;

    if (use_no3 == 1)
      mu_scaledRI += beta0_no3[m] * no3;

    scaledRI ~ normal(mu_scaledRI, sigma_scaledRI[m]);
  }
}
