// ═══════════════════════════════════════════════════════════════════════════════
// gen_logi_fixed_hier_crtp_multiv_odr.stan
//
// PURPOSE: Full hierarchical Bayesian forward calibration (culture + mesocosm
//          + coretop jointly) with TRUE Bayesian error-in-variables (EIV) /
//          latent variable treatment of the secondary non-thermal predictors
//          (G₂/₃ ratio and/or NO₃) at coretop sites.
//          Extends gen_logi_fixed_hier_crtp_multiv.stan.
//
// EIV MODEL — latent variable formulation
// ─────────────────────────────────────────────────────────────────────────────
// Culture and mesocosm likelihoods are unaffected (no secondary predictors).
// For each coretop predictor with classical measurement error:
//
//   Measurement model:   X_obs[i] = X_true[i] + ε_X[i],  ε_X ~ N(0, σ_X[i])
//   Structural equation: RI[i]    = f(T[i], X_true[i]) + ε_RI,  ε_RI ~ N(0, σ_RI)
//
// The latent true predictors (X_true) are sampled jointly with all model
// parameters via HMC. Conditioning the structural equation on X_true rather
// than X_obs removes the attenuation bias in β (Carroll et al. 2006, Chap. 2).
//
//   Carroll, R.J., Ruppert, D., Stefanski, L.A., and Crainiceanu, C.M. (2006).
//     Measurement Error in Nonlinear Models: A Modern Perspective, 2nd ed.
//     Chapman & Hall/CRC.  Chap. 2 (attenuation bias in linear models),
//     Chap. 7 (Bayesian methods for measurement error).
//   Fuller, W.A. (1987). Measurement Error Models. Wiley.
//   Stan User's Guide — Measurement Error and Meta-Analysis.
//     https://mc-stan.org/docs/stan-users-guide/measurement-error-and-meta-analysis.html
//   Buonaccorsi, J.P. (2010). Measurement Error: Models, Methods, and Applications.
//     Chapman & Hall/CRC.
//
// CONTRAST WITH VARIANCE PROPAGATION (archived as _odr_archived.stan):
//   The archived model inflated σ_eff via β² · σ²_X. This widens the likelihood,
//   letting the prior attenuate β toward zero — the opposite of the intended
//   de-attenuation. The latent variable approach here is the correct fix.
//
// PRIOR DESIGN NOTE — why β_{NO₃} must not be centered at zero:
//   The latent variables log10_no3_true[j] introduce extra degrees of freedom.
//   With a zero-centered prior on β, the HMC sampler can fit the RI observations
//   by adjusting the latent variables WITHOUT moving β away from zero — the
//   latent variables absorb the residuals instead. This paradoxically produces
//   MORE attenuation than the naive (no-EIV) model that uses X_obs directly.
//   Solution: use the same informative prior as the non-EIV model,
//   normal(-0.064, 0.008), so both models are directly comparable and the
//   EIV de-attenuation signal is not masked by a miscentered prior.
//
// LATENT VARIABLES (coretop only):
//
//   G₂/₃ (linear term — exact Gaussian measurement model):
//     g23_true[i] ~ Normal(g23_obs[i], σ_{G23}[i])
//     RI_mean[i] += β_{G23} · g23_true[i]
//     N_g23 = N_crtp when use_gdgt23ratio = 1; zero-length otherwise.
//
//   NO₃ (log₁₀ term — delta-method measurement model on log scale):
//     σ_log10[i] = σ_{NO₃}[i] / (NO₃_obs[i] · ln 10)   [delta method; Carroll et al. 2006]
//     log10_no3_true[j] ~ Normal(log₁₀(NO₃_obs[j]), σ_log10[j])
//     RI_mean[i] += β_{NO₃} · log10_no3_true[j]
//     Applied only at the N_no3_valid sites where 0 < NO₃_obs < no3_cutoff
//     (selection-on-observables assumption; Carroll et al. 2006).
//
// MODEL DESIGN (same hierarchy as gen_logi_fixed_hier_crtp_multiv.stan):
//   Two-group hierarchy: culture + mesocosm constrain curve SHAPE; coretop
//   parameters are drawn from hierarchical priors centered on culmeso estimates
//   (partial pooling). Non-thermal EIV corrections applied to coretop data only.
//
// CALIBRATION CURVE — generalized logistic (Richards, upper asymptote = 1, Q = 1):
//   RI = b + (1 − b) / (1 + exp(−k · (T − T₀)))^(1/ν)            [Eq. 1]
//
// NON-THERMAL CORRECTIONS (coretop only, if enabled):
//   RI += β_{G₂/₃} · g23_true                                     [Eq. 6, latent]
//   RI += β_{NO₃}  · log₁₀(no3_true)  [only 0 < NO₃ < cutoff]   [Eq. 7, latent]
// ═══════════════════════════════════════════════════════════════════════════════

