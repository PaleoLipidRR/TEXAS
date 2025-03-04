data {
  int<lower=1> N;
  vector[N] x;
  vector[N] y;
  
  real X0_MEAN;  // Mean of x0 posterior
  real X0_STD;   // Standard deviation of x0 posterior
  
  real K_MEAN;   // Mean of k posterior
  real K_STD;    // Standard deviation of k posterior

  real B_MEAN;   // Mean of b posterior
  real B_STD;    // Standard deviation of b posterior
}
parameters {
  real x0;
  real<lower=0> k;
  real<lower=0, upper=1> b;
  real<lower=0> sigma;
}
model {
  // Informative priors from culture+mesocosm posteriors
  x0 ~ normal(X0_MEAN, X0_STD);
  k ~ normal(K_MEAN, K_STD);
  b ~ normal(B_MEAN, B_STD);
  sigma ~ normal(0, 1);
  
  // Logistic function with fixed upper asymptote at 1
  y ~ normal((1 - b) ./ (1 + exp(-k * (x - x0))) + b, sigma);
}
