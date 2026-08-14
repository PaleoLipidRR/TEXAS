// ===============================================================================
// linear_model.stan
//
// PURPOSE: Straight-line regression of a proxy against temperature, used as the
//          reference functional form the sigmoid calibrations are compared
//          against in the SI figures.
//
//   proxy = slope * T + intercept,   proxy ~ Normal(mu, sigma)
//
// slope and intercept are both constrained non-negative, which suits the
// positively sloped proxy-temperature relationships this is applied to; it is
// not a general-purpose linear regression.
// ===============================================================================

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
    slope   ~ normal(0,0.5)T[0,];
    intercept ~ normal(0,1);

    sigma_proxy_vals ~ normal(0.01, 0.1);

    // Linear model
    vector[N] mu_proxy_vals = slope * temp_vals + intercept;

    // Likelihoods
    proxy_vals ~ normal(mu_proxy_vals,sigma_proxy_vals);
}