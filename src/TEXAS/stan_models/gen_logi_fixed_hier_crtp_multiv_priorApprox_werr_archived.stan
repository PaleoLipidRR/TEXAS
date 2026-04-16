// ═══════════════════════════════════════════════════════════════════════════════
// gen_logi_fixed_hier_crtp_multiv_priorApprox_werr.stan
//
// PURPOSE: Coretop-only forward calibration with Bayesian error-in-variables
//          (EIV) treatment of the secondary non-thermal predictors (G₂/₃
//          ratio and/or NO₃). Extends the priorApprox model by accepting
//          known per-site measurement SEs for gdgt23ratio and NO₃ and
//          propagating them into the residual variance of the calibration
//          curve (heteroscedastic likelihood).
//
// ERROR-IN-VARIABLES TREATMENT:
//   Rather than introducing N_crtp latent "true predictor" parameters, we
//   propagate each SE analytically into the effective per-site residual SD:
//
//   G₂/₃ (linear term) — exact Gaussian error propagation:
//     Var[β_{G₂/₃} · g23_true[i]] = β²_{G₂/₃} · σ²_{G₂/₃}[i]
//
//   NO₃ (log₁₀ term) — first-order delta method:
//     d/d(no3)[β_{NO₃} · log₁₀(no3)] = β_{NO₃} / (no3 · ln 10)
//     propagated SE: σ_log10[i] = σ_{NO₃}[i] / (no3[i] · ln 10)
//     Var[β_{NO₃} · log₁₀(no3_true[i])] ≈ β²_{NO₃} · σ²_log10[i]
//     (applied only where 0 < NO₃[i] < no3_cutoff)
//
//   Heteroscedastic likelihood per site i:
//     σ²_eff[i] = σ²_proxyObs
//               + β²_{G₂/₃} · σ²_{G₂/₃}[i]        (if use_gdgt23ratio = 1)
//               + β²_{NO₃}  · σ²_log10[i]           (if use_no3 = 1 & in range)
//     RI[i] ~ Normal(μ[i], σ_eff[i])
//
//   σ_proxyObs is therefore the "irreducible" RI scatter — variability not
//   explained by T, G₂/₃, or NO₃ even if those predictors were measured
//   without error. It is expected to be smaller than in the no-error model.
//
// WORKFLOW (two-stage priorApprox):
//   Step 1: Run gen_logi_fixed_culmeso.stan → extract posterior mean/SD for
//           {t0, k, b, v} and pass as prior_mean_* / prior_sd_* inputs.
//   Step 2: This model fits only the coretop parameters conditional on those
//           priors, with predictor measurement errors explicitly accounted for.
//
// CALIBRATION CURVE — generalized logistic (Richards, upper asymptote = 1, Q = 1):
//   RI = b + (1 - b) / (1 + exp(-k · (T - T₀)))^(1/ν)            [Eq. 1]
//
// NON-THERMAL CORRECTIONS (if enabled):
//   RI += β_{G₂/₃} · gdgt23ratio                                  [Eq. 6]
//   RI += β_{NO₃}  · log₁₀(NO₃)   [only where 0 < NO₃ < cutoff] [Eq. 7]
// ═══════════════════════════════════════════════════════════════════════════════

data {
    // ─── Coretop (sediment) data ──────────────────────────────────────────────
    int<lower=1> N_crtp;
    vector[N_crtp] t_crtp;           // Modern instrumental temperature (°C)
    vector[N_crtp] proxyObs_crtp;    // Observed scaled Ring Index

    // ─── Non-thermal predictors with known per-site measurement SEs ───────────
    vector[N_crtp] gdgt23ratio_crtp;
    vector<lower=0>[N_crtp] sd_gdgt23ratio_crtp;  // SE of G₂/₃ per site (linear)
    int<lower=0, upper=1> use_gdgt23ratio;

    vector[N_crtp] no3_crtp;
    vector<lower=0>[N_crtp] sd_no3_crtp;           // SE of NO₃ per site (μmol/L, linear)
    int<lower=0, upper=1> use_no3;
    real no3_cutoff;
    // Precision cutoff: sites where cv(NO₃) = σ_{NO₃}/NO₃ exceeds this threshold
    // are excluded from both the mean correction and the variance propagation.
    // Rationale: the delta method σ_log10 = σ_{NO₃}/(NO₃·ln10) explodes when NO₃
    // is near zero, turning σ²_eff into an aggressive L₂ regularizer on β_{NO₃}
    // and causing extreme shrinkage toward zero. Typical value: 0.50 (50% CV).
    real<lower=0> no3_cv_threshold;

    // ─── Stage-1 hyperpriors (culmeso posterior summary statistics) ───────────
    real prior_mean_t0;   real prior_sd_t0;
    real prior_mean_k;    real prior_sd_k;
    real prior_mean_b;    real prior_sd_b;
    real prior_mean_v;    real prior_sd_v;
}

parameters {
    // ─── Coretop generalized-logistic curve parameters ────────────────────────
    // k has no upper cap: culmeso posterior mean (~0.57) can exceed 0.5.
    real<lower=10, upper=50>  t0_crtp;
    real<lower=0.01>          k_crtp;
    real<lower=0.1, upper=1.0> b_crtp;
    real<lower=0.1, upper=10>  v_crtp;

    // ─── Non-thermal correction coefficients ──────────────────────────────────
    real<lower=-1, upper=0>  beta_G23_crtp;
    real<lower=-1, upper=0>  beta_NO3_crtp;

    // ─── Residual observation noise (pure RI scatter, excluding predictor SEs) ─
    real<lower=0>  sigma_proxyObs_crtp;
}

