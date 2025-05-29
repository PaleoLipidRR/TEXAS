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
    vector[N_crtp] gdgt23ratio;
    int<lower=0, upper=1> use_gdgt23ratio;

    vector[N_crtp] no3;
    int<lower=0, upper=1> use_no3;
}

parameters {
    // shared logistic parameters
    real<lower=-1.8> t0_culmeso;
    real<lower=0, upper=1> k_culmeso;
    real<lower=0, upper=1> b_culmeso;

    // coretop-specific parameters
    real<lower=-1.8> t0_crtp;
    real<lower=0, upper=1> k_crtp;
    real<lower=0, upper=1> b_crtp;

    real<lower=-1, upper=0> beta0_gdgt23ratio;
    real<lower=-1, upper=0> beta0_no3;

    // hierarchical priors
    real<lower=0> sigma_t0_culmeso;
    real<lower=0> sigma_k_culmeso;
    real<lower=0> sigma_b_culmeso;

    // noise
    real<lower=0> sigma_scaledRI_cul;
    real<lower=0> sigma_scaledRI_meso;
    real<lower=0> sigma_scaledRI_crtp;
}

model {
    // shared priors
    t0_culmeso ~ normal(30, 10) T[-1.8, ];
    k_culmeso ~ beta(2, 5);
    b_culmeso ~ beta(2, 5);

    sigma_t0_culmeso ~ cauchy(0, 1);
    sigma_k_culmeso ~ cauchy(0, 1);
    sigma_b_culmeso ~ cauchy(0, 1);

    sigma_scaledRI_cul ~ normal(0.01, 0.1);
    sigma_scaledRI_meso ~ normal(0.01, 0.1);
    sigma_scaledRI_crtp ~ normal(0.01, 0.1);

    // culture + mesocosm likelihood
    vector[N_cul] mu_scaledRI_cul = (1 - b_culmeso) * inv_logit(k_culmeso * (t_cul - t0_culmeso)) + b_culmeso;
    vector[N_meso] mu_scaledRI_meso = (1 - b_culmeso) * inv_logit(k_culmeso * (t_meso - t0_culmeso)) + b_culmeso;

    scaledRI_cul ~ normal(mu_scaledRI_cul, sigma_scaledRI_cul);
    scaledRI_meso ~ normal(mu_scaledRI_meso, sigma_scaledRI_meso);

    // hierarchical priors
    t0_crtp ~ normal(t0_culmeso, sigma_t0_culmeso);
    k_crtp ~ normal(k_culmeso, sigma_k_culmeso);
    b_crtp ~ normal(b_culmeso, sigma_b_culmeso);

    beta0_gdgt23ratio ~ normal(0, 0.05) T[-1, 0];
    beta0_no3 ~ normal(0, 0.05) T[-1, 0];

    // coretop likelihood
    vector[N_crtp] mu_scaledRI_crtp;
    for (i in 1:N_crtp) {
        mu_scaledRI_crtp[i] = (1 - b_crtp) * inv_logit(k_crtp * (t_crtp[i] - t0_crtp)) + b_crtp;

        if (use_gdgt23ratio == 1) {
            mu_scaledRI_crtp[i] += beta0_gdgt23ratio * gdgt23ratio[i];
        }

        if (use_no3 == 1 && no3[i] <= 2.7) {
            mu_scaledRI_crtp[i] += beta0_no3 * log10(no3[i]);
        }
    }

    scaledRI_crtp ~ normal(mu_scaledRI_crtp, sigma_scaledRI_crtp);
}
