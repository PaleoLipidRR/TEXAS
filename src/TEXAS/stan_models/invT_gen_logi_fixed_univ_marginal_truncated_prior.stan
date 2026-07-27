// ===============================================================================
// invT_gen_logi_fixed_univ_marginal_truncated_prior.stan
//
// PURPOSE: Bayesian paleotemperature reconstruction from observed Ring Index
//          values. Univariate (no non-thermal predictors), generalized logistic
//          (Richards) curve.
//
// APPROACH - "Marginal" (direct sampling):
//   The forward calibration introduces uncertainty in the RI-T curve parameters
//   theta = {T0, k, b, nu, sigma}. We marginalize (integrate) over this uncertainty:
//
//     p(RI_obs | T) = integral p(RI_obs | T, theta) * p(theta | calib. data) dtheta
//                   ~= (1/M) Sum_{m=1}^{M}  Normal(RI_obs | f(T; theta_m), sigma_m)
//
//   where theta_m is the m-th draw from the forward calibration posterior.
//   This is a Monte Carlo approximation of the integral using M pre-sampled
//   calibration curves. The only free parameter in this Stan model is T.
//
// TEMPERATURE CONSTRAINT: "truncated_prior" variant
//
//   PROBLEM WITH HARD CONSTRAINT:
//   Declaring t_est as vector<lower=min_temp>[N] causes Stan to reparameterize
//   internally: t_est = min_temp + exp(eta). The resulting Jacobian log(t-min_temp)
//   is automatically added to the log-target, making the effective prior:
//     p_eff(t) proportional to Normal(t | mu, sigma) * (t - min_temp)
//   The linear factor repels the posterior away from the boundary, shifting P50
//   unrealistically warm for polar sites where t is close to min_temp.
//
//   THIS MODEL'S SOLUTION - inverse-CDF reparameterization:
//   Instead of sampling t directly, we sample q ~ Uniform(0,1) and map it to
//   temperature via the quantile function of the truncated Normal:
//
//     p_lower = Phi((min_temp - mu_n) / sigma)          // CDF at lower bound
//     t_n = Normal_QF(p_lower + (1-p_lower)*q_n, mu_n, sigma)
//
//   Because q ~ Uniform(0,1) (the default for a <lower=0,upper=1> parameter),
//   the implied prior on t is exactly the truncated Normal - no Jacobian distortion.
//   The posterior is correctly shaped near min_temp and P50 remains data-driven.
//
//   SUMMARY:
//     hard_constraint : t can't go below min_temp, but Jacobian biases P50 warm
//     unconstrained   : P50 correct, but P5 can reach unrealistically cold values
//     truncated_prior : P50 correct AND P5 bounded at min_temp - best of both
// ===============================================================================

data {
    // --- Proxy observations to reconstruct ------------------------------------
    int<lower=1> N;            // Number of sediment samples (downcore or coretop)
    vector[N] proxy_param;        // Observed scaled Ring Index for each sample (in [0,1])

    // --- Prior on paleotemperature ---------------------------------------------
    // Defines the truncated Normal prior: T ~ TruncNormal(prior_mu_t, prior_sigma_t, lower=min_temp).
    // Use prior_sigma_t = 10-15degC for a diffuse prior.
    vector[N] prior_mu_t;      // Prior mean temperature for each sample (degC)
    real prior_sigma_t;        // Prior SD (shared across all samples) (degC)

    // --- Forward calibration posterior - M draws of all curve parameters -------
    // Loaded from the forward calibration .nc file by build_invT_inputData().
    int<lower=1> M;
    vector[M] t0;              // T0_m: reference temperature of each calibration draw (degC)
    vector[M] k;               // k_m: steepness
    vector[M] b;               // b_m: lower asymptote
    vector[M] v;               // nu_m: shape
    vector[M] sigma_proxy_param;  // sigma_m: residual calibration noise

    // --- Truncated Normal lower bound -----------------------------------------
    // Physical lower bound for the truncated Normal prior on temperature.
    // Typical value: -1.8degC (seawater freezing point).
    // Unlike hard_constraint, this is used only to define the prior, NOT as a
    // hard constraint on the sampled parameter (no Jacobian distortion).
    real min_temp;
}

parameters {
    // --- Quantile of the truncated Normal prior --------------------------------
    // q[n] in (0,1) is the quantile of the truncated Normal for sample n.
    // Sampling q ~ Uniform(0,1) and mapping to t via the quantile function gives
    // a proper truncated Normal prior on t WITHOUT any Jacobian distortion.
    // Stan samples q on the logit scale internally; the (0,1) bounds prevent
    // HMC from ever proposing temperatures below min_temp.
    vector<lower=0, upper=1>[N] q;
}

transformed parameters {
    // --- Temperature reconstruction via inverse-CDF mapping -------------------
    // Map each q[n] in (0,1) to a temperature via the quantile function of the
    // truncated Normal(prior_mu_t[n], prior_sigma_t, lower=min_temp).
    //
    //   p_lower = Phi((min_temp - mu_n) / sigma)     // fraction of Normal mass below min_temp
    //   t[n] = mu_n + sigma * std_normal_qf(p_lower + (1-p_lower)*q[n])
    //
    // By construction: t[n] >= min_temp for all n. The prior on t[n] implied by
    // q[n] ~ Uniform(0,1) is exactly TruncNormal(mu_n, sigma, lower=min_temp).
    vector[N] t_est;
    for (n in 1:N) {
        real p_lower = normal_cdf(min_temp | prior_mu_t[n], prior_sigma_t);
        t_est[n] = prior_mu_t[n]
                 + prior_sigma_t * std_normal_qf(p_lower + (1.0 - p_lower) * q[n]);
    }
}

model {
    // No explicit prior on q - the implicit Uniform(0,1) from the <lower=0,upper=1>
    // bounds IS the intended prior. The truncated Normal prior on t_est is
    // automatically induced by the q -> t_est transformation above.

    // --- Likelihood: Monte Carlo marginalization over calibration uncertainty --
    // For each sample n, average the Normal likelihood over all M calibration
    // curves (log-sum-exp trick for numerical stability):
    //
    //   log p(RI_n | T_n) ~= log_sum_exp(lp_1, ..., lp_M) - log(M)

    real log_M = log(M);

    for (n in 1:N) {
        vector[M] lp;

        for (m in 1:M) {
            // Richards curve: expected RI for temperature t_est[n] under draw m.
            real mu = b[m] + (1 - b[m])
                / pow(1 + exp(-k[m] * (t_est[n] - t0[m])), 1.0 / v[m]);
            lp[m] = normal_lpdf(proxy_param[n] | mu, sigma_proxy_param[m]);
        }

        target += log_sum_exp(lp) - log_M;
    }
}
