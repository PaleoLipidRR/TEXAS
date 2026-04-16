// ═══════════════════════════════════════════════════════════════════════════════
// gen_logi_fixed_hier_crtp_multiv_priorApprox_werr.stan
//
// PURPOSE: Coretop-only forward calibration with TRUE Bayesian error-in-variables
//          (EIV) / latent variable treatment of the secondary non-thermal
//          predictors (G₂/₃ ratio and/or NO₃). Extends the priorApprox model.
//
// EIV MODEL — latent variable formulation
// ─────────────────────────────────────────────────────────────────────────────
// For each predictor with classical measurement error:
//
//   Measurement model:   X_obs[i] = X_true[i] + ε_X[i],  ε_X ~ N(0, σ_X[i])
//   Structural equation: RI[i]    = f(T[i], X_true[i]) + ε_RI,  ε_RI ~ N(0, σ_RI)
//
// The latent true predictors (X_true) are sampled jointly with all model
// parameters via HMC. Because the structural equation is conditioned on the
// LATENT (error-free) predictor, the resulting posterior for β is de-attenuated:
// it is more extreme than the naive estimator that uses noisy X_obs directly.
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
// CONTRAST WITH VARIANCE PROPAGATION (archived as _werr_archived.stan):
//   The archived model inflated σ_eff via β² · σ²_X. This WIDENS the likelihood,
//   letting the prior attenuate β toward zero — the opposite of de-attenuation.
//   The latent variable approach below is the correct fix.
//
// PRIOR DESIGN NOTE — why β_{NO₃} is zero-centered in this model:
//   The latent variables log10_no3_true[j] introduce extra degrees of freedom.
//   With a strongly informative prior on β, the sampler can be forced toward
//   that prior regardless of the EIV signal in the data. Here we instead use
//   a weakly informative zero-centered prior, normal(0, 0.05), so that the
//   latent-variable model can reveal the de-attenuated NO₃ effect if present.
//
// LATENT VARIABLES:
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
// WORKFLOW (two-stage priorApprox):
//   Step 1: Run gen_logi_fixed_culmeso.stan → extract posterior mean/SD for
//           {t0, k, b, v} and pass as prior_mean_* / prior_sd_* inputs.
//   Step 2: This model fits only the coretop parameters using those hyperpriors.
//
// CALIBRATION CURVE — generalized logistic (Richards, upper asymptote = 1, Q = 1):
//   RI = b + (1 − b) / (1 + exp(−k · (T − T₀)))^(1/ν)            [Eq. 1]
//
// NON-THERMAL CORRECTIONS (if enabled):
//   RI += β_{G₂/₃} · g23_true                                     [Eq. 6, latent]
//   RI += β_{NO₃}  · log₁₀(no3_true)  [only 0 < NO₃ < cutoff]   [Eq. 7, latent]
// ═══════════════════════════════════════════════════════════════════════════════

data {
    // ─── Coretop (sediment) data ──────────────────────────────────────────────
    int<lower=1> N_crtp;
    vector[N_crtp] t_crtp;           // Modern instrumental temperature (°C)
    vector[N_crtp] proxyObs_crtp;    // Observed scaled Ring Index

    // ─── G₂/₃ ratio: observed values + per-site measurement SEs ─────────────
    // N_g23 = N_crtp when use_gdgt23ratio = 1; N_g23 = 0 when not used.
    // Zero-length parameter arrays are valid in Stan and eliminate wasted sampling
    // when a predictor is disabled. See Stan User's Guide, "Measurement Error and Meta-Analysis":
    // https://mc-stan.org/docs/stan-users-guide/measurement-error-and-meta-analysis.html
    int<lower=0> N_g23;
    vector[N_crtp] gdgt23ratio_crtp;              // observed G₂/₃ (used when N_g23 > 0)
    vector<lower=0>[N_crtp] sd_gdgt23ratio_crtp;  // per-site SE of G₂/₃ (linear scale)
    int<lower=0, upper=1> use_gdgt23ratio;

    // ─── NO₃: observed values + per-site measurement SEs ─────────────────────
    // Latent log₁₀(NO₃) is estimated only at N_no3_valid sites where
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
    // (sd = 0 means measurement SE is unavailable; no EIV correction applied.)
    int<lower=0> N_no3_exact;
    array[N_no3_exact] int<lower=1, upper=N_crtp> no3_exact_idx;

    // ─── Stage-1 hyperpriors (culmeso posterior summary statistics) ───────────
    real prior_mean_t0;   real prior_sd_t0;
    real prior_mean_k;    real prior_sd_k;
    real prior_mean_b;    real prior_sd_b;
    real prior_mean_v;    real prior_sd_v;
}

parameters {
    // ─── Coretop generalized-logistic curve parameters ────────────────────────
    real<lower=10, upper=50>   t0_crtp;
    real<lower=0.01>           k_crtp;
    real<lower=0.1, upper=1.0> b_crtp;
    real<lower=0.1, upper=10>  v_crtp;

    // ─── Non-thermal correction coefficients ──────────────────────────────────
    real<lower=-1, upper=0>  beta_G23_crtp;
    real<lower=-1, upper=0>  beta_NO3_crtp;

    // ─── Residual RI observation noise ────────────────────────────────────────
    // Pure RI scatter only — predictor measurement errors are absorbed by the
    // latent variables below, not into this term.
    real<lower=0>  sigma_proxyObs_crtp;

    // ─── Latent true predictor values ─────────────────────────────────────────
    // g23_true[i]       : true G₂/₃ ratio at coretop site i  (length N_g23)
    // log10_no3_true[j] : true log₁₀(NO₃) at valid NO₃ site j  (length N_no3_valid)
    // Both may be zero-length when the corresponding predictor is not used.
    vector[N_g23]       g23_true;
    vector[N_no3_valid] log10_no3_true;
}

model {
    // ─── 1. Stage-1 hyperpriors ───────────────────────────────────────────────
    t0_crtp ~ normal(prior_mean_t0, prior_sd_t0);
    k_crtp  ~ normal(prior_mean_k,  prior_sd_k);
    b_crtp  ~ normal(prior_mean_b,  prior_sd_b);
    v_crtp  ~ normal(prior_mean_v,  prior_sd_v);

    beta_G23_crtp       ~ normal(0, 0.05);
    beta_NO3_crtp       ~ normal(-0.064, 0.008); // non-zero center essential: zero-centered prior
                                                  // + latent vars causes MORE attenuation, not less
                                                  // (latent vars absorb residuals that would otherwise
                                                  // pull beta negative). Matches _odr and _eiv models.
    sigma_proxyObs_crtp ~ normal(0, 0.1);

    // ─── 2. Measurement models for latent predictors ──────────────────────────
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

    // ─── 3. Structural equation: calibration curve mean using LATENT values ───
    //
    // Conditioning on X_true rather than X_obs removes the attenuation bias in β:
    // the posterior of β_{NO₃} is more negative (stronger) than in the naive model.
    // Ref: Carroll et al. (2006), Chap. 2 (attenuation bias), Chap. 7 (Bayesian solution).
    //
    vector[N_crtp] mu = b_crtp + (1 - b_crtp)
        ./ pow(1 + exp(-k_crtp * (t_crtp - t0_crtp)), 1.0 / v_crtp);

    if (N_g23 > 0)
        mu += beta_G23_crtp * g23_true;       // latent true G₂/₃, not X_obs

    for (j in 1:N_no3_valid) {
        int i = no3_valid_idx[j];
        mu[i] += beta_NO3_crtp * log10_no3_true[j];  // latent true log₁₀(NO₃)
    }
    // Exact sites (sd_no3 = 0): SE unknown, use observed value directly.
    for (j in 1:N_no3_exact) {
        int i = no3_exact_idx[j];
        mu[i] += beta_NO3_crtp * log10(no3_crtp[i]);
    }

    // ─── 4. Likelihood — homoscedastic pure RI scatter ────────────────────────
    //
    // Predictor measurement errors are absorbed into the latent variable posteriors
    // above, so the likelihood is homoscedastic. sigma_proxyObs_crtp is therefore
    // the irreducible RI residual — typically SMALLER than in the naive model because
    // part of the residual scatter is now attributed to predictor noise.
    //
    proxyObs_crtp ~ normal(mu, sigma_proxyObs_crtp);
}

generated quantities {
    // R2_full     : frequentist 1 − RSS/TSS  (evaluated at posterior latent predictor means)
    // bayesR2_full: Gelman et al. (2019) var(μ) / (var(μ) + σ²_RI)
    //               Homoscedastic model → denominator is σ²_proxyObs_crtp.
    // RMSE_full   : root-mean-square error at observed proxy values.
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
