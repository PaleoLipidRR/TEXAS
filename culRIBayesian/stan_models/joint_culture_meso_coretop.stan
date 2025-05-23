data {
  int<lower=1> N_cul;         // number of culture observations
  vector[N_cul] t_cul;           // temperatures
  vector[N_cul] scaledRI_cul;           // scaled ring index

  int<lower=1> N_meso;         // number of mesocosm observations
  vector[N_meso] t_meso;
  vector[N_meso] scaledRI_meso;

  int<lower=1> N_coretop;         // number of coretop observations
  vector[N_coretop] t_coretop;
  vector[N_coretop] scaledRI_coretop;
}

parameters {
  real<lower=-4>         t0_culmesocore;      // inflection point
  real<lower=0>          k_culmesocore;       // steepness
  real<lower=0,upper=1>  b_culmesocore;       // lower asymptote

  real<lower=0> sigma_cul;          // noise for dataset 1
  real<lower=0> sigma_meso;          // noise for dataset 2
  real<lower=0> sigma_coretop;          // noise for dataset 3
}

model {
  // Priors
  t0_culmesocore      ~ normal(20, 20) T[-4, ];
  k_culmesocore       ~ normal(0, 0.25);
  b_culmesocore       ~ beta(2, 5);
  sigma_cul           ~ normal(0.01, 0.1) T[0.01, ];
  sigma_meso          ~ normal(0.01, 0.1) T[0.01, ];
  sigma_coretop       ~ normal(0.01, 0.1) T[0.01, ];

  // Logistic‐curve means (vectorized)
  vector[N_cul] mu_cul = (1 - b_culmesocore) * inv_logit(k_culmesocore * (t_cul - t0_culmesocore)) + b_culmesocore;
  vector[N_meso] mu_meso = (1 - b_culmesocore) * inv_logit(k_culmesocore * (t_meso - t0_culmesocore)) + b_culmesocore;
  vector[N_coretop] mu_coretop = (1 - b_culmesocore) * inv_logit(k_culmesocore * (t_coretop - t0_culmesocore)) + b_culmesocore;

  // Likelihoods
  scaledRI_cul      ~ normal(mu_cul, sigma_cul);
  scaledRI_meso     ~ normal(mu_meso, sigma_meso);
  scaledRI_coretop  ~ normal(mu_coretop, sigma_coretop);
}
