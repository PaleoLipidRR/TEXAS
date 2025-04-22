// joint_culture_meso_three.stan
data {
  // first dataset
  int<lower=1> N1;
  vector[N1] x1;
  vector[N1] y1;

  // second dataset
  int<lower=1> N2;
  vector[N2] x2;
  vector[N2] y2;

  // third dataset
  int<lower=1> N3;
  vector[N3] x3;
  vector[N3] y3;
}

parameters {
  real<lower=-4>         x0;      // inflection point
  real<lower=0>          k;       // steepness
  real<lower=0,upper=1>  b;       // lower asymptote

  real<lower=0> sigma1;          // noise for dataset 1
  real<lower=0> sigma2;          // noise for dataset 2
  real<lower=0> sigma3;          // noise for dataset 3
}

model {
  // Priors
  x0     ~ normal(20, 20) T[-4, ];
  k      ~ normal(0, 0.25);
  b      ~ beta(2, 5);
  sigma1 ~ normal(0.01, 0.1) T[0.01, ];
  sigma2 ~ normal(0.01, 0.1) T[0.01, ];
  sigma3 ~ normal(0.01, 0.1) T[0.01, ];

  // Logistic‐curve means (vectorized)
  vector[N1] mu1 = (1 - b) * inv_logit(k * (x1 - x0)) + b;
  vector[N2] mu2 = (1 - b) * inv_logit(k * (x2 - x0)) + b;
  vector[N3] mu3 = (1 - b) * inv_logit(k * (x3 - x0)) + b;

  // Likelihoods
  y1 ~ normal(mu1, sigma1);
  y2 ~ normal(mu2, sigma2);
  y3 ~ normal(mu3, sigma3);
}

generated quantities {
  // ratios for diagnostics
  real sigma2_sigma1 = sigma2 / sigma1;
  real sigma3_sigma1 = sigma3 / sigma1;
}
