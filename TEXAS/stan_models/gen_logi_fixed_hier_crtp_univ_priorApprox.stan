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

  real prior_mean_Q;
  real prior_sd_Q;
  real prior_mean_v;
  real prior_sd_v;
}

parameters {
  real<lower=10, upper=50> t0_crtp;            // center (not necessarily inflection point)
  real<lower=0.01, upper=0.5> k_crtp;          // growth rate
  real<lower=0.1, upper=0.6> b_crtp;           // lower asymptote
  real<lower=0.01> Q_crtp;                    // curve-start factor (Q)
  real<lower=0.1> v_crtp;                     // asymmetry / shape parameter (ν)
  real<lower=0> sigma_scaledRI_crtp;          // residual std dev
}

model {
  // Priors
  t0_crtp ~ normal(prior_mean_t0, prior_sd_t0);
  k_crtp  ~ normal(prior_mean_k, prior_sd_k);
  b_crtp  ~ normal(prior_mean_b, prior_sd_b);
  Q_crtp  ~ normal(prior_mean_Q, prior_sd_Q);
  v_crtp  ~ normal(prior_mean_v, prior_sd_v);
  sigma_scaledRI_crtp ~ normal(0.01, 0.1);

  // Generalized logistic mean (upper asymptote fixed at 1)
  vector[N_crtp] mu_scaledRI_crtp = b_crtp + (1 - b_crtp)
    ./ pow(1 + Q_crtp * exp(-k_crtp * (t_crtp - t0_crtp)), 1 / v_crtp);

  // Likelihood
  scaledRI_crtp ~ normal(mu_scaledRI_crtp, sigma_scaledRI_crtp);
}

generated quantities {
  real inflection_point;
  inflection_point = t0_crtp + log(v_crtp) / k_crtp;
}
