data {
  int<lower=1> N;
  vector[N] scaledRI;
  vector[N] prior_mu_t;
  real<lower=0> prior_sigma_t;

  // Ensemble priors for forward-model parameters
  real mu_t0;
  real<lower=0> std_t0;
  real mu_k;
  real<lower=0> std_k;
  real mu_b;
  real<lower=0> std_b;
  real mu_v;
  real<lower=0> std_v;
  real mu_Q;
  real<lower=0> std_Q;
  real mu_sigma_scaledRI;
  real<lower=0> std_sigma_scaledRI;
}

parameters {
  vector<lower=-1.8>[N] t_est;

  real<lower=-5,upper=100> t0;
  real<lower=0> k;
  real<lower=0,upper=1> b;
  real<lower=0> v;
  real<lower=0> Q;
  real<lower=0> sigma_scaledRI;
}

model {

  // Hyperpriors from ensemble
  t0             ~ normal(mu_t0, std_t0);
  k              ~ normal(mu_k, std_k);
  b              ~ normal(mu_b, std_b);
  v              ~ normal(mu_v, std_v);
  Q              ~ normal(mu_Q, std_Q);
  sigma_scaledRI ~ normal(mu_sigma_scaledRI, std_sigma_scaledRI);

  vector[N] mu_scaledRI;

  // Prior for inverse temperature
  t_est ~ normal(prior_mu_t, prior_sigma_t);

  // Forward: generalized logistic (fixed upper=1)
  mu_scaledRI = b + ((1 - b) / pow(1 + Q * exp(-k * (t_est - t0)), 1.0 / v));

  // Likelihood
  scaledRI ~ normal(mu_scaledRI, sigma_scaledRI);
}