model {
    // ─── 1. Stage-1 hyperpriors ───────────────────────────────────────────────
    t0_crtp ~ normal(prior_mean_t0, prior_sd_t0);
    k_crtp  ~ normal(prior_mean_k,  prior_sd_k);
    b_crtp  ~ normal(prior_mean_b,  prior_sd_b);
    v_crtp  ~ normal(prior_mean_v,  prior_sd_v);

    beta_G23_crtp       ~ normal(0, 0.05);
    beta_NO3_crtp       ~ normal(0, 0.05);
    sigma_proxyObs_crtp ~ normal(0, 0.1);

    // ─── 2. Calibration curve mean ────────────────────────────────────────────
    vector[N_crtp] mu_proxyObs_crtp = b_crtp + (1 - b_crtp)
        ./ pow(1 + exp(-k_crtp * (t_crtp - t0_crtp)), 1.0 / v_crtp);

    if (use_gdgt23ratio == 1)
        mu_proxyObs_crtp += beta_G23_crtp * gdgt23ratio_crtp;

    if (use_no3 == 1) {
        for (i in 1:N_crtp) {
            if (no3_crtp[i] > 0 && no3_crtp[i] < no3_cutoff && sd_no3_crtp[i] / no3_crtp[i] < no3_cv_threshold)
                mu_proxyObs_crtp[i] += beta_NO3_crtp * log10(no3_crtp[i]);
        }
    }

    // ─── 3. Heteroscedastic σ_eff via error propagation ───────────────────────
    //
    // Start from the pure RI noise, then add the contribution of each predictor's
    // measurement uncertainty propagated through its regression coefficient.
    //
    // G₂/₃ (linear):  β²_{G₂/₃} · σ²_{G₂/₃}[i]
    // NO₃  (log₁₀):   β²_{NO₃}  · (σ_{NO₃}[i] / (no3[i] · ln 10))²
    //
    vector[N_crtp] sigma_eff_sq = rep_vector(square(sigma_proxyObs_crtp), N_crtp);

    if (use_gdgt23ratio == 1)
        sigma_eff_sq += square(beta_G23_crtp) * square(sd_gdgt23ratio_crtp);

    if (use_no3 == 1) {
        for (i in 1:N_crtp) {
            if (no3_crtp[i] > 0 && no3_crtp[i] < no3_cutoff && sd_no3_crtp[i] / no3_crtp[i] < no3_cv_threshold) {
                real sd_log10_no3_i = sd_no3_crtp[i] / (no3_crtp[i] * log(10.0));
                sigma_eff_sq[i] += square(beta_NO3_crtp) * square(sd_log10_no3_i);
            }
        }
    }

    proxyObs_crtp ~ normal(mu_proxyObs_crtp, sqrt(sigma_eff_sq));
}

generated quantities {
    // R2_full     : frequentist 1 - RSS/TSS
    // bayesR2_full: Gelman et al. (2019) var(μ)/(var(μ) + mean(σ²_eff))
    //               Uses mean effective variance to account for heteroscedasticity.
    // RMSE_full   : root-mean-square error at observed predictor values.
    real R2_full;
    real bayesR2_full;
    real RMSE_full;

    {
        vector[N_crtp] mu = b_crtp + (1 - b_crtp)
            ./ pow(1 + exp(-k_crtp * (t_crtp - t0_crtp)), 1.0 / v_crtp);

        if (use_gdgt23ratio == 1)
            mu += beta_G23_crtp * gdgt23ratio_crtp;

        if (use_no3 == 1) {
            for (i in 1:N_crtp) {
                if (no3_crtp[i] > 0 && no3_crtp[i] < no3_cutoff && sd_no3_crtp[i] / no3_crtp[i] < no3_cv_threshold)
                    mu[i] += beta_NO3_crtp * log10(no3_crtp[i]);
            }
        }

        // Recompute σ²_eff (must match the model block computation exactly)
        vector[N_crtp] sigma_eff_sq = rep_vector(square(sigma_proxyObs_crtp), N_crtp);
        if (use_gdgt23ratio == 1)
            sigma_eff_sq += square(beta_G23_crtp) * square(sd_gdgt23ratio_crtp);
        if (use_no3 == 1) {
            for (i in 1:N_crtp) {
                if (no3_crtp[i] > 0 && no3_crtp[i] < no3_cutoff && sd_no3_crtp[i] / no3_crtp[i] < no3_cv_threshold) {
                    real sd_log10_no3_i = sd_no3_crtp[i] / (no3_crtp[i] * log(10.0));
                    sigma_eff_sq[i] += square(beta_NO3_crtp) * square(sd_log10_no3_i);
                }
            }
        }

        vector[N_crtp] resid = proxyObs_crtp - mu;
        real ybar  = mean(proxyObs_crtp);
        real TSS   = dot_self(proxyObs_crtp - ybar);
        real RSS   = dot_self(resid);
        R2_full    = 1 - RSS / TSS;
        RMSE_full  = sqrt(RSS / N_crtp);

        real var_mu            = variance(mu);
        real mean_sigma_eff_sq = mean(sigma_eff_sq);
        bayesR2_full = var_mu / (var_mu + mean_sigma_eff_sq);
    }
}
