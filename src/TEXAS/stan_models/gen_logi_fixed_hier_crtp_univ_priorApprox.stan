// ===============================================================================
// gen_logi_fixed_hier_crtp_univ_priorApprox.stan
//
// PURPOSE: Coretop forward calibration of the Scaled Ring Index against
//          temperature alone, with no non-thermal predictors. This is the
//          thermal-only fit: it gives the univariate calibration, and its
//          R2_full supplies the R2_thermal that the errors-in-variables models
//          need to scale their process-noise prior.
//
// CALIBRATION CURVE - generalized logistic (Richards), upper asymptote fixed at
// 1 and Q fixed at 1:
//
//   RI = b + (1 - b) / (1 + exp(-k * (T - T0)))^(1/nu)
//
// T0 is the curve's LOCATION parameter, not its inflection point. The steepest
// response sits at T0 - ln(nu)/k, several degC below T0 for the fitted nu, and
// the slope varies severalfold across the sampled range - so there is no single
// thermal sensitivity to quote for this curve.
//
// WORKFLOW (two-stage priorApprox):
//   Stage 1: fit gen_logi_fixed_culmeso.stan on the culture and mesocosm data
//            and pass the posterior mean and SD of {t0, k, b, v} in as
//            prior_mean_* / prior_sd_*.
//   Stage 2: this model, which fits the coretop parameters conditional on those
//            hyperpriors. Because the coretop stage is separate, it can be
//            re-run without refitting the culture and mesocosm data.
//
// GENERATED QUANTITIES:
//   R2_full      frequentist 1 - RSS/TSS, the quantity reported in the
//                manuscript and comparable with published TEX86 calibrations
//   bayesR2_full var(mu) / (var(mu) + sigma^2), Gelman et al. (2019)
//   RMSE_full    root mean squared residual, in Scaled RI units
//   max_slope_temp  the temperature of steepest response, T0 - ln(nu)/k
//
//   R2_full is the one to difference across posteriors for sequential variance
//   partitioning in Python; the two R2 definitions are not interchangeable.
// ===============================================================================

data {
  int<lower=1> N_crtp;
  vector[N_crtp] t_crtp;
  vector[N_crtp] proxyObs_crtp;

  real prior_mean_t0;
  real prior_sd_t0;
  real prior_mean_k;
  real prior_sd_k;
  real prior_mean_b;
  real prior_sd_b;

  real prior_mean_v;
  real prior_sd_v;
}

parameters {
  real<lower=10, upper=50> t0_crtp;            // curve location (steepest response at t0 - ln(v)/k)
  real<lower=0.01, upper=0.5> k_crtp;          // growth rate
  real<lower=0.1, upper=1.0> b_crtp;           // lower asymptote (upper=1 matches joint model)
  real<lower=0.1, upper=10> v_crtp;           // asymmetry / shape parameter (nu)
  real<lower=0> sigma_proxyObs_crtp;          // residual std dev
}

model {
  // Priors
  t0_crtp ~ normal(prior_mean_t0, prior_sd_t0);
  k_crtp  ~ normal(prior_mean_k, prior_sd_k);
  b_crtp  ~ normal(prior_mean_b, prior_sd_b);
  v_crtp  ~ normal(prior_mean_v, prior_sd_v);
  sigma_proxyObs_crtp ~ normal(0, 0.1);

  // Generalized logistic mean (upper asymptote fixed at 1, Q fixed to 1)
  vector[N_crtp] mu_proxyObs_crtp = b_crtp + (1 - b_crtp)
    ./ pow(1 + exp(-k_crtp * (t_crtp - t0_crtp)), 1 / v_crtp);

  // Likelihood
  proxyObs_crtp ~ normal(mu_proxyObs_crtp, sigma_proxyObs_crtp);
}

generated quantities {
    // Temperature of steepest response for the Richards curve. Setting
    // d2f/dT2 = 0 gives exp(-k(T - T0)) = nu, hence T = T0 - ln(nu)/k, which
    // lies BELOW T0 for nu > 1. T0 itself is only the location parameter.
    real max_slope_temp = t0_crtp - log(v_crtp) / k_crtp;

    // -- In-sample R^2 for this model -------------------------------------------
    // R2_full     : frequentist 1 - RSS/TSS  (matches figure; fixed denominator)
    // bayesR2_full: Bayesian var(mu)/(var(mu)+sigma^2)  (Gelman et al. 2019)
    // Both computed using this model's own estimated parameters (T only, no
    // non-thermal predictors). Use R2_full for sequential variance partitioning
    // by differencing across posteriors in Python.
    real R2_full;
    real bayesR2_full;
    real RMSE_full;

    {   // local scope - mu vector not saved
        vector[N_crtp] mu    = b_crtp + (1 - b_crtp)
            ./ pow(1 + exp(-k_crtp * (t_crtp - t0_crtp)), 1.0 / v_crtp);

        vector[N_crtp] resid = proxyObs_crtp - mu;
        real ybar    = mean(proxyObs_crtp);
        real TSS     = dot_self(proxyObs_crtp - ybar);
        real RSS     = dot_self(resid);
        R2_full      = 1 - RSS / TSS;
        RMSE_full    = sqrt(RSS / N_crtp);

        real var_mu  = variance(mu);
        real sigma2  = sigma_proxyObs_crtp ^ 2;
        bayesR2_full = var_mu / (var_mu + sigma2);
    }
}
