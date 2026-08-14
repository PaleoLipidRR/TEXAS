// ===============================================================================
// invT_gen_logi_fixed_univ_unconstrained.stan
//
// PURPOSE: Bayesian paleotemperature reconstruction from observed Scaled Ring
//          Index values, with no non-thermal predictors.
//
// APPROACH - "Ensemble": one temperature is estimated for each of the N samples
//   under each of the M forward-posterior draws, giving an N x M parameter
//   block. Calibration uncertainty is carried by spreading across draws rather
//   than by marginalizing inside the likelihood.
//
//   This costs N*M parameters instead of N. The marginal (log-sum-exp) files in
//   this directory solve the same inference problem with N parameters and are
//   what production runs use.
//
// TEMPERATURE CONSTRAINT: "unconstrained" - t_est has no lower bound, so
//   reconstructions may fall below the seawater freezing point where the data
//   drive them there.
// ===============================================================================

data {
  int<lower=1> N;       
  int<lower=1> M;       

  vector[N] proxyObs;    
  vector[N] prior_mu_t;
  real prior_sigma_t;

  vector[M] t0;
  vector[M] k;
  vector[M] b;
  vector[M] v;
  vector[M] sigma_proxyObs;
}

parameters {
  matrix[N,M] t_est;  // estimated temperatures
}

model {
  vector[N] mu_proxyObs;

  for (m in 1:M) {
    vector[N] t_col = t_est[:, m];

    t_col ~ normal(prior_mu_t, prior_sigma_t);

    mu_proxyObs = b[m] + elt_divide(1 - b[m],
                     pow(1 + exp(-k[m] * (t_col - t0[m])), 1 / v[m]));

    proxyObs ~ normal(mu_proxyObs, sigma_proxyObs[m]);
  }
}