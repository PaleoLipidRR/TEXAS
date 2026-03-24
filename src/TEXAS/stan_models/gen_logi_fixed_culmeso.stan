// joint_culture_meso_generalized_logistic.stan
data {
  int<lower=1> N_cul;
  vector[N_cul] t_cul;
  vector[N_cul] proxyObs_cul;

  int<lower=1> N_meso;
  vector[N_meso] t_meso;
  vector[N_meso] proxyObs_meso;
}

parameters {
  real<lower=-1.8> t0_culmeso;        // Center of the curve (NOT necessarily inflection)
  real<lower=0>    k_culmeso;             // Growth rate (B)
  real<lower=0>    Q_culmeso;             // Q: curve-start factor
  real<lower=0.1>  v_culmeso;             // Shape (nu); >0, often >0.1 to avoid numerical issues
  real<lower=0>    b_culmeso;             // Lower asymptote (A)

  real<lower=0> sigma_proxyObs_cul;
  real<lower=0> sigma_proxyObs_meso;
}

model {
  // Priors
  t0_culmeso ~ normal(30, 10) T[-1.8, ];
  k_culmeso      ~ normal(0, 0.5) T[0, ];  // reverted - k is unbounded above in gen logistic
  Q_culmeso      ~ normal(1, 30) T[0.1, ]; 
  v_culmeso      ~ normal(1, 20) T[0.1, ]; 
  b_culmeso      ~ beta(2, 5);
  sigma_proxyObs_cul  ~ normal(0.01, 0.1);
  sigma_proxyObs_meso ~ normal(0.01, 0.1);

  // Generalized logistic mean vectors
  vector[N_cul] mu_proxyObs_cul = b_culmeso + (1 - b_culmeso)
    ./ pow(1 + Q_culmeso * exp(-k_culmeso * (t_cul - t0_culmeso)), 1 / v_culmeso);
  vector[N_meso] mu_proxyObs_meso = b_culmeso + (1 - b_culmeso)
    ./ pow(1 + Q_culmeso * exp(-k_culmeso * (t_meso - t0_culmeso)), 1 / v_culmeso);

  // Likelihood
  proxyObs_cul  ~ normal(mu_proxyObs_cul, sigma_proxyObs_cul);
  proxyObs_meso ~ normal(mu_proxyObs_meso, sigma_proxyObs_meso);
}