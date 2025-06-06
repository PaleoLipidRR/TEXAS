data {
  int<lower=1> N_cul;         // number of culture observations
  vector[N_cul] t_cul;           // temperatures
  vector[N_cul] scaledRI_cul;           // scaled ring index

  int<lower=1> N_meso;         // number of mesocosm observations
  vector[N_meso] t_meso;
  vector[N_meso] scaledRI_meso;

  int<lower=1> N_crtp;         // number of coretop observations
  vector[N_crtp] t_crtp;
  vector[N_crtp] scaledRI_crtp;
}

parameters {
  real<lower=-4>         t0_culmesocore;      // inflection point
  real<lower=0>          k_culmesocore;       // steepness
  real<lower=0>          b_culmesocore;       // lower asymptote

  real<lower=0> sigma_scaledRI_cul;          // noise for dataset 1
  real<lower=0> sigma_scaledRI_meso;          // noise for dataset 2
  real<lower=0> sigma_scaledRI_crtp;          // noise for dataset 3
}

model {
  // Priors
  t0_culmesocore      ~ normal(20, 20) T[-4, ];
  k_culmesocore       ~ normal(0, 0.25);
  b_culmesocore       ~ beta(2, 5);
  sigma_scaledRI_cul        ~ cauchy(0, 0.1);
  sigma_scaledRI_meso       ~ cauchy(0, 0.1);
  sigma_scaledRI_crtp       ~ cauchy(0, 0.1);

  // Logistic‐curve means (vectorized)
  vector[N_cul] mu_scaledRI_cul = (1 - b_culmesocore) * inv_logit(k_culmesocore * (t_cul - t0_culmesocore)) + b_culmesocore;
  vector[N_meso] mu_scaledRI_meso = (1 - b_culmesocore) * inv_logit(k_culmesocore * (t_meso - t0_culmesocore)) + b_culmesocore;
  vector[N_crtp] mu_scaledRI_crtp = (1 - b_culmesocore) * inv_logit(k_culmesocore * (t_crtp - t0_culmesocore)) + b_culmesocore;

  // Likelihoods
  scaledRI_cul      ~ normal(mu_scaledRI_cul, sigma_scaledRI_cul);
  scaledRI_meso     ~ normal(mu_scaledRI_meso, sigma_scaledRI_meso);
  scaledRI_crtp  ~ normal(mu_scaledRI_crtp, sigma_scaledRI_crtp);
}

generated quantities {
  vector[N_crtp] scaledRI_hat = (1 - b_culmesocore) * inv_logit(k_culmesocore * (t_crtp - t0_culmesocore)) + b_culmesocore;

}