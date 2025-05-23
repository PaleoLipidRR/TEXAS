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
  // shared logistic parameters for culture+mesocosm
  real<lower=-1.8>     t0_culmeso;    // inflection point
  real<lower=0,upper=1> k_culmeso;    // steepness
  real<lower=0,upper=1> b_culmeso;    // lower asymptote (on [0,1] via beta prior)

  // logistic parameters for coretop
  real<lower=-1.8>     t0_coretop;
  real<lower=0,upper=1> k_coretop;
  real<lower=0,upper=1> b_coretop;

  // hierarchical scale parameters (hyperpriors)
  real<lower=0>        sigma_t0_culmeso;
  real<lower=0>        sigma_k_culmeso;
  real<lower=0>        sigma_b_culmeso;

  // observation noise
  real<lower=0>        sigma_scaledRI_cul;  // culture noise
  real<lower=0>        sigma_scaledRI_meso;  // mesocosm noise
  real<lower=0>        sigma_scaledRI_coretop;  // coretop noise
}

model {
  // 1 Priors for shared parameters for culture+mesocosm
  t0_culmeso    ~ normal(30, 10) T[-1.8, ];  // truncated normal
  k_culmeso     ~ beta(2, 5);
  b_culmeso     ~ beta(2, 5);

  // 2 Hyperpriors for scales (weakly informative)
  sigma_t0_culmeso     ~ cauchy(0, 1);
  sigma_k_culmeso      ~ cauchy(0, 1);
  sigma_b_culmeso      ~ cauchy(0, 1);

  // 3 Priors for observation noise
  sigma_scaledRI_cul ~ normal(0.01, 0.1);
  sigma_scaledRI_meso ~ normal(0.01, 0.1);

  // 4 Likelihoods for culture and mesocosm
  vector[N_cul] mu_scaledRI_cul = (1 - b_culmeso)   * inv_logit(k_culmeso   * (t_cul - t0_culmeso))   + b_culmeso;
  vector[N_meso] mu_scaledRI_meso = (1 - b_culmeso)   * inv_logit(k_culmeso   * (t_meso - t0_culmeso))   + b_culmeso;

  scaledRI_cul ~ normal(mu_scaledRI_cul, sigma_scaledRI_cul);
  scaledRI_meso ~ normal(mu_scaledRI_meso, sigma_scaledRI_meso);
  
  // 5 Coretop priors 
  t0_coretop  ~ normal(t0_culmeso, sigma_t0_culmeso);
  k_coretop   ~ normal(k_culmeso, sigma_k_culmeso);
  b_coretop   ~ normal(b_culmeso, sigma_b_culmeso);

  // 6 Likelihoods for coretops
  vector[N_coretop] mu_scaledRI_coretop = (1 - b_coretop) * inv_logit(k_coretop * (t_coretop - t0_coretop)) + b_coretop;
  sigma_scaledRI_coretop ~ normal(0.01, 0.1);

  scaledRI_coretop ~ normal(mu_scaledRI_coretop, sigma_scaledRI_coretop);
}
