// ═══════════════════════════════════════════════════════════════════════════════
// gen_logi_fixed_hier_crtp_multiv_priorApprox_werr_ver2.stan
//
// PURPOSE: Coretop-only forward calibration with Bayesian error-in-variables
//          (EIV) on secondary predictors (G₂/₃, NO₃) AND explicit separation
//          of RI analytical measurement error from structural process noise.
//
// DIFFERENCES FROM _werr.stan (latent-variable priorApprox):
//   1. sd_proxyObs is passed per-site and enters the likelihood in quadrature:
//      total_sd = √(sd_proxyObs² + sigma_proxyObs_crtp²).
//      sigma_proxyObs_crtp is therefore the PROCESS noise only (oceanographic
//      scatter, bioturbation, model misfit) — not total RI scatter.
//   2. sigma prior is scaled to the residual SE after the thermal curve:
//      sigma ~ N(0, mean(sd_proxyObs) · √(1 − R²_thermal)).
//   3. NO₃ latent variable uses a lognormal prior on the LINEAR scale and a
//      normal measurement model (no delta-method approximation). All N_crtp
//      latent NO₃ values are sampled; sites outside (0, no3_cutoff) receive
//      only the prior (no likelihood update).
//   4. CV-gating is NOT implemented here (unlike _werr.stan). All sub-threshold
//      sites receive the EIV measurement model regardless of SE/NO₃ ratio.
//      build_fwd_data() still supplies the EIV index arrays for _werr.stan
//      compatibility but they are not used by this model.
//
// WORKFLOW (two-stage priorApprox):
//   Step 1: Run gen_logi_fixed_culmeso.stan → extract posterior mean/SD for
//           {t0, k, b, v}; also compute R²_thermal from a thermal-only
//           coretop run and pass as R2_thermal.
//   Step 2: This model fits only the coretop parameters.
//
// CALIBRATION CURVE — generalized logistic (Richards, upper asymptote = 1, Q = 1):
//   RI = b + (1 − b) / (1 + exp(−k · (T − T₀)))^(1/ν)            [Eq. 1]
//
// NON-THERMAL CORRECTIONS (if enabled):
//   RI += β_{G₂/₃} · g23_true                                     [Eq. 6]
//   RI += β_{NO₃}  · log₁₀(no3_true)  [only 0 < NO₃ < cutoff]   [Eq. 7]
// ═══════════════════════════════════════════════════════════════════════════════

data {
    // ─── Coretop (sediment) data ──────────────────────────────────────────────
    int<lower=1> N_crtp;
    vector[N_crtp] t_crtp;
    vector[N_crtp] proxyObs_crtp;
    vector<lower=0>[N_crtp] sd_proxyObs;      // Per-site analytical SE of RI (Rs ≈ 0.03,
                                               // Schouten et al. 2013).

    // ─── Optional non-thermal predictors ──────────────────────────────────────
    vector[N_crtp] gdgt23ratio_crtp;
    vector<lower=0>[N_crtp] sd_gdgt23ratio_crtp;  // per-site SE of G₂/₃ (linear scale)
    int<lower=0, upper=1> use_gdgt23ratio;

    vector[N_crtp] no3_crtp;
    vector<lower=0>[N_crtp] sd_no3_crtp;          // per-site SE of NO₃ (µmol/L, linear)
    int<lower=0, upper=1> use_no3;
    real no3_cutoff;

    // ─── Stage-1 hyperpriors (culmeso posterior summary statistics) ───────────
    real prior_mean_t0;   real prior_sd_t0;
    real prior_mean_k;    real prior_sd_k;
    real prior_mean_b;    real prior_sd_b;
    real prior_mean_v;    real prior_sd_v;

    // ─── Thermal R² from a thermal-only preliminary fit ───────────────────────
    // Pre-compute in Python as the R² of a thermal-only (no G23, no NO3) run
    // on the same coretop data, then pass as R2_thermal to build_fwd_data().
    // Used only to scale the half-normal prior on sigma_proxyObs_crtp.
    real<lower=0, upper=1> R2_thermal;
}

// ─── Pre-compute residual SE scale ────────────────────────────────────────────
// proxyObs_res_se ≈ mean(sd_proxyObs) · √(1 − R²_thermal)
// Used as the scale of the half-normal prior on sigma_proxyObs_crtp.
// sd_proxyObs still enters the likelihood directly — this is prior scaling only.
transformed data {
    real mean_sd_proxyObs = mean(sd_proxyObs);
    real proxyObs_res_se  = mean_sd_proxyObs * sqrt(1.0 - R2_thermal);
}

