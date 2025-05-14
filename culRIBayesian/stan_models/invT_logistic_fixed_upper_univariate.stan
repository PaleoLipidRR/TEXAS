// invT_logistic_fixed_upper
data {
  // input params from GDGT dataset
  int<lower=1> N;       
  vector[N] scaledRI; // RI predictor    
  vector[N] prior_mu_t;
  real      prior_sig_t;


  // input params from solved posteriors
  int<lower=1> M;
  vector[M] x0;
  vector[M] k;
  vector[M] b;
  vector[M] sigma_coretop_scaledRI;
}

parameters {
    matrix<lower=-1.8>[N,M] t; // temperature to estimate
}

model {
    vector[N] mu_scaledRI; // mean values
    for (m in 1:M) {
        t[:,m] ~ normal(prior_mu_t, prior_sig_t);
        
        // Solve for T from the logistic model
        mu_scaledRI = (1 - b[m]) * inv_logit(k[m] * (t[:,m] - x0[m])) + b[m];

        // Likelihoods
        scaledRI ~ normal(mu_scaledRI,sigma_coretop_scaledRI[m])
    }

}
