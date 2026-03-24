// invT_logistic_fixed_univ_unconstrained.stan
data {
  int<lower=1> N;       
  int<lower=1> M;       

  vector[N] proxyObs;    
  vector[N] prior_mu_t;
  real prior_sigma_t;

  vector[M] t0;
  vector[M] k;
  vector[M] b;
  vector[M] v;
  vector[M] sigma_proxyObs;
}

parameters {
  matrix[N,M] t_est;  // estimated temperatures
}

model {
  vector[N] mu_proxyObs;

  for (m in 1:M) {
    vector[N] t_col = t_est[:, m];

    t_col ~ normal(prior_mu_t, prior_sigma_t);

    mu_proxyObs = b[m] + elt_divide(1 - b[m],
                     pow(1 + exp(-k[m] * (t_col - t0[m])), 1 / v[m]));

    proxyObs ~ normal(mu_proxyObs, sigma_proxyObs[m]);
  }
}