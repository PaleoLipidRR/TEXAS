// joint_culture_meso.stan
data {
  // first dataset
  int<lower=1> N_cul;       
  vector[N_cul] t_cul;         
  vector[N_cul] scaledRI_cul;         

  // second dataset
  int<lower=1> N_meso;       
  vector[N_meso] t_meso;         
  vector[N_meso] scaledRI_meso;

  int<lower=1> N_crtp;         // number of coretop observations
  vector[N_crtp] t_crtp;    
}

parameters {
  real<lower=-1.8>    t0_culmeso;      // inflection point
  real<lower=0>       k_culmeso;       // steepness
  real<lower=0>       b_culmeso;       // lower asymptote
  
  real<lower=0>       sigma_scaledRI_cul;           // noise for dataset 1
  real<lower=0>       sigma_scaledRI_meso;           // noise for dataset 2

}

model {
  // Priors
  t0_culmeso    ~ normal(30, 10) T[-1.8, ];  // truncated normal
  k_culmeso     ~ normal(0, 0.25);
  b_culmeso     ~ beta(2, 5);
  sigma_scaledRI_cul     ~ cauchy(0, 0.1);
  sigma_scaledRI_meso    ~ cauchy(0, 0.1);

  // Logistic means using inv_logit for elementwise operations
  // vector[N_cul] mu_scaledRI_cul = (1 - b_culmeso) ./ (1 + exp(-k_culmeso * (t_cul - t0_culmeso))) + b_culmeso;
  // vector[N_meso] mu_scaledRI_meso = (1 - b_culmeso) ./ (1 + exp(-k_culmeso * (t_meso - t0_culmeso))) + b_culmeso;

  vector[N_cul] mu_scaledRI_cul = (1 - b_culmeso) * inv_logit(k_culmeso * (t_cul - t0_culmeso)) + b_culmeso;
  vector[N_meso] mu_scaledRI_meso = (1 - b_culmeso) * inv_logit(k_culmeso * (t_meso - t0_culmeso)) + b_culmeso;

  // Likelihoods
  scaledRI_cul    ~ normal(mu_scaledRI_cul, sigma_scaledRI_cul);
  scaledRI_meso   ~ normal(mu_scaledRI_meso, sigma_scaledRI_meso);

}

generated quantities {
  real<lower=0> sigma_scaledRI_culmeso;

  sigma_scaledRI_culmeso = sqrt(
    (N_cul * square(sigma_scaledRI_cul) + N_meso * square(sigma_scaledRI_meso)) 
    / (N_cul + N_meso)
  );
}