parameters {
    // ─── Coretop generalized-logistic curve parameters ────────────────────────
    real<lower=10, upper=50>   t0_crtp;
    real<lower=0.01>           k_crtp;       // no upper bound: culmeso posterior mean ≈ 0.57
    real<lower=0.1, upper=1.0> b_crtp;
    real<lower=0.1, upper=10>  v_crtp;

    // ─── Non-thermal correction coefficients ──────────────────────────────────
    real<lower=-1, upper=0> beta_G23_crtp;
    real<lower=-1, upper=0> beta_NO3_crtp;

    // ─── Residual process noise (beyond analytical measurement error) ─────────
    // sigma_proxyObs_crtp is structural residual ONLY.
    // Total RI SD = √(sd_proxyObs² + sigma_proxyObs_crtp²).
    real<lower=0> sigma_proxyObs_crtp;

    // ─── Latent true predictor values ─────────────────────────────────────────
    // G₂/₃: Gaussian measurement model on linear scale.
    // NO₃:  lognormal prior on linear scale; normal measurement model at valid
    //       sites (0 < NO₃ < no3_cutoff). Sampled for all N_crtp sites;
    //       above-threshold sites receive only the prior (no likelihood update).
    //       Upper bound = no3_cutoff prevents exp() overflow during HMC leapfrog
    //       (unconstrained param α = log(true_no3); without an upper cap, α can
    //       wander past ~710 → exp(710) = Inf in double precision).
    vector[N_crtp]                        true_gdgt23ratio_crtp;
    vector<lower=0, upper=no3_cutoff>[N_crtp] true_no3_crtp;
}

model {
    // ─── 1. Stage-1 hyperpriors ───────────────────────────────────────────────
    t0_crtp ~ normal(prior_mean_t0, prior_sd_t0);
    k_crtp  ~ normal(prior_mean_k,  prior_sd_k);
    b_crtp  ~ normal(prior_mean_b,  prior_sd_b);
    v_crtp  ~ normal(prior_mean_v,  prior_sd_v);

    beta_G23_crtp       ~ normal(0,      0.05);
    beta_NO3_crtp       ~ normal(-0.064, 0.008);  // informative: zero-centered prior + latent vars
                                                   // causes MORE attenuation (latent vars absorb
                                                   // residuals rather than moving beta negative).
    sigma_proxyObs_crtp ~ normal(0, proxyObs_res_se);

    // ─── 2. EIV: G₂/₃ ratio ──────────────────────────────────────────────────
    if (use_gdgt23ratio == 1) {
        true_gdgt23ratio_crtp ~ normal(0, 2);
        gdgt23ratio_crtp      ~ normal(true_gdgt23ratio_crtp, sd_gdgt23ratio_crtp);
    } else {
        true_gdgt23ratio_crtp ~ normal(0, 2);
    }

    // ─── 3. EIV: NO₃ concentration ───────────────────────────────────────────
    // Lognormal prior centered near sub-threshold typical values (median 0.3 µM).
    // Normal measurement model at sites with 0 < NO₃_obs < no3_cutoff.
    if (use_no3 == 1) {
        true_no3_crtp ~ lognormal(log(0.3), 1.0);
        for (i in 1:N_crtp) {
            if (no3_crtp[i] > 0 && no3_crtp[i] < no3_cutoff && sd_no3_crtp[i] > 0)
                no3_crtp[i] ~ normal(true_no3_crtp[i], sd_no3_crtp[i]);
            // sd_no3_crtp[i] == 0 → no measurement model; true_no3_crtp[i] receives
            // only the lognormal prior (same effect as treating the site as "exact" in _werr.stan).
        }
    } else {
        true_no3_crtp ~ lognormal(log(0.3), 1.0);
    }

    // ─── 4. Likelihood ────────────────────────────────────────────────────────
    vector[N_crtp] mu = b_crtp + (1.0 - b_crtp)
        ./ pow(1.0 + exp(-k_crtp * (t_crtp - t0_crtp)), 1.0 / v_crtp);

    if (use_gdgt23ratio == 1)
        mu += beta_G23_crtp * true_gdgt23ratio_crtp;

    if (use_no3 == 1) {
        for (i in 1:N_crtp) {
            if (no3_crtp[i] > 0 && no3_crtp[i] < no3_cutoff)
                mu[i] += beta_NO3_crtp * log10(true_no3_crtp[i]);
        }
    }

    // Analytical measurement error (sd_proxyObs) and process noise
    // (sigma_proxyObs_crtp) combined in quadrature.
    vector[N_crtp] total_sd = sqrt(square(sd_proxyObs) + square(sigma_proxyObs_crtp));
    proxyObs_crtp ~ normal(mu, total_sd);
}

generated quantities {
    real R2_full;
    real bayesR2_full;
    real RMSE_full;

    {
        vector[N_crtp] mu = b_crtp + (1.0 - b_crtp)
            ./ pow(1.0 + exp(-k_crtp * (t_crtp - t0_crtp)), 1.0 / v_crtp);

        if (use_gdgt23ratio == 1)
            mu += beta_G23_crtp * true_gdgt23ratio_crtp;

        if (use_no3 == 1) {
            for (i in 1:N_crtp) {
                if (no3_crtp[i] > 0 && no3_crtp[i] < no3_cutoff)
                    mu[i] += beta_NO3_crtp * log10(true_no3_crtp[i]);
            }
        }

        vector[N_crtp] resid = proxyObs_crtp - mu;
        real ybar    = mean(proxyObs_crtp);
        real TSS     = dot_self(proxyObs_crtp - ybar);
        real RSS     = dot_self(resid);
        R2_full      = 1.0 - RSS / TSS;
        RMSE_full    = sqrt(RSS / N_crtp);

        // bayesR2 uses process noise only (sigma²), not total_sd²,
        // because sd_proxyObs is fixed known measurement error.
        real var_mu  = variance(mu);
        bayesR2_full = var_mu / (var_mu + square(sigma_proxyObs_crtp));
    }
}
