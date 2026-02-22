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
    real prior_mean_Q;
    real prior_sd_Q;
    real prior_mean_v;
    real prior_sd_v;   
}

parameters {
    // logistic parameters for coretop
    real<lower=10, upper=50> t0_crtp;            // center (not necessarily inflection point)
    real<lower=0.01, upper=0.5> k_crtp;          // growth rate
    real<lower=0.1, upper=0.6> b_crtp;           // lower asymptote
    real<lower=0.01> Q_crtp;                    // curve-start factor (Q)
    real<lower=0.1> v_crtp;                     // asymmetry / shape parameter (ν)
  
    real<lower=-1,upper=0> beta_G23_crtp;
    real<lower=-1,upper=0> beta_NO3_crtp;

    // observation noise
    real<lower=0>        sigma_scaledRI_crtp;  // coretop noise
}

model {

    // Coretop priors 
    t0_crtp ~ normal(prior_mean_t0, prior_sd_t0);
    k_crtp  ~ normal(prior_mean_k, prior_sd_k);
    b_crtp  ~ normal(prior_mean_b, prior_sd_b);
    Q_crtp  ~ normal(prior_mean_Q, prior_sd_Q);
    v_crtp  ~ normal(prior_mean_v, prior_sd_v);
    beta_G23_crtp ~ normal(0, 0.05);
    beta_NO3_crtp ~ normal(0, 0.05);

    // Likelihoods for coretops 
    vector[N_crtp] mu_scaledRI_crtp;
    for (i in 1:N_crtp) {
        //temperature term
        real base_scaledRI = b_crtp + (1 - b_crtp) 
        ./ pow(1 + Q_crtp * exp(-k_crtp * (t_crtp[i] - t0_crtp)), 1 / v_crtp);
        mu_scaledRI_crtp[i] = base_scaledRI;

        if (use_gdgt23ratio == 1)
            mu_scaledRI_crtp[i] += beta_G23_crtp * gdgt23ratio_crtp[i];

        if (use_no3 == 1) {
            if (no3_crtp[i] > 0 && no3_crtp[i] < no3_cutoff)
            mu_scaledRI_crtp[i] += beta_NO3_crtp * log10(no3_crtp[i]);
        }
    }
    sigma_scaledRI_crtp ~ normal(0.01, 0.1);
    scaledRI_crtp ~ normal(mu_scaledRI_crtp, sigma_scaledRI_crtp);
}