data {
  int<lower=1> N;
  vector[N] scaledRI;
  vector[N] prior_mu_t;
  real prior_sigma_t;

  // prior means
  real mu_t0;
  real mu_k;
  real mu_b;
  real mu_sigma_scaledRI;

  // prior stds
  real std_t0;
  real std_k;
  real std_b;
  real std_sigma_scaledRI;
}

parameters {
  vector<lower=-1.8>[N] t_est;

  real<lower=-5, upper=100> t0;
  real<lower=0> k;
  real<lower=0, upper=1> b;
  real<lower=0> sigma_scaledRI;
}

model {
  // Hyperpriors (informative priors from ensemble stats)
  t0 ~ normal(mu_t0, std_t0);
  k  ~ normal(mu_k, std_k);
  b  ~ normal(mu_b, std_b);
  sigma_scaledRI ~ normal(mu_sigma_scaledRI, std_sigma_scaledRI);

  vector[N] mu_scaledRI;
  t_est ~ normal(prior_mu_t, prior_sigma_t);
  mu_scaledRI = (1 - b) * inv_logit(k * (t_est - t0)) + b;
  scaledRI ~ normal(mu_scaledRI, sigma_scaledRI);
}
