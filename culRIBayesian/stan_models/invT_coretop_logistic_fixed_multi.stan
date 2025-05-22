data {
  int<lower=1> N;
  vector[N] scaledRI_coretop;
  vector[N] prior_mu_thermoT;
  real prior_sigma_thermoT;

  int<lower=1> M;
  vector[M] x0_coretop;
  vector[M] k_coretop;
  vector[M] b_coretop;
  vector[M] sigma_coretop_scaledRI;

  vector[N] gdgt23ratio;
  vector[M] beta0_gdgt23ratio;
  int<lower=0, upper=1> use_gdgt23ratio;

  vector[N] depthIntg_thermoT_no3;
  vector[M] beta0_depthIntg_thermoT_no3;
  int<lower=0, upper=1> use_depthIntg_thermoT_no3;
}

parameters {
  matrix[N, M] thermoT_est;
}

model {
  for (m in 1:M) {
    col(thermoT_est, m) ~ normal(prior_mu_thermoT, prior_sigma_thermoT);

    vector[N] mu_scaledRI = 
      (1 - b_coretop[m]) * inv_logit(k_coretop[m] * (col(thermoT_est, m) - x0_coretop[m])) 
      + b_coretop[m];

    if (use_gdgt23ratio == 1)
      mu_scaledRI += beta0_gdgt23ratio[m] * gdgt23ratio;

    if (use_depthIntg_thermoT_no3 == 1)
      mu_scaledRI += beta0_depthIntg_thermoT_no3[m] * depthIntg_thermoT_no3;

    scaledRI_coretop ~ normal(mu_scaledRI, sigma_coretop_scaledRI[m]);
  }
}
