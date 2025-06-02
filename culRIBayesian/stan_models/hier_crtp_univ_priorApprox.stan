data {
  int<lower=1> N_crtp;
  vector[N_crtp] t_crtp;
  vector[N_crtp] scaledRI_crtp;

  real prior_mean_t0;
  real prior_sd_t0;
  real prior_mean_k;
  real prior_sd_k;
  real prior_mean_b;
  real prior_sd_b;
}

parameters {
  real<lower=10, upper=50> t0_crtp;
  real<lower=0.01, upper=0.5> k_crtp;
  real<lower=0.1, upper=0.6> b_crtp;
  real<lower=0> sigma_scaledRI_crtp;
}

model {
  t0_crtp ~ normal(prior_mean_t0, prior_sd_t0);
  k_crtp  ~ normal(prior_mean_k, prior_sd_k);
  b_crtp  ~ normal(prior_mean_b, prior_sd_b);
  sigma_scaledRI_crtp ~ normal(0.01, 0.1);

  vector[N_crtp] mu = (1 - b_crtp) * inv_logit(k_crtp * (t_crtp - t0_crtp)) + b_crtp;
  scaledRI_crtp ~ normal(mu, sigma_scaledRI_crtp);
}
