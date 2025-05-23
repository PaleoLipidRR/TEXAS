// invT_logistic_fixed_univ.stan
data {
  int<lower=1> N_downcore;       
  vector[N_downcore] scaledRI_downcore;    
  vector[N_downcore] prior_mu_t;
  real prior_sigma_t;

  int<lower=1> M;
  vector[M] t0;
  vector[M] k;
  vector[M] b;
  vector[M] sigma_scaledRI;
}

parameters {
  matrix<lower=-1.8>[N_downcore,M] t_est;
}

model {
  vector[N_downcore] mu_scaledRI;
  for (m in 1:M) {
    t_est[:,m] ~ normal(prior_mu_t, prior_sigma_t);

    mu_scaledRI = (1 - b[m]) * inv_logit(k[m] * (t_est[:,m] - t0[m])) + b[m];

    scaledRI_downcore ~ normal(mu_scaledRI, sigma_scaledRI[m]);
  }
}