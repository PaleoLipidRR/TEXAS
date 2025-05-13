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
    vector[N3] z3;           // gdgt23ratio
    vector[N3] aa3;          // thermocline-integrated nitrate
}

parameters {
    // shared logistic parameters for culture+mesocosm
    real<lower=-1.8>     x0;    // inflection point
    real<lower=0,upper=1> k;    // steepness
    real<lower=0,upper=1> b;    // lower asymptote (on [0,1] via beta prior)

    // logistic parameters for coretop
    real<lower=-1.8>     x0_3;
    real<lower=0,upper=1> k_3;
    real<lower=0,upper=1> b_3;
    real<lower=-1,upper=0> beta0_z3;
    real<lower=-1,upper=0> beta0_aa3;

    // hierarchical scale parameters (hyperpriors)
    real<lower=0>        sigma_x0;
    real<lower=0>        sigma_k;
    real<lower=0>        sigma_b;

    // observation noise
    real<lower=0>        sigma1;  // culture noise
    real<lower=0>        sigma2;  // mesocosm noise
    real<lower=0>        sigma3;  // coretop noise
}


model {
    // 1 Priors for shared parameters for culture+mesocosm
    x0    ~ normal(30, 10) T[-1.8, ];  // truncated normal
    k     ~ beta(2, 5);
    b     ~ beta(2, 5);

    // 2 Hyperpriors for scales (weakly informative)
    sigma_x0     ~ cauchy(0, 1);
    sigma_k      ~ cauchy(0, 1);
    sigma_b      ~ cauchy(0, 1);

    // 3 Priors for observation noise
    sigma1 ~ normal(0.01, 0.1);
    sigma2 ~ normal(0.01, 0.1);

    // 4 Likelihoods for culture and mesocosm
    vector[N1] mu1 = (1 - b)   * inv_logit(k   * (x1 - x0))   + b;
    vector[N2] mu2 = (1 - b)   * inv_logit(k   * (x2 - x0))   + b;

    y1 ~ normal(mu1, sigma1);
    y2 ~ normal(mu2, sigma2);
    
    // 5 Coretop priors 
    x0_3  ~ normal(x0, sigma_x0);
    k_3   ~ normal(k, sigma_k);
    b_3   ~ normal(b, sigma_b);
    beta0_z3 ~ normal(0, 0.05)  T[-1,0];
    beta0_aa3 ~ normal(0, 0.05)  T[-1,0];

    // 6 Likelihoods for coretops

    vector[N3] mu3;
    for (i in 1:N3) {
        // base logistic + z3 effect
        real base3 = (1 - b_3) 
                    * inv_logit(k_3 * (x3[i] - x0_3)) 
                    + b_3 
                    + beta0_z3 * z3[i];

        if (aa3[i] <= 2.7) {
        // include aa3 effect only when aa3 ≤ 2.7
        mu3[i] = base3 + beta0_aa3 * log10(aa3[i]);
        } 
        
        else {
        // drop aa3 effect for high aa3 values
        mu3[i] = base3;
        }
    }

    sigma3 ~ normal(0.01, 0.1);

    y3 ~ normal(mu3, sigma3);
}

// Generated quantities for diagnostic ratios
generated quantities {
  real sigma2_sigma1 = sigma2 / sigma1;
  real sigma3_sigma1 = sigma3 / sigma1;
}