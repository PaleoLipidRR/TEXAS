// joint_culture_meso_coretop_multivariate.stan
data {
  // first dataset
  int<lower=1> N1;
  vector[N1] x1;
  vector[N1] y1;

  // second dataset
  int<lower=1> N2;
  vector[N2] x2;
  vector[N2] y2;

  // third dataset, now with an extra predictor z3
  int<lower=1>   N3;
  vector[N3]     x3;
  vector[N3]     y3;
  vector[N3]     z3;        // e.g. nutrient concentration or depth, etc.
}

parameters {
  real<lower=-4>        x0;      // shared inflection
  real<lower=0>         k;       // shared steepness
  real<lower=0,upper=1> b;       // shared lower asymptote

  real                  beta1; // intercept for dataset3 (coretop)
  real                  beta0;      // new slope for z3
  real<lower=0>         sigma1;  // noise DS1
  real<lower=0>         sigma2;  // noise DS2
  real<lower=0>         sigma3;  // noise DS3
}

model {
  // Priors
  x0     ~ normal(20, 20) T[-4, ];
  k      ~ normal(0, 0.25);
  b      ~ beta(2, 5);

  // prior on the linear term
  beta1     ~ normal(0, 0.3);
  beta0     ~ normal(0, 0.01);

  // noise priors
  sigma1 ~ normal(0.01, 0.1) T[0.01, ];
  sigma2 ~ normal(0.01, 0.1) T[0.01, ];
  sigma3 ~ normal(0.01, 0.1) T[0.01, ];

  // Logistic‐curve means (vectorized)
  vector[N1] mu1 = (1 - b) * inv_logit(k * (x1 - x0)) + b;
  vector[N2] mu2 = (1 - b) * inv_logit(k * (x2 - x0)) + b;

  // for dataset 3, add the linear term beta3 * z3
  vector[N3] mu3 = ((1 - b) * inv_logit(k * (x3 - x0)) + b)
                  + beta0 * z3
                  + beta1;

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
