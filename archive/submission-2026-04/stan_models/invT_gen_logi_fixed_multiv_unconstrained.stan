// ===============================================================================
// invT_gen_logi_fixed_multiv_unconstrained.stan
//
// PURPOSE: Bayesian paleotemperature reconstruction from observed Scaled Ring
//          Index values, with non-thermal corrections (GDGT-2/3 ratio and/or
//          NO3) applied on the response.
//
// MEAN FUNCTION:
//   mu = b + beta_G23*g23 + beta_NO3*log10(no3) + (1-b)/(1+exp(-k*(T-T0)))^(1/v)
//   beta carries Scaled-RI units per unit predictor. The NO3 term applies only
//   where the observed value falls inside (0, no3_cutoff).
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
  real<lower=0> prior_sigma_t;

  vector[M] t0;
  vector[M] k;
  vector[M] b;
  vector[M] v;
  vector<lower=0>[M] sigma_proxyObs;

  int<lower=0,upper=1> use_gdgt23ratio;
  vector[N] gdgt23ratio;
  vector[M] beta_G23;

  int<lower=0,upper=1> use_no3;
  vector[N] no3;
  vector[M] beta_NO3;
  real no3_cutoff;
}

parameters {
  matrix[N, M] t_est;
}

model {
  for (m in 1:M) {
    vector[N] t_col = t_est[:, m];
    vector[N] mu_proxyObs;
    vector[N] denominator;
    vector[N] power_base;

    // Prior
    t_col ~ normal(prior_mu_t, prior_sigma_t);

    // Ensure the base of the pow() function is non-negative.
    power_base = fmax(0.0, 1 + exp(-k[m] * (t_col - t0[m])));
    denominator = pow(power_base, 1 / v[m]) + 1e-9;
    mu_proxyObs = b[m] + elt_divide(1 - b[m], denominator);

    // Optional GDGT-2/3 ratio term
    if (use_gdgt23ratio == 1) {
      mu_proxyObs += beta_G23[m] * gdgt23ratio;
    }

    // Optional nitrate term
    if (use_no3 == 1) {
      vector[N] logno3 = rep_vector(0.0, N);
      for (n in 1:N) {
        if (no3[n] > 0.0 && no3[n] < no3_cutoff) {
          logno3[n] = log10(no3[n] + 1e-9);
        }
      }
      mu_proxyObs += beta_NO3[m] * logno3;
    }

    // Likelihood
    proxyObs ~ normal(mu_proxyObs, sigma_proxyObs[m]);
  }
}
