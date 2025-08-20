// invT_logistic_fixed_univ_marginal.stan

data {
  int<lower=1> N;
  int<lower=1> M;
  vector[N] scaledRI;
  vector[N] prior_mu_t;
  real prior_sigma_t;

  vector[M] t0;
  vector[M] k;
  vector[M] b;
  vector[M] sigma_scaledRI;
}

parameters {
  vector[N] t_est;
}

model {
  t_est ~ normal(prior_mu_t, prior_sigma_t);

  for (n in 1:N) {
    vector[M] lp;
    for (m in 1:M) {
      real mu = b[m] + (1 - b[m]) / (1 + exp(-k[m] * (t_est[n] - t0[m])));
      lp[m] = normal_lpdf(scaledRI[n] | mu, sigma_scaledRI[m]);
    }
    target += log_sum_exp(lp) - log(M);
  }
}