data {
    // ─── Culture data ─────────────────────────────────────────────────────────
    int<lower=1> N_cul;
    vector[N_cul] t_cul;
    vector[N_cul] proxyObs_cul;

    // ─── Mesocosm data ────────────────────────────────────────────────────────
    int<lower=1> N_meso;
    vector[N_meso] t_meso;
    vector[N_meso] proxyObs_meso;

    // ─── Coretop (sediment) data ──────────────────────────────────────────────
    int<lower=1> N_crtp;
    vector[N_crtp] t_crtp;
    vector[N_crtp] proxyObs_crtp;

    // ─── G₂/₃ ratio: observed values + per-site measurement SEs ─────────────
    // N_g23 = N_crtp when use_gdgt23ratio = 1; N_g23 = 0 when not used.
    // Zero-length parameter arrays eliminate wasted sampling when disabled.
    int<lower=0> N_g23;
    vector[N_crtp] gdgt23ratio_crtp;              // observed G₂/₃ (used when N_g23 > 0)
    vector<lower=0>[N_crtp] sd_gdgt23ratio_crtp;  // per-site SE of G₂/₃ (linear scale)
    int<lower=0, upper=1> use_gdgt23ratio;

    // ─── NO₃: observed values + per-site measurement SEs ─────────────────────
    // Latent log₁₀(NO₃) estimated only at N_no3_valid sites where
    // 0 < NO₃_obs < no3_cutoff. no3_valid_idx gives their 1-based positions in
    // the coretop arrays (pre-computed by build_fwd_data() in builder.py).
    vector[N_crtp] no3_crtp;                                         // observed NO₃ (μmol/L)
    vector<lower=0>[N_crtp] sd_no3_crtp;                             // per-site SE of NO₃ (μmol/L); 0 = unknown
    int<lower=0, upper=1> use_no3;
    real no3_cutoff;
    // EIV sites: 0 < NO₃ < cutoff AND sd_no3 > 0 → latent variable estimated.
    int<lower=0> N_no3_valid;
    array[N_no3_valid] int<lower=1, upper=N_crtp> no3_valid_idx;
    // Exact sites: 0 < NO₃ < cutoff AND sd_no3 = 0 → observed value used directly.
    int<lower=0> N_no3_exact;
    array[N_no3_exact] int<lower=1, upper=N_crtp> no3_exact_idx;
}

parameters {
    // ─── Generalized-logistic curve parameters (culture + mesocosm) ───────────
    real<lower=10, upper=50>  t0_culmeso;
    real<lower=0, upper=0.5>  k_culmeso;
    real<lower=0, upper=1>    b_culmeso;
    real<lower=0.1, upper=10> v_culmeso;

    // ─── Coretop curve parameters (hierarchically linked to culmeso) ──────────
    real<lower=10, upper=50>  t0_crtp;
    real<lower=0, upper=0.5>  k_crtp;
    real<lower=0, upper=1>    b_crtp;
    real<lower=0.1, upper=10> v_crtp;

    // ─── Non-thermal correction coefficients (coretop only) ───────────────────
    real<lower=-1, upper=0>  beta_G23_crtp;
    real<lower=-1, upper=0>  beta_NO3_crtp;

    // ─── Hierarchical scale hyperparameters ───────────────────────────────────
    real<lower=0>  sigma_t0_culmeso;
    real<lower=0>  sigma_k_culmeso;
    real<lower=0>  sigma_b_culmeso;
    real<lower=0>  sigma_v_culmeso;

    // ─── Residual observation noise ───────────────────────────────────────────
    real<lower=0>  sigma_proxyObs_cul;
    real<lower=0>  sigma_proxyObs_meso;
    real<lower=0>  sigma_proxyObs_crtp;  // pure RI scatter; predictor SEs in latent vars

    // ─── Latent true predictor values (coretop only) ──────────────────────────
    // g23_true[i]       : true G₂/₃ ratio at coretop site i  (length N_g23)
    // log10_no3_true[j] : true log₁₀(NO₃) at valid NO₃ site j  (length N_no3_valid)
    // Both may be zero-length when the corresponding predictor is not used.
    vector[N_g23]       g23_true;
    vector[N_no3_valid] log10_no3_true;
}

model {
    // ─── 1. Priors for culmeso curve parameters ───────────────────────────────
    t0_culmeso ~ normal(30, 10) T[10, 50];
    k_culmeso  ~ normal(0, 0.2) T[0, 0.5];
    b_culmeso  ~ beta(2, 5);
    v_culmeso  ~ normal(1, 2)   T[0.1, 10];

    // ─── 2. Hyperpriors for hierarchical scale parameters ─────────────────────
    sigma_t0_culmeso ~ normal(0, 5)   T[0, ];
    sigma_k_culmeso  ~ normal(0, 0.2) T[0, ];
    sigma_b_culmeso  ~ normal(0, 0.2) T[0, ];
    sigma_v_culmeso  ~ normal(0, 2)   T[0, ];

    // ─── 3. Priors for residual noise ─────────────────────────────────────────
    sigma_proxyObs_cul  ~ normal(0.01, 0.1);
    sigma_proxyObs_meso ~ normal(0.01, 0.1);
    sigma_proxyObs_crtp ~ normal(0, 0.1);

    // ─── 4. Likelihood for culture + mesocosm data ────────────────────────────
    vector[N_cul] mu_proxyObs_cul = b_culmeso + (1 - b_culmeso)
        ./ pow(1 + exp(-k_culmeso * (t_cul - t0_culmeso)), 1.0 / v_culmeso);
    vector[N_meso] mu_proxyObs_meso = b_culmeso + (1 - b_culmeso)
        ./ pow(1 + exp(-k_culmeso * (t_meso - t0_culmeso)), 1.0 / v_culmeso);

    proxyObs_cul  ~ normal(mu_proxyObs_cul,  sigma_proxyObs_cul);
    proxyObs_meso ~ normal(mu_proxyObs_meso, sigma_proxyObs_meso);

    // ─── 5. Hierarchical priors linking coretop parameters to culmeso ─────────
    t0_crtp ~ normal(t0_culmeso, sigma_t0_culmeso) T[10, 50];
    k_crtp  ~ normal(k_culmeso,  sigma_k_culmeso)  T[0, 0.5];
    b_crtp  ~ normal(b_culmeso,  sigma_b_culmeso)  T[0, 1];
    v_crtp  ~ normal(v_culmeso,  sigma_v_culmeso)  T[0.1, 10];

    beta_G23_crtp ~ normal(0, 0.05);
    beta_NO3_crtp ~ normal(-0.064, 0.008); // matches non-EIV model prior; center ≠ 0 is
                                            // essential — a zero-centered prior with the
                                            // EIV latent variables can cause β to drift
                                            // MORE toward zero (not less) because the
                                            // latent variables absorb residuals that would
                                            // otherwise pull β negative.

    // ─── 6. Measurement models for latent predictors ──────────────────────────
    //
    // Classical measurement error: X_true | X_obs ~ N(X_obs, σ_X)
    // Ref: Carroll et al. (2006), Chap. 2; Stan User's Guide, "Measurement Error and Meta-Analysis"
    //   https://mc-stan.org/docs/stan-users-guide/measurement-error-and-meta-analysis.html
    //
    // G₂/₃ — exact Gaussian, linear scale:
    if (N_g23 > 0)
        g23_true ~ normal(gdgt23ratio_crtp, sd_gdgt23ratio_crtp);

    // NO₃ — delta-method approximation on log₁₀ scale:
    //   σ_log10[i] = σ_{NO₃,obs}[i] / (NO₃_obs[i] · ln 10)
    //   Valid when σ_{NO₃} / NO₃ (coefficient of variation) is small (< ~30%).
    //   Ref: Carroll et al. (2006), Chap. 2 (delta method for transformations);
    //        Buonaccorsi (2010), Chap. 6 (log-scale propagation).
    for (j in 1:N_no3_valid) {
        int i = no3_valid_idx[j];
        real sd_log10_i = sd_no3_crtp[i] / (no3_crtp[i] * log(10.0));
        log10_no3_true[j] ~ normal(log10(no3_crtp[i]), sd_log10_i);
    }

    // ─── 7. Structural equation: coretop calibration curve using LATENT values ─
    //
    // Conditioning on X_true rather than X_obs removes attenuation bias in β:
    // the posterior of β_{NO₃} is more negative (stronger) than in the naive model.
    // Ref: Carroll et al. (2006), Chap. 2 (attenuation bias), Chap. 7 (Bayesian solution).
    //
    vector[N_crtp] mu_crtp = b_crtp + (1 - b_crtp)
        ./ pow(1 + exp(-k_crtp * (t_crtp - t0_crtp)), 1.0 / v_crtp);

    if (N_g23 > 0)
        mu_crtp += beta_G23_crtp * g23_true;       // latent true G₂/₃

    for (j in 1:N_no3_valid) {
        int i = no3_valid_idx[j];
        mu_crtp[i] += beta_NO3_crtp * log10_no3_true[j];  // latent true log₁₀(NO₃)
    }
    // Exact sites (sd_no3 = 0): SE unknown, use observed value directly.
    for (j in 1:N_no3_exact) {
        int i = no3_exact_idx[j];
        mu_crtp[i] += beta_NO3_crtp * log10(no3_crtp[i]);
    }

    // ─── 8. Coretop likelihood — homoscedastic pure RI scatter ────────────────
    //
    // Predictor measurement errors are absorbed into the latent variable posteriors
    // above, so the coretop likelihood is homoscedastic. sigma_proxyObs_crtp is
    // therefore the irreducible RI residual.
    //
    proxyObs_crtp ~ normal(mu_crtp, sigma_proxyObs_crtp);
}

generated quantities {
    // R2_full     : frequentist 1 − RSS/TSS  (evaluated at posterior latent predictor means)
    // bayesR2_full: Gelman et al. (2019) var(μ) / (var(μ) + σ²_RI)
    //               Homoscedastic model → denominator is σ²_proxyObs_crtp.
    // RMSE_full   : root-mean-square error on coretop RI observations.
    real R2_full;
    real bayesR2_full;
    real RMSE_full;

    {
        // g23_true and log10_no3_true are sampled parameters — accessible here
        // without recomputation (parameters are in scope in generated quantities blocks).
        vector[N_crtp] mu = b_crtp + (1 - b_crtp)
            ./ pow(1 + exp(-k_crtp * (t_crtp - t0_crtp)), 1.0 / v_crtp);

        if (N_g23 > 0)
            mu += beta_G23_crtp * g23_true;

        for (j in 1:N_no3_valid) {
            int i = no3_valid_idx[j];
            mu[i] += beta_NO3_crtp * log10_no3_true[j];
        }
        for (j in 1:N_no3_exact) {
            int i = no3_exact_idx[j];
            mu[i] += beta_NO3_crtp * log10(no3_crtp[i]);
        }

        vector[N_crtp] resid = proxyObs_crtp - mu;
        real ybar  = mean(proxyObs_crtp);
        real TSS   = dot_self(proxyObs_crtp - ybar);
        real RSS   = dot_self(resid);
        R2_full    = 1 - RSS / TSS;
        RMSE_full  = sqrt(RSS / N_crtp);

        real var_mu    = variance(mu);
        real var_sigma = square(sigma_proxyObs_crtp);
        bayesR2_full   = var_mu / (var_mu + var_sigma);
    }
}
