data {
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

    real prior_mean_t0;
    real prior_sd_t0;
    real prior_mean_k;
    real prior_sd_k;
    real prior_mean_b;
    real prior_sd_b;    
}

parameters {
    // logistic parameters for coretop
    real<lower=-1.8>     t0_crtp;
    real<lower=0,upper=1> k_crtp;
    real<lower=0,upper=1> b_crtp;
    real<lower=-1,upper=0> beta0_gdgt23ratio_crtp;
    real<lower=-1,upper=0> beta0_no3_crtp;

    // observation noise
    real<lower=0>        sigma_scaledRI_crtp;  // coretop noise
}

model {

    // 5 Coretop priors 
    t0_crtp ~ normal(prior_mean_t0, prior_sd_t0);
    k_crtp  ~ normal(prior_mean_k, prior_sd_k);
    b_crtp  ~ normal(prior_mean_b, prior_sd_b);
    beta0_gdgt23ratio_crtp ~ normal(0, 0.05);
    beta0_no3_crtp ~ normal(0, 0.05);

    // 6 Likelihoods for coretops 
    vector[N_crtp] mu_scaledRI_crtp;
    for (i in 1:N_crtp) {
        real base_scaledRI = (1 - b_crtp) * inv_logit(k_crtp * (t_crtp[i] - t0_crtp)) + b_crtp;
        mu_scaledRI_crtp[i] = base_scaledRI;

        if (use_gdgt23ratio == 1)
            mu_scaledRI_crtp[i] += beta0_gdgt23ratio_crtp * gdgt23ratio_crtp[i];

        if (use_no3 == 1) {
            if (no3_crtp[i] > 0 && no3_crtp[i] < no3_cutoff)
            mu_scaledRI_crtp[i] += beta0_no3_crtp * log10(no3_crtp[i]);
        }
    }
    sigma_scaledRI_crtp ~ normal(0.01, 0.1) T[1e-6, ];
    scaledRI_crtp ~ normal(mu_scaledRI_crtp, sigma_scaledRI_crtp);
}