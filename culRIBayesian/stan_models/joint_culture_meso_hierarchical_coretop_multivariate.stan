data {
    // culture data
    int<lower=1> N_cul;
    vector[N_cul] t_cul;
    vector[N_cul] scaledRI_cul;

    // mesocosm data
    int<lower=1> N_meso;
    vector[N_meso] t_meso;
    vector[N_meso] scaledRI_meso;

    // coretop
    int<lower=1> N_coretop;
    vector[N_coretop] t_coretop;
    vector[N_coretop] scaledRI_coretop;

    // optional predictors
    vector[N_coretop] gdgt23ratio_coretop;
    vector[N_coretop] no3_coretop;
}

parameters {
    // shared logistic parameters for culture+mesocosm
    real<lower=-1.8>     t0_culmeso;    // inflection point
    real<lower=0,upper=1> k_culmeso;    // steepness
    real<lower=0,upper=1> b_culmeso;    // lower asymptote (on [0,1] via beta prior)

    // logistic parameters for coretop
    real<lower=-1.8>     t0_coretop;
    real<lower=0,upper=1> k_coretop;
    real<lower=0,upper=1> b_coretop;
    real<lower=-1,upper=0> beta0_gdgt23ratio_coretop;
    real<lower=-1,upper=0> beta0_no3_coretop;

    // hierarchical scale parameters (hyperpriors)
    real<lower=0>        sigma_t0_culmeso;
    real<lower=0>        sigma_k_culmeso;
    real<lower=0>        sigma_b_culmeso;

    // observation noise
    real<lower=0>        sigma_cul;  // culture noise
    real<lower=0>        sigma_meso;  // mesocosm noise
    real<lower=0>        sigma_coretop;  // coretop noise
}


model {
    // 1 Priors for shared parameters for culture+mesocosm
    t0_culmeso    ~ normal(30, 10) T[-1.8, ];  // truncated normal
    k_culmeso     ~ beta(2, 5);
    b_culmeso     ~ beta(2, 5);

    // 2 Hyperpriors for scales (weakly informative)
    sigma_t0_culmeso     ~ cauchy(0, 1);
    sigma_k_culmeso      ~ cauchy(0, 1);
    sigma_b_culmeso      ~ cauchy(0, 1);

    // 3 Priors for observation noise
    sigma_cul ~ normal(0.01, 0.1);
    sigma_meso ~ normal(0.01, 0.1);

    // 4 Likelihoods for culture and mesocosm
    vector[N_cul] mu_cul = (1 - b_culmeso)   * inv_logit(k_culmeso   * (t_cul - t0_culmeso))   + b_culmeso;
    vector[N_meso] mu_meso = (1 - b_culmeso)   * inv_logit(k_culmeso   * (t_meso - t0_culmeso))   + b_culmeso;

    scaledRI_cul ~ normal(mu_cul, sigma_cul);
    scaledRI_meso ~ normal(mu_meso, sigma_meso);
    
    // 5 Coretop priors 
    t0_coretop  ~ normal(t0_culmeso, sigma_t0_culmeso);
    k_coretop   ~ normal(k_culmeso, sigma_k_culmeso);
    b_coretop   ~ normal(b_culmeso, sigma_b_culmeso);
    beta0_gdgt23ratio_coretop ~ normal(0, 0.05)  T[-1,0];
    beta0_no3_coretop ~ normal(0, 0.05)  T[-1,0];

    // 6 Likelihoods for coretops

    vector[N_coretop] mu_coretop;
    for (i in 1:N_coretop) {
        // base logistic + gdgt23ratio_coretop effect
        real base_coretop = (1 - b_coretop) 
                    * inv_logit(k_coretop * (t_coretop[i] - t0_coretop)) 
                    + b_coretop 
                    + beta0_gdgt23ratio_coretop * gdgt23ratio_coretop[i];

        if (no3_coretop[i] <= 2.7) {
        // include no3_coretop effect only when no3_coretop ≤ 2.7
        mu_coretop[i] = base_coretop + beta0_no3_coretop * log10(no3_coretop[i]);
        } 
        
        else {
        // drop no3_coretop effect for high no3_coretop values
        mu_coretop[i] = base_coretop;
        }
    }

    sigma_coretop ~ normal(0.01, 0.1);
    scaledRI_coretop ~ normal(mu_coretop, sigma_coretop);
}
