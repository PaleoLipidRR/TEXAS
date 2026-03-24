// ═══════════════════════════════════════════════════════════════════════════════
// invT_logistic_fixed_univ_marginal_truncated_prior.stan
//
// PURPOSE: Bayesian paleotemperature reconstruction from observed Ring Index
//          values. Univariate (no non-thermal predictors), standard logistic
//          curve (Q = 1, ν = 1 fixed — no asymmetry or shape parameters).
//
// CURVE: Standard logistic (special case of Richards/generalized logistic):
//   f(T; θ_m) = b_m + (1 - b_m) / (1 + exp(-k_m · (T - T₀_m)))
//   Used when the forward calibration was run with a standard logistic model
//   (Q and v were not estimated, so the forward posterior has no Q or v draws).
//   Use the gen_logi variant if Q and ν are present in the forward posterior.
//
// TEMPERATURE CONSTRAINT: "truncated_prior" variant
//   See invT_gen_logi_fixed_univ_marginal_truncated_prior.stan for a full
//   explanation of why the hard_constraint Jacobian biases P50 warm for polar
//   sites, and how the inverse-CDF reparameterization avoids this.
//
//   q[n] ~ Uniform(0,1) is mapped to t_est[n] via the quantile function of
//   TruncNormal(prior_mu_t[n], prior_sigma_t, lower=min_temp). This gives a
//   proper truncated Normal prior with no Jacobian distortion.
// ═══════════════════════════════════════════════════════════════════════════════

data {
    int<lower=1> N;
    vector[N] proxy_param;

    vector[N] prior_mu_t;
    real prior_sigma_t;

    int<lower=1> M;
    vector[M] t0;
    vector[M] k;
    vector[M] b;
    vector[M] sigma_proxy_param;
    // Note: no Q or v — standard logistic fixes Q=1, ν=1 (symmetric sigmoid).

    real min_temp;
}

parameters {
    vector<lower=0, upper=1>[N] q;
}

transformed parameters {
    vector[N] t_est;
    for (n in 1:N) {
        real p_lower = normal_cdf(min_temp | prior_mu_t[n], prior_sigma_t);
        t_est[n] = prior_mu_t[n]
                 + prior_sigma_t * std_normal_qf(p_lower + (1.0 - p_lower) * q[n]);
    }
}

model {
    real log_M = log(M);

    for (n in 1:N) {
        vector[M] lp;

        for (m in 1:M) {
            // Standard logistic (Q=1, ν=1):
            real mu = b[m] + (1 - b[m]) / (1 + exp(-k[m] * (t_est[n] - t0[m])));
            lp[m] = normal_lpdf(proxy_param[n] | mu, sigma_proxy_param[m]);
        }

        target += log_sum_exp(lp) - log_M;
    }
}
