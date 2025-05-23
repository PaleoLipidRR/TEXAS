// invT_logistic_fixed_multiv.stan (generalized)
data {
  int<lower=1> N_downcore;
  vector[N_downcore] scaledRI_downcore;
  vector[N_downcore] prior_mu_t;
  real prior_sigma_t;

  // generic posterior parameters
  int<lower=1> M;
  vector[M] t0;
  vector[M] k;
  vector[M] b;
  vector[M] sigma_scaledRI;

  // optional predictors
  vector[N_downcore] gdgt23ratio_downcore;
  vector[M] beta0_gdgt23ratio;
  int<lower=0, upper=1> use_gdgt23ratio;

  vector[N_downcore] no3_downcore;
  vector[M] beta0_no3;
  int<lower=0, upper=1> use_no3;
}

parameters {
  matrix[N_downcore, M] t_est;
}

model {
  for (m in 1:M) {
    col(t_est, m) ~ normal(prior_mu_t, prior_sigma_t);

    vector[N_downcore] mu_scaledRI = 
      (1 - b[m]) * inv_logit(k[m] * (col(t_est, m) - t0[m])) 
      + b[m];

    if (use_gdgt23ratio == 1)
      mu_scaledRI += beta0_gdgt23ratio[m] * gdgt23ratio_downcore;

    if (use_no3 == 1)
      mu_scaledRI += beta0_no3[m] * no3_downcore;

    scaledRI_downcore ~ normal(mu_scaledRI, sigma_scaledRI[m]);
  }
}
