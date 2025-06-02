data {
  int<lower=1> N;
  vector[N] scaledRI;
  vector[N] prior_mu_t;
  real<lower=0> prior_sigma_t;

  // Prior means
  real mu_t0;
  real mu_k;
  real mu_b;
  real mu_sigma_scaledRI;

  // Prior stds
  real<lower=0> std_t0;
  real<lower=0> std_k;
  real<lower=0> std_b;
  real<lower=0> std_sigma_scaledRI;

  // Optional predictors
  vector[N] gdgt23ratio;
  real mu_beta0_gdgt23ratio;
  real<lower=0> std_beta0_gdgt23ratio;
  int<lower=0, upper=1> use_gdgt23ratio;

  vector[N] no3;
  real mu_beta0_no3;
  real<lower=0> std_beta0_no3;
  int<lower=0, upper=1> use_no3;
}

parameters {
  vector<lower=-1.8>[N] t_est;

  real t0;
  real<lower=0> k;
  real<lower=0, upper=1> b;
  real<lower=0> sigma_scaledRI;

  real beta0_gdgt23ratio;
  real beta0_no3;
}

model {
  vector[N] mu_scaledRI;

  // Priors from ensemble
  t0 ~ normal(mu_t0, std_t0);
  k  ~ normal(mu_k, std_k);
  b  ~ normal(mu_b, std_b);
  sigma_scaledRI ~ normal(mu_sigma_scaledRI, std_sigma_scaledRI);

  if (use_gdgt23ratio == 1)
    beta0_gdgt23ratio ~ normal(mu_beta0_gdgt23ratio, std_beta0_gdgt23ratio);
  else
    beta0_gdgt23ratio ~ normal(0, 0.1); // tight prior near 0

  if (use_no3 == 1)
    beta0_no3 ~ normal(mu_beta0_no3, std_beta0_no3);
  else
    beta0_no3 ~ normal(0, 0.1);

  // Inverse temperature prior
  t_est ~ normal(prior_mu_t, prior_sigma_t);

  // Likelihood
  mu_scaledRI = (1 - b) * inv_logit(k * (t_est - t0)) + b;
  if (use_gdgt23ratio == 1)
    mu_scaledRI += beta0_gdgt23ratio * gdgt23ratio;
  if (use_no3 == 1)
    mu_scaledRI += beta0_no3 * no3;

  scaledRI ~ normal(mu_scaledRI, sigma_scaledRI);
}
