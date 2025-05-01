// joint_culture_meso_hierarchical_coretop_T-only.stan
// Hierarchical logistic model with logit‐reparameterization for b and b_3
//
// Extended comments:
//
// 1. Model overview:
//    - Datasets 1 & 2 (culture & mesocosm) share logistic parameters x0, k, and b.
//    - Dataset 3 (coretop) borrows strength via hierarchical priors centered on those shared parameters.
//    - We model proxy (scaled ring index) y as a logistic function of temperature x:
//        y ~ (1 - b) * inv_logit(k * (x - x0)) + b
//    - Hierarchical structure enables partial pooling and principled uncertainty propagation.
//
// 2. Logit reparameterization for b terms:
//    - Declare logit_b on the real line; transform to b = inv_logit(logit_b) ∈ (0,1).
//    - Place Beta(2,5) prior on b with Jacobian correction for the logit transform:
//        target += beta_lpdf(b | 2, 5) + log(b * (1 - b));
//    - Repeat for coretop logit_b_3 to avoid truncation and sampling pathologies.
//
// 3. Non-centered parametrization for hierarchical deviations:
//    - z_x0_3, z_k_3, z_logit_b_3 ~ Normal(0,1) are standardized offsets.
//    - Hyperparameters sigma_x0, sigma_k, sigma_logit_b control the scale of deviations.
//    - Coretop parameters: shared + scale * z, reducing funnel effects.
//
// 4. Priors and hyperpriors:
//    - x0       ~ Normal(30,10) truncated below -1.8: reflects plausible inflection range.
//    - k        ~ Normal(0,0.25): steepness around zero with moderate dispersion.
//    - b        ~ Beta(2,5): lower asymptote favoring small values.
//    - sigma_*  ~ Half-normal(0,1): weakly informative group‐level scales.
//    - sigma1-3 ~ Half-normal(0,0.1): observation noise across datasets.
//
// 5. Generated quantities:
//    - sigma2_sigma1 and sigma3_sigma1: ratios of noise SDs for diagnostics.
//
// Usage notes:
//    * If sampling warnings persist, consider adapt_delta=0.95 and max_treedepth=12.
//    * Provide initial values near expected ranges (e.g. logit_b=0 for b≈0.5).


data {
  int<lower=1> N1;         // number of culture observations
  vector[N1] x1;           // temperatures
  vector[N1] y1;           // scaled ring index

  int<lower=1> N2;         // number of mesocosm observations
  vector[N2] x2;
  vector[N2] y2;

  int<lower=1> N3;         // number of coretop observations
  vector[N3] x3;
  vector[N3] y3;
}

parameters {
  // shared logistic parameters for culture+mesocosm
  real<lower=-1.8>        x0;          // inflection point (unbounded)
  real<lower=1e-6>        k;           // steepness (unbounded)
  real        logit_b;     // logit of lower asymptote

  // hyperparameters controlling coretop deviation scales
  real<lower=1e-6> sigma_x0;
  real<lower=1e-6> sigma_k;
  real<lower=1e-6> sigma_logit_b;

  // non‐centered offsets for coretop group
  real<lower=-1.8> z_x0_3;
  real<lower=1e-6> z_k_3;
  real z_logit_b_3;

  // observation noise
  real<lower=1e-6> sigma1;    // culture noise
  real<lower=1e-6> sigma2;    // mesocosm noise
  real<lower=1e-6> sigma3;    // coretop noise
}

transformed parameters {
  // transform logit_b to b ∈ (0,1)
  real<lower=0,upper=1> b = inv_logit(logit_b);

  // reconstruct coretop parameters with non‐centered form
  real<lower=-1.8>        x0_3      = x0 + sigma_x0     * z_x0_3;       // inflection for coretop
  real<lower=1e-6>        k_3       = k  + sigma_k      * z_k_3;        // steepness for coretop
  real        logit_b_3 = logit_b + sigma_logit_b * z_logit_b_3;
  real<lower=0,upper=1> b_3 = inv_logit(logit_b_3);          // asymptote for coretop
}

model {
  // 1 Priors for shared parameters
  x0    ~ normal(30, 10) T[-1.8, ];  // truncated normal
  k     ~ normal(0, 0.25);

  // Beta prior on b with Jacobian term for logit
  target += beta_lpdf(b | 2, 5) + log(b * (1 - b));

  // 2 Hyperpriors for scales (weakly informative)
  sigma_x0     ~ normal(0, 1);
  sigma_k      ~ normal(0, 1);
  sigma_logit_b ~ normal(0, 0.2);

  // 3 Standard normal for non‐centered offsets
  z_x0_3      ~ normal(0, 1);
  z_k_3       ~ normal(0, 1);
  z_logit_b_3 ~ normal(0, 1);

  // 4 Priors for observation noise
  sigma1 ~ normal(0.01, 0.1) T[1e-6, ];
  sigma2 ~ normal(0.01, 0.1) T[1e-6, ];
  sigma3 ~ normal(0.01, 0.1) T[1e-6, ];

  // 5 Likelihoods for each dataset
  vector[N1] mu1 = (1 - b)   * inv_logit(k   * (x1 - x0))   + b;
  vector[N2] mu2 = (1 - b)   * inv_logit(k   * (x2 - x0))   + b;
  vector[N3] mu3 = (1 - b_3) * inv_logit(k_3 * (x3 - x0_3)) + b_3;

  y1 ~ normal(mu1, sigma1) T[1e-6, ];
  y2 ~ normal(mu2, sigma2) T[1e-6, ];
  y3 ~ normal(mu3, sigma3) T[1e-6, ];
}

// Generated quantities for diagnostic ratios
generated quantities {
  real sigma2_sigma1 = sigma2 / sigma1;
  real sigma3_sigma1 = sigma3 / sigma1;
}
