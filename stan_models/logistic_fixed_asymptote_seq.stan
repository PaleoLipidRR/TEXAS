data {
  int<lower=1> N;       // Number of observations
  vector[N] x;          // Predictor variable
  vector[N] y;          // Observed values (continuous)
  real  p50_x0_culture_post; // x0 prior based on culture posterior
  real  std_x0_culture_post; //
  real  p50_k_culture_post; // k prior based on culture posterior
  real  std_k_culture_post; //
  real  p50_b_culture_post; // b prior based on culture posterior
  real  std_b_culture_post; //
  real  p50_sigma_culture_post; // sigma prior based on culture posterior
  real  std_sigma_culture_post; //  
}

transformed data {
  real sigma_prior_std = std_sigma_culture_post > 1e-6
                        ? std_sigma_culture_post
                        : 1e-6;
}

parameters {
  real<lower=-4> x0;    // Inflection point (fixed lower bound)
  real<lower=0> k;      // Rate of change (steepness)
  real<lower=0, upper=1> b;  // Lower asymptote (bounded)
  real<lower=0> sigma;  // Noise (error term)
}

model {
  // Priors (adjust as needed)
  x0 ~ normal(p50_x0_culture_post, std_x0_culture_post) T[-4, ];  // Truncated normal
  k ~ normal(p50_k_culture_post, std_k_culture_post);
  b ~ normal(p50_b_culture_post, std_b_culture_post);     
  sigma ~ normal(p50_sigma_culture_post, sigma_prior_std) T[0,];

  // Logistic function with fixed upper asymptote at 1
  vector[N] logistic_part;
  logistic_part = (1 - b) ./ (1 + exp(-k * (x - x0))) + b;
  y ~ normal(logistic_part, sigma);
}

