// linear model

data {
    int<lower=1> N;
    vector[N] temp_vals;
    vector[N] proxy_vals;
}

parameters {
    real<lower=0> slope;
    real<lower=0> intercept;
    real<lower=0> sigma_proxy_vals;
}

model {
    // Priors
    slope   ~ normal(0,0.25)T[0,];
    intercept ~ normal(0,0.25);

    sigma_proxy_vals ~ normal(0.01, 0.1);

    // Linear model
    vector[N] mu_proxy_vals = slope * temp_vals + intercept;

    // Likelihoods
    proxy_vals ~ normal(mu_proxy_vals,sigma_proxy_vals);
}