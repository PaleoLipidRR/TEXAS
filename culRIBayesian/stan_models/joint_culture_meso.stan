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
}

parameters {
  real<lower=-1.8>       t0_culmeso;      // inflection point
  real<lower=0>          k_culmeso;       // steepness
  real<lower=0,upper=1>  b_culmeso;       // lower asymptote
  
  real<lower=0> sigma_cul;           // noise for dataset 1
  real<lower=0> sigma_meso;           // noise for dataset 2
}

model {
  // Priors
  t0_culmeso    ~ normal(30, 10) T[-1.8, ];  // truncated normal
  k_culmeso     ~ normal(0, 0.25);
  b_culmeso     ~ beta(2, 5);
  sigma_cul     ~ normal(0.01, 0.1) T[0.01, ];
  sigma_meso    ~ normal(0.01, 0.1) T[0.01, ];

  // Logistic means using inv_logit for elementwise operations
  // vector[N_cul] mu_cul = (1 - b_culmeso) ./ (1 + exp(-k_culmeso * (t_cul - t0_culmeso))) + b_culmeso;
  // vector[N_meso] mu_meso = (1 - b_culmeso) ./ (1 + exp(-k_culmeso * (t_meso - t0_culmeso))) + b_culmeso;


  vector[N_cul] mu_cul = (1 - b_culmeso) * inv_logit(k_culmeso * (t_cul - t0_culmeso)) + b_culmeso;
  vector[N_meso] mu_meso = (1 - b_culmeso) * inv_logit(k_culmeso * (t_meso - t0_culmeso)) + b_culmeso;

  // Likelihoods
  scaledRI_cul    ~ normal(mu_cul, sigma_cul);
  scaledRI_meso   ~ normal(mu_meso, sigma_meso);

}

