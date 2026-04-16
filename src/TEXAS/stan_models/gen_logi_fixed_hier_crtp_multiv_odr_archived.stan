// ═══════════════════════════════════════════════════════════════════════════════
// gen_logi_fixed_hier_crtp_multiv_odr.stan
//
// PURPOSE: Full hierarchical Bayesian forward calibration (culture + mesocosm
//          + coretop jointly) with Bayesian error-in-variables (EIV) treatment
//          of the secondary non-thermal predictors (G₂/₃ ratio and/or NO₃).
//          Extends gen_logi_fixed_hier_crtp_multiv.stan.
//
// ERROR-IN-VARIABLES TREATMENT:
//   Per-site measurement SEs for gdgt23ratio and NO₃ are propagated analytically
//   into the effective per-site residual SD of the coretop likelihood
//   (heteroscedastic likelihood). Culture and mesocosm likelihoods are
//   unaffected because those datasets carry no secondary predictors.
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
//   Heteroscedastic coretop likelihood per site i:
//     σ²_eff[i] = σ²_proxyObs_crtp
//               + β²_{G₂/₃} · σ²_{G₂/₃}[i]        (if use_gdgt23ratio = 1)
//               + β²_{NO₃}  · σ²_log10[i]           (if use_no3 = 1 & in range)
//     RI[i] ~ Normal(μ[i], σ_eff[i])
//
// MODEL DESIGN (same as gen_logi_fixed_hier_crtp_multiv.stan):
//   Two-group hierarchy: culture+mesocosm data constrain the SHAPE of the RI–T
//   curve; coretop parameters are drawn from hierarchical priors centered on the
//   culmeso estimates (partial pooling). Non-thermal corrections applied to
//   coretop data only.
//
// CALIBRATION CURVE — generalized logistic (Richards, upper asymptote = 1, Q = 1):
//   RI = b + (1 - b) / (1 + exp(-k · (T - T₀)))^(1/ν)            [Eq. 1]
//
// NON-THERMAL CORRECTIONS (if enabled, coretop only):
//   RI += β_{G₂/₃} · gdgt23ratio                                  [Eq. 6]
//   RI += β_{NO₃}  · log₁₀(NO₃)   [only where 0 < NO₃ < cutoff] [Eq. 7]
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
    real<lower=0>  sigma_proxyObs_crtp;  // "pure" RI scatter (predictor SEs separate)
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
    beta_NO3_crtp ~ normal(0, 0.05);

    // ─── 6. Coretop calibration curve mean ───────────────────────────────────
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

    // ─── 7. ODR: predictor-error propagation into heteroscedastic σ_eff ───────
    //
    // σ²_eff[i] = σ²_proxyObs_crtp          (pure RI noise, homoscedastic)
    //           + β²_{G₂/₃} · σ²_{G₂/₃}[i] (G23 error, exact for linear term)
    //           + β²_{NO₃} · (σ_{NO₃}[i] / (no3[i] · ln10))²
    //                                        (NO3 error, delta-method for log term)
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
