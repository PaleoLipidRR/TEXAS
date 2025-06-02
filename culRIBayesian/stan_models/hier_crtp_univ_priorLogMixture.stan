// Stage 2 - use posteriors from stage 1 from jnt-cul-meso
data {
    int<lower=1> N_crtp;    
    vector[N_crtp] t_crtp;    
    vector[N_crtp] scaledRI_crtp;    

    // posteriors from stage 1 model
    int<lower=1> M;
    vector[M] t0;
    vector[M] k;
    vector[M] b;
    vector[M] sigma_scaledRI;

    // bandwidth for log-mixture prior
    real<lower=0> mixture_sigma;
}

parameters {
    real<lower=-2, upper=50> t0_crtp;       // slightly conservative range
    real<lower=1e-3, upper=50> k_crtp;      // avoid k → 0 (flat) or → ∞ (numerical explosion)
    real<lower=1e-3, upper=1 - 1e-3> b_crtp; // prevent exact 0 or 1 (flat lines)


    real<lower=0> sigma_scaledRI_crtp;          // observed noise
}

model {
  // Informative priors based on Stage 1 posteriors using log mixture
    {
        vector[M] log_lik_t0;
        vector[M] log_lik_k;
        vector[M] log_lik_b;

        for (m in 1:M) {
        log_lik_t0[m] = normal_lpdf(t0_crtp | t0[m], mixture_sigma);  // adjust spread if needed
        log_lik_k[m]  = normal_lpdf(k_crtp  | k[m],  mixture_sigma);
        log_lik_b[m]  = normal_lpdf(b_crtp  | b[m],  mixture_sigma);
        }

        target += log_sum_exp(log_lik_t0) - log(M);
        target += log_sum_exp(log_lik_k)  - log(M);
        target += log_sum_exp(log_lik_b)  - log(M);
    }

    // Prior for observation noise
    sigma_scaledRI_crtp ~ normal(0.01, 0.1);  // or another weakly informative prior

    // Coretop likelihood using logistic model
    vector[N_crtp] mu = (1 - b_crtp) * inv_logit(k_crtp * (t_crtp - t0_crtp)) + b_crtp;
    scaledRI_crtp ~ normal(mu, sigma_scaledRI_crtp);
}


