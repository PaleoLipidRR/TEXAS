data {
  int<lower=1> N;
  vector[N] x;
  vector[N] y;
  vector[N] x2; // gdgt23ratio as a predictor
  
  real X0_MEAN;  // Mean of x0 posterior
  real X0_STD;   // Standard deviation of x0 posterior
  
  real K_MEAN;   // Mean of k posterior
  real K_STD;    // Standard deviation of k posterior

  real B_MEAN;   // Mean of b posterior
  real B_STD;    // Standard deviation of b posterior
}
parameters {
  real alpha;  // Overall y-intercept
  real x0;
  real<lower=0> k;
  real<lower=0, upper=1> b;
  real beta_x2;  // Coefficient for x2
  real<lower=0> sigma;
}
model {
  // Informative priors from culture+mesocosm posteriors
  alpha ~ normal(0, 1);  // General intercept for y
  x0 ~ normal(X0_MEAN, X0_STD);
  k ~ normal(K_MEAN, K_STD);
  b ~ normal(B_MEAN, B_STD);
  beta_x2 ~ normal(0, 1);  // Prior for x2 coefficient
  sigma ~ normal(0, 1);
  
  // Logistic function with an added linear effect from x2
  y ~ normal(alpha + ((1 - b) ./ (1 + exp(-k * (x - x0))) + b) + beta_x2 * x2, sigma);
}
