data {
  int<lower=1> N;
  int<lower=1> M;

  vector[N] scaledRI;
  vector[N] prior_mu_t;
  real prior_sigma_t;

  vector[M] t0;
  vector[M] k;
  vector[M] b;
  vector[M] Q;
  vector[M] v;
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
    vector[N] t_col = t_est[:, m];
    vector[N] mu_scaledRI;

    // Prior
    t_col ~ normal(prior_mu_t, prior_sigma_t);

    // Base logistic-mix model
    mu_scaledRI = b[m] + elt_divide(1 - b[m],
                     pow(1 + Q[m] * exp(-k[m] * (t_col - t0[m])), 1 / v[m]));

    // Optional GDGT-2/3 ratio term
    if (use_gdgt23ratio == 1)
      mu_scaledRI += beta0_gdgt23ratio[m] * gdgt23ratio;

    // Optional nitrate term
    if (use_no3 == 1) {
      vector[N] logno3 = rep_vector(0.0, N);
      for (n in 1:N)
        if (no3[n] > 0.0 && no3[n] < no3_cutoff)
          logno3[n] = log10(no3[n]);

      mu_scaledRI += beta0_no3[m] * logno3;
    }

    // Likelihood
    scaledRI ~ normal(mu_scaledRI, sigma_scaledRI[m]);
  }
}