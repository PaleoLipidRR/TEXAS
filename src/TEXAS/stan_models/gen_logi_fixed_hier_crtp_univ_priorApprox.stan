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
  real<lower=10, upper=50> t0_crtp;            // center (not necessarily inflection point)
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
