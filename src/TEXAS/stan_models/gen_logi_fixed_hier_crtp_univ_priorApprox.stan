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
  real<lower=0.1> v_crtp;                     // asymmetry / shape parameter (ν)
  real<lower=0> sigma_proxyObs_crtp;          // residual std dev
}

model {
  // Priors
  t0_crtp ~ normal(prior_mean_t0, prior_sd_t0);
  k_crtp  ~ normal(prior_mean_k, prior_sd_k);
  b_crtp  ~ normal(prior_mean_b, prior_sd_b);
  v_crtp  ~ normal(prior_mean_v, prior_sd_v);
  sigma_proxyObs_crtp ~ normal(0.01, 0.1);

  // Generalized logistic mean (upper asymptote fixed at 1, Q fixed to 1)
  vector[N_crtp] mu_proxyObs_crtp = b_crtp + (1 - b_crtp)
    ./ pow(1 + exp(-k_crtp * (t_crtp - t0_crtp)), 1 / v_crtp);

  // Likelihood
  proxyObs_crtp ~ normal(mu_proxyObs_crtp, sigma_proxyObs_crtp);
}

generated quantities {
  real inflection_point;
  inflection_point = t0_crtp + log(v_crtp) / k_crtp;
}
