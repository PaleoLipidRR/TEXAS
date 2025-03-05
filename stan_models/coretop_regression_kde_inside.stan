data {
  int<lower=1> N;            // Number of core-top observations
  vector[N] x;               // Predictor variable (e.g., Temperature)
  vector[N] y;               // Observed values (e.g., scaled RI)

  int<lower=1> M;            // Number of posterior draws from first layer
  vector[M] x0_post;         // Posterior draws for x0
  vector[M] k_post;          // Posterior draws for k
  vector[M] b_post;          // Posterior draws for b
}

transformed data {
  // Use categorical sampling to get integer indices from posterior samples
  int sample_idx_x0 = categorical_rng(rep_vector(1.0 / M, M));
  int sample_idx_k = categorical_rng(rep_vector(1.0 / M, M));
  int sample_idx_b = categorical_rng(rep_vector(1.0 / M, M));
}

parameters {
  real x0;                   // Inflection point (to be estimated)
  real<lower=0> k;           // Growth rate (to be estimated)
  real<lower=0, upper=1> b;  // Lower asymptote (to be estimated)
  real<lower=0> sigma;       // Noise term (to be estimated)
}

model {
  // Use KDE priors by sampling from first-layer posterior draws
  x0 ~ normal(x0_post[sample_idx_x0], 0.1);
  k ~ normal(k_post[sample_idx_k], 0.1);
  b ~ normal(b_post[sample_idx_b], 0.05);
  sigma ~ normal(0.05, 0.1) T[0, ]; //

  // Logistic function with fixed upper asymptote at 1
  vector[N] logistic_part;
  logistic_part = (1 - b) ./ (1 + exp(-k * (x - x0))) + b;
  y ~ normal(logistic_part, sigma);
}
