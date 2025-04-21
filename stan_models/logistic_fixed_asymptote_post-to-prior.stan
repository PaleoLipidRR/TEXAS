data {
  int<lower=1> N;       // Number of observations
  vector[N] x;          // Predictor variable
  vector[N] y;          // Observed values (continuous)
}
parameters {
  real<lower=-4> x0;    // Inflection point (fixed lower bound)
  real<lower=0> k;      // Rate of change (steepness)
  real<lower=0, upper=1> b;  // Lower asymptote (bounded)
  real<lower=0> sigma;  // Noise (error term)
}
model {
  // Priors (adjust as needed)
  x0 ~ normal(20, 20) T[-4, ];  // Truncated normal
  k ~ normal(0, 0.25);
  b ~ beta(2, 5);       // Lower bound (0,1)
  sigma ~ normal(0.01, 0.1) T[0.01, ]; // 

  // Logistic function with fixed upper asymptote at 1
  vector[N] logistic_part;
  logistic_part = (1 - b) ./ (1 + exp(-k * (x - x0))) + b;
  y ~ normal(logistic_part, sigma);
}

