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
    int<lower=1> N_crtp;
    vector[N_crtp] t_crtp;
    vector[N_crtp] scaledRI_crtp;

    // optional predictors
    vector[N_crtp] gdgt23ratio_crtp;
    int<lower=0, upper=1> use_gdgt23ratio;

    vector[N_crtp] no3_crtp;
    int<lower=0, upper=1> use_no3;
    real no3_cutoff;
}

parameters {
    // shared logistic parameters for culture+mesocosm
    real<lower=10, upper=50>    t0_culmeso;
    real<lower=0,upper=1>       k_culmeso;    // steepness
    real<lower=0,upper=1>       b_culmeso;    // lower asymptote (on [0,1] via beta prior)
    real<lower=0.01>            Q_culmeso;      // curve start factor (Q), must be > 0
    real<lower=0.1>             v_culmeso;      // shape/asymmetry (ν), must be > 0

    // logistic parameters for coretop
    real<lower=10, upper=50>    t0_crtp;            // center (not necessarily inflection point)
    real<lower=0,upper=1>       k_crtp;
    real<lower=0,upper=1>       b_crtp;
    real<lower=0.01>            Q_crtp;      // curve start factor (Q), must be > 0
    real<lower=0.1>             v_crtp;      // shape/asymmetry (ν), must be > 0
    
    real<lower=-1,upper=0> beta0_gdgt23ratio_crtp;
    real<lower=-1,upper=0> beta0_no3_crtp;

    // hierarchical scale parameters (hyperpriors)
    real<lower=0>        sigma_t0_culmeso;
    real<lower=0>        sigma_k_culmeso;
    real<lower=0>        sigma_b_culmeso;
    real<lower=0>        sigma_Q_culmeso;
    real<lower=0>        sigma_v_culmeso;

    // observation noise
    real<lower=0>        sigma_scaledRI_cul;  // culture noise
    real<lower=0>        sigma_scaledRI_meso;  // mesocosm noise
    real<lower=0>        sigma_scaledRI_crtp;  // coretop noise
}

model {
    // 1 Priors for shared parameters for culture+mesocosm
    t0_culmeso    ~ normal(30, 10) T[-1.8, ];  // truncated normal
    k_culmeso     ~ beta(2, 5);
    b_culmeso     ~ beta(2, 5);
    Q_culmeso      ~ normal(1, 30) T[0, ]; 
    v_culmeso      ~ normal(1, 10) T[0, ]; 

    // 2 Hyperpriors for scales (weakly informative)
    sigma_t0_culmeso     ~ cauchy(0, 1);
    sigma_k_culmeso      ~ cauchy(0, 1);
    sigma_b_culmeso      ~ cauchy(0, 1);
    sigma_Q_culmeso      ~ cauchy(0, 1);
    sigma_v_culmeso      ~ cauchy(0, 1);

    // 3 Priors for observation noise
    sigma_scaledRI_cul ~ normal(0.01, 0.1);
    sigma_scaledRI_meso ~ normal(0.01, 0.1);

    // 4 Generalized logistic mean vectors of culture and mesocosm
    vector[N_cul] mu_scaledRI_cul = b_culmeso + (1 - b_culmeso)
        ./ pow(1 + Q_culmeso * exp(-k_culmeso * (t_cul - t0_culmeso)), 1 / v_culmeso);
    vector[N_meso] mu_scaledRI_meso = b_culmeso + (1 - b_culmeso)
        ./ pow(1 + Q_culmeso * exp(-k_culmeso * (t_meso - t0_culmeso)), 1 / v_culmeso);

    scaledRI_cul ~ normal(mu_scaledRI_cul, sigma_scaledRI_cul);
    scaledRI_meso ~ normal(mu_scaledRI_meso, sigma_scaledRI_meso);
    
    // 5 Coretop priors 
    t0_crtp  ~ normal(t0_culmeso, sigma_t0_culmeso);
    k_crtp   ~ normal(k_culmeso, sigma_k_culmeso);
    b_crtp   ~ normal(b_culmeso, sigma_b_culmeso);
    Q_crtp   ~ normal(Q_culmeso, sigma_Q_culmeso);
    v_crtp   ~ normal(v_culmeso, sigma_v_culmeso)
    beta0_gdgt23ratio_crtp ~ normal(0, 0.05);
    beta0_no3_crtp ~ normal(0, 0.05);

    // 6 Likelihoods for coretops 
    vector[N_crtp] mu_scaledRI_crtp;
    for (i in 1:N_crtp) {
        real base_scaledRI = b_crtp + (1 - b_crtp) 
        ./ pow(1 + Q_crtp * exp(-k_crtp * (t_crtp[i] - t0_crtp)), 1 / v_crtp);
        mu_scaledRI_crtp[i] = base_scaledRI;

        if (use_gdgt23ratio == 1)
            mu_scaledRI_crtp[i] += beta0_gdgt23ratio_crtp * gdgt23ratio_crtp[i];

        if (use_no3 == 1) {
            if (no3_crtp[i] > 0 && no3_crtp[i] < no3_cutoff)
            mu_scaledRI_crtp[i] += beta0_no3_crtp * log10(no3_crtp[i]);
        }
    }
    sigma_scaledRI_crtp ~ normal(0.01, 0.1);
    scaledRI_crtp ~ normal(mu_scaledRI_crtp, sigma_scaledRI_crtp);
}