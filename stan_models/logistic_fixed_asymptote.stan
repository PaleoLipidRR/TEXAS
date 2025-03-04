data {
  int<lower=1> N;       // Number of observations
  vector[N] x;          // Predictor variable
  vector[N] y;          // Observed values (continuous)
}
parameters {
  real x0;             // Inflection point
  real<lower=0> k;     // Growth rate (steepness)
  real<lower=0, upper=1> b;  // Lower asymptote (bounded)
  real<lower=0> sigma; // Noise (error term)
}
model {
  // Priors (adjust as needed)
  x0 ~ normal(0, 50);
  k ~ normal(0, 1);
  b ~ beta(2, 2); // Lower bound (0,1)
  sigma ~ normal(0, 1);

  // Logistic function with fixed upper asymptote at 1
  y ~ normal((1 - b) ./ (1 + exp(-k * (x - x0))) + b, sigma);
}
