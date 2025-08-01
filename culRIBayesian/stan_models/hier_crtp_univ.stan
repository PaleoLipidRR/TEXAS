// --------------------------------------------------------------  // 5. Priors for coretop "logistic" parameters
  t0_crtp  ~ normal(t0_culmeso, sigma_t0_culmeso);
  k_crtp   ~ normal(k_culmeso, sigma_k_culmeso);
  b_crtp   ~ normal(b_culmeso, sigma_b_culmeso);

  // 5.1. Prior for coretop observation noise
  sigma_scaledRI_crtp ~ normal(0.01, 0.1);

  // 6. Likelihood for coretop uses mu_scaledRI_crtp from transformed parametersa {
  int<lower=1> N_cul;
  vector[N_cul] t_cul;
  vector[N_cul] scaledRI_cul;

  int<lower=1> N_meso;
  vector[N_meso] t_meso;
  vector[N_meso] scaledRI_meso;

  int<lower=1> N_crtp;
  vector[N_crtp] t_crtp;
  vector[N_crtp] scaledRI_crtp;
}

parameters {
  // shared logistic parameters for culture+mesocosm
  real<lower=-1.8>       t0_culmeso;
  real<lower=0,upper=1>  k_culmeso;
  real<lower=0,upper=1>  b_culmeso;

  // logistic parameters for coretop
  real<lower=-1.8>       t0_crtp;
  real<lower=0,upper=1>  k_crtp;
  real<lower=0,upper=1>  b_crtp;

  // hierarchical scale parameters (hyperpriors)
  real<lower=0>          sigma_t0_culmeso;
  real<lower=0>          sigma_k_culmeso;
  real<lower=0>          sigma_b_culmeso;

  // observation noise
  real<lower=0>          sigma_scaledRI_cul;
  real<lower=0>          sigma_scaledRI_meso;
  real<lower=0>          sigma_scaledRI_crtp;
}


// ---------------------------------------------------------------
model {
  // 1. Priors for culture+mesocosm
  t0_culmeso    ~ normal(30, 10) T[-1.8, ];
  k_culmeso     ~ beta(2, 5);
  b_culmeso     ~ beta(2, 5);

  // 2. Hyperpriors for scales (more informative to allow reasonable hierarchical structure)
  sigma_t0_culmeso   ~ normal(0, 5);  // allow more variation for temperature
  sigma_k_culmeso    ~ normal(0, 0.2);  // k is bounded [0,1], so smaller scale
  sigma_b_culmeso    ~ normal(0, 0.2);  // b is bounded [0,1], so smaller scale

  // 3. Priors for observation noise
  sigma_scaledRI_cul  ~ normal(0.01, 0.1);
  sigma_scaledRI_meso ~ normal(0.01, 0.1);

  // 4. Likelihoods for culture and mesocosm
  {
    vector[N_cul]  mu_scaledRI_cul  = 
      (1 - b_culmeso) * inv_logit(k_culmeso * (t_cul - t0_culmeso)) + b_culmeso;
    vector[N_meso] mu_scaledRI_meso = 
      (1 - b_culmeso) * inv_logit(k_culmeso * (t_meso - t0_culmeso)) + b_culmeso;

    scaledRI_cul  ~ normal(mu_scaledRI_cul,  sigma_scaledRI_cul);
    scaledRI_meso ~ normal(mu_scaledRI_meso, sigma_scaledRI_meso);
  }

  // 5. Priors for coretop “logistic” parameters
  t0_crtp  ~ normal(t0_culmeso, sigma_t0_culmeso);
  k_crtp   ~ normal(k_culmeso, sigma_k_culmeso);
  b_crtp   ~ normal(b_culmeso, sigma_b_culmeso);

  // 6. Likelihood for coretop uses mu_scaledRI_crtp from transformed parameters
  vector[N_crtp] mu_scaledRI_crtp;
  for (i in 1:N_crtp) {
    mu_scaledRI_crtp[i] = (1 - b_crtp)
                       * inv_logit(k_crtp * (t_crtp[i] - t0_crtp))
                       + b_crtp;
  }
  scaledRI_crtp ~ normal(mu_scaledRI_crtp, sigma_scaledRI_crtp);
}

