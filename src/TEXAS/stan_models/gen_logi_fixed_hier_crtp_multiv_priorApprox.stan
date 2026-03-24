// ═══════════════════════════════════════════════════════════════════════════════
// gen_logi_fixed_hier_crtp_multiv_priorApprox.stan
//
// PURPOSE: Coretop-only forward calibration using pre-computed hyperpriors.
//          This is the Stage-2 model in the two-stage calibration workflow.
//
// HOW IT RELATES TO THE FULL HIERARCHICAL MODEL:
//   Instead of fitting culture + mesocosm + coretop data jointly (as in
//   gen_logi_fixed_hier_crtp_multiv.stan), this model uses SUMMARY STATISTICS
//   from the culmeso posterior as fixed hyperpriors for the coretop parameters.
//   This is an approximation of the full hierarchical model that is faster to
//   run and allows the coretop stage to be re-run independently.
//
//   Workflow:
//     Step 1: Run gen_logi_fixed_culmeso.stan → get posterior means/SDs
//             of {t0, k, b, v} (e.g., via extract_and_update_metadata)
//     Step 2: Pass those summary statistics as prior_mean_* / prior_sd_* inputs
//     Step 3: This model fits only the coretop parameters conditional on those priors
//
// CALIBRATION CURVE — generalized logistic (Richards, upper asymptote fixed = 1, Q fixed = 1):
//   RI = b + (1 - b) / (1 + exp(-k · (T - T₀)))^(1/ν)    [Eq. 1]
//
// NON-THERMAL CORRECTIONS (if enabled):
//   RI += β_{G₂/₃} · (gdgt23ratio)                            [Eq. 6]
//   RI += β_{NO₃}  · log₁₀(NO₃)   [only where 0 < NO₃ < cutoff]  [Eq. 7]
// ═══════════════════════════════════════════════════════════════════════════════

data {
    // ─── Coretop (sediment) data ──────────────────────────────────────────────
    int<lower=1> N_crtp;
    vector[N_crtp] t_crtp;         // Modern instrumental temperature at each site (°C)
    vector[N_crtp] proxyObs_crtp;  // Observed scaled Ring Index from sediment

    // ─── Optional non-thermal predictors ──────────────────────────────────────
    vector[N_crtp] gdgt23ratio_crtp;
    int<lower=0, upper=1> use_gdgt23ratio;

    vector[N_crtp] no3_crtp;
    int<lower=0, upper=1> use_no3;
    real no3_cutoff;

    // ─── Hyperpriors from the culmeso posterior (Stage-1 summary statistics) ──
    // These replace the full culmeso likelihood. Each pair (mean, sd) defines
    // a normal prior on the corresponding coretop parameter, approximating
    // the hierarchical prior from the joint model.
    real prior_mean_t0;   real prior_sd_t0;
    real prior_mean_k;    real prior_sd_k;
    real prior_mean_b;    real prior_sd_b;
    real prior_mean_v;    real prior_sd_v;
}

parameters {
    // ─── Coretop generalized-logistic curve parameters ────────────────────────
    // Lower bounds reflect physical constraints; the hyperprior (from culmeso)
    // provides regularization above — no hard upper cap on k or v.
    real<lower=10, upper=50>  t0_crtp;  // T₀: reference temperature (°C)
    real<lower=0.01>          k_crtp;   // k: steepness (unbounded above, matching culmeso)
    real<lower=0.1,  upper=0.6>   b_crtp;   // b: lower asymptote
    real<lower=0.1>               v_crtp;   // ν: shape

    // ─── Non-thermal correction coefficients ──────────────────────────────────
    real<lower=-1, upper=0>  beta_G23_crtp;
    real<lower=-1, upper=0>  beta_NO3_crtp;

    // ─── Residual observation noise ───────────────────────────────────────────
    real<lower=0>  sigma_proxyObs_crtp;
}

model {
    // ─── 1. Priors from culmeso posterior (Stage-1 approximate hyperpriors) ───
    // Normal priors parameterized by the posterior mean and SD from the culmeso
    // model. This is the "prior approximation" that gives the model its name:
    // it approximates the full hierarchical prior with a simple normal summary.
    t0_crtp ~ normal(prior_mean_t0, prior_sd_t0);
    k_crtp  ~ normal(prior_mean_k,  prior_sd_k);
    b_crtp  ~ normal(prior_mean_b,  prior_sd_b);
    v_crtp  ~ normal(prior_mean_v,  prior_sd_v);

    beta_G23_crtp ~ normal(0, 0.05);
    beta_NO3_crtp ~ normal(0, 0.05);

    // ─── 2. Likelihood for coretop data ───────────────────────────────────────
    //
    // Step A: Base thermal term — vectorized over all N_crtp sites.
    vector[N_crtp] mu_proxyObs_crtp = b_crtp + (1 - b_crtp)
        ./ pow(1 + exp(-k_crtp * (t_crtp - t0_crtp)), 1.0 / v_crtp);

    // Step B: Ecology correction (if enabled) — vectorized element-wise multiply.
    if (use_gdgt23ratio == 1)
        mu_proxyObs_crtp += beta_G23_crtp * gdgt23ratio_crtp;

    // Step C: NO₃ correction (if enabled) — loop required for threshold condition.
    if (use_no3 == 1) {
        for (i in 1:N_crtp) {
            if (no3_crtp[i] > 0 && no3_crtp[i] < no3_cutoff)
                mu_proxyObs_crtp[i] += beta_NO3_crtp * log10(no3_crtp[i]);
        }
    }

    sigma_proxyObs_crtp ~ normal(0.01, 0.1);
    proxyObs_crtp ~ normal(mu_proxyObs_crtp, sigma_proxyObs_crtp);
}
