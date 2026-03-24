// invT_logistic_fixed_univ_unconstrained.stan
data {
  int<lower=1> N;       
  vector[N] proxyObs;    
  vector[N] prior_mu_t;
  real prior_sigma_t;

  int<lower=1> M;
  vector[M] t0;
  vector[M] k;
  vector[M] b;
  vector[M] sigma_proxyObs;
}

parameters {
  matrix[N,M] t_est;
}

model {
  vector[N] mu_proxyObs;
  for (m in 1:M) {
    t_est[:,m] ~ normal(prior_mu_t, prior_sigma_t);

    mu_proxyObs = (1 - b[m]) * inv_logit(k[m] * (t_est[:,m] - t0[m])) + b[m];

    proxyObs ~ normal(mu_proxyObs, sigma_proxyObs[m]);
  }
}