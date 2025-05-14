data {
    int<lower=1> N_cul;
    vector[N_cul] thermoT_cul;
    vector[N_cul] scaledRI_cul;

    int<lower=1> N_meso;
    vector[N_meso] thermoT_meso;
    vector[N_meso] scaledRI_meso;

    int<lower=1> N_coretop;
    vector[N_coretop] thermoT_coretop;
    vector[N_coretop] scaledRI_coretop;

    // optional predictors
    vector[N_coretop] gdgt23ratio;
    int<lower=0, upper=1> use_gdgt23ratio;

    vector[N_coretop] depthIntg_thermoT_no3;
    int<lower=0, upper=1> use_depthIntg_thermoT_no3;
}

parameters {
    // shared logistic parameters
    real<lower=-1.8> x0_culmeso;
    real<lower=0, upper=1> k_culmeso;
    real<lower=0, upper=1> b_culmeso;

    // coretop-specific parameters
    real<lower=-1.8> x0_coretop;
    real<lower=0, upper=1> k_coretop;
    real<lower=0, upper=1> b_coretop;

    real<lower=-1, upper=0> beta0_gdgt23ratio;
    real<lower=-1, upper=0> beta0_depthIntg_thermoT_no3;

    // hierarchical priors
    real<lower=0> sigma_x0;
    real<lower=0> sigma_k;
    real<lower=0> sigma_b;

    // noise
    real<lower=0> sigma_scaledRI_cul;
    real<lower=0> sigma_scaledRI_meso;
    real<lower=0> sigma_scaledRI_coretop;
}

model {
    // shared priors
    x0_culmeso ~ normal(30, 10) T[-1.8, ];
    k_culmeso ~ beta(2, 5);
    b_culmeso ~ beta(2, 5);

    sigma_x0 ~ cauchy(0, 1);
    sigma_k ~ cauchy(0, 1);
    sigma_b ~ cauchy(0, 1);

    sigma_scaledRI_cul ~ normal(0.01, 0.1);
    sigma_scaledRI_meso ~ normal(0.01, 0.1);
    sigma_scaledRI_coretop ~ normal(0.01, 0.1);

    // culture + mesocosm likelihood
    vector[N_cul] mu_scaledRI_cul = (1 - b_culmeso) * inv_logit(k_culmeso * (thermoT_cul - x0_culmeso)) + b_culmeso;
    vector[N_meso] mu_scaledRI_meso = (1 - b_culmeso) * inv_logit(k_culmeso * (thermoT_meso - x0_culmeso)) + b_culmeso;

    scaledRI_cul ~ normal(mu_scaledRI_cul, sigma_scaledRI_cul);
    scaledRI_meso ~ normal(mu_scaledRI_meso, sigma_scaledRI_meso);

    // hierarchical priors
    x0_coretop ~ normal(x0_culmeso, sigma_x0);
    k_coretop ~ normal(k_culmeso, sigma_k);
    b_coretop ~ normal(b_culmeso, sigma_b);

    beta0_gdgt23ratio ~ normal(0, 0.05) T[-1, 0];
    beta0_depthIntg_thermoT_no3 ~ normal(0, 0.05) T[-1, 0];

    // coretop likelihood
    vector[N_coretop] mu_scaledRI_coretop;
    for (i in 1:N_coretop) {
        mu_scaledRI_coretop[i] = (1 - b_coretop) * inv_logit(k_coretop * (thermoT_coretop[i] - x0_coretop)) + b_coretop;

        if (use_gdgt23ratio == 1) {
            mu_scaledRI_coretop[i] += beta0_gdgt23ratio * gdgt23ratio[i];
        }

        if (use_depthIntg_thermoT_no3 == 1 && depthIntg_thermoT_no3[i] <= 2.7) {
            mu_scaledRI_coretop[i] += beta0_depthIntg_thermoT_no3 * log10(depthIntg_thermoT_no3[i]);
        }
    }

    scaledRI_coretop ~ normal(mu_scaledRI_coretop, sigma_scaledRI_coretop);
}

generated quantities {
    real sigma_meso_cul_ratio = sigma_scaledRI_meso / sigma_scaledRI_cul;
    real sigma_coretop_cul_ratio = sigma_scaledRI_coretop / sigma_scaledRI_cul;
}
