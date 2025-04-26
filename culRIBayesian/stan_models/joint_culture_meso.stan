// joint_culture_meso.stan
data {
  // first dataset
  int<lower=1> N1;       
  vector[N1] x1;         
  vector[N1] y1;         

  // second dataset
  int<lower=1> N2;       
  vector[N2] x2;         
  vector[N2] y2;         
}

parameters {
  real<lower=-4>         x0;      // inflection point
  real<lower=0>          k;       // steepness
  real<lower=0,upper=1>  b;       // lower asymptote
  
  real<lower=0> sigma1;           // noise for dataset 1
  real<lower=0> sigma2;           // noise for dataset 2
}

model {
  // Priors
  x0     ~ normal(20, 20) T[-4, ];
  k      ~ normal(0, 0.25);
  b      ~ beta(2, 5);
  sigma1 ~ normal(0.01, 0.1) T[0.01, ];
  sigma2 ~ normal(0.01, 0.1) T[0.01, ];

  // Logistic means using inv_logit for elementwise operations
  // vector[N1] mu1 = (1 - b) ./ (1 + exp(-k * (x1 - x0))) + b;
  // vector[N2] mu2 = (1 - b) ./ (1 + exp(-k * (x2 - x0))) + b;

  // Solve
  // (1 - b) * inv_logit(z) + b  
  // = (1 - b) * (1 / (1 + exp(-z))) + b  
  // = (1 - b) / (1 + exp(-z))         + b

  vector[N1] mu1 = (1 - b) * inv_logit(k * (x1 - x0)) + b;
  vector[N2] mu2 = (1 - b) * inv_logit(k * (x2 - x0)) + b;

  // Likelihoods
  y1 ~ normal(mu1, sigma1);
  y2 ~ normal(mu2, sigma2);
}

generated quantities {
  real sigma_ratio = sigma2 / sigma1;
}
