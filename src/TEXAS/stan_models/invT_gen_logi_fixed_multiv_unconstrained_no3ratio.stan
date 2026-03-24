// ═══════════════════════════════════════════════════════════════════════════════
// invT_gen_logi_fixed_multiv_unconstrained_no3ratio.stan
//
// PURPOSE: Ensemble-mode (non-marginal) Bayesian paleotemperature reconstruction
//          with non-thermal corrections (GDGT-2/3 ratio and/or NO₃).
//
// DIFFERENCE FROM invT_gen_logi_fixed_multiv_unconstrained.stan:
//   The NO₃ correction uses log₁₀(NO₃ / no3_cutoff) instead of log₁₀(NO₃).
//   Must be paired with a forward posterior from a _no3ratio forward model.
//
// ENSEMBLE MODE: t_est has shape (N, M) — one temperature per sample per draw.
//   The marginal model (marginal_unconstrained_no3ratio) is preferred for most
//   uses; this file is retained for ensemble diagnostics or legacy comparisons.
// ═══════════════════════════════════════════════════════════════════════════════

data {
  int<lower=1> N;
  int<lower=1> M;

  vector[N] proxy_param;
  vector[N] prior_mu_t;
  real<lower=0> prior_sigma_t;

  vector[M] t0;
  vector[M] k;
  vector[M] b;
  vector[M] v;
  vector<lower=0>[M] sigma_proxy_param;

  int<lower=0,upper=1> use_gdgt23ratio;
  vector[N] gdgt23ratio;
  vector[M] beta_G23;

  int<lower=0,upper=1> use_no3;
  vector[N] no3;
  vector[M] beta_NO3;
  real<lower=0> no3_cutoff;
}

parameters {
  matrix[N, M] t_est;
}

model {
  for (m in 1:M) {
    vector[N] t_col = t_est[:, m];
    vector[N] mu_proxy_param;
    vector[N] denominator;
    vector[N] power_base;

    // Prior
    t_col ~ normal(prior_mu_t, prior_sigma_t);

    power_base = fmax(0.0, 1 + exp(-k[m] * (t_col - t0[m])));
    denominator = pow(power_base, 1 / v[m]) + 1e-9;
    mu_proxy_param = b[m] + elt_divide(1 - b[m], denominator);

    if (use_gdgt23ratio == 1) {
      mu_proxy_param += beta_G23[m] * gdgt23ratio;
    }

    // NO₃ correction using log₁₀(NO₃ / no3_cutoff) — zero at the boundary.
    if (use_no3 == 1) {
      vector[N] logno3ratio = rep_vector(0.0, N);
      for (n in 1:N) {
        if (no3[n] > 0.0 && no3[n] < no3_cutoff) {
          logno3ratio[n] = log10(no3[n] / no3_cutoff);
        }
      }
      mu_proxy_param += beta_NO3[m] * logno3ratio;
    }

    proxy_param ~ normal(mu_proxy_param, sigma_proxy_param[m]);
  }
}
