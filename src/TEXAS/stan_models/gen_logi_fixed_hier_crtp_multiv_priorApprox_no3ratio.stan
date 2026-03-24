// ═══════════════════════════════════════════════════════════════════════════════
// gen_logi_fixed_hier_crtp_multiv_priorApprox_no3ratio.stan
//
// PURPOSE: Coretop-only forward calibration using pre-computed hyperpriors.
//          This is the Stage-2 model in the two-stage calibration workflow.
//
// HOW IT RELATES TO THE FULL HIERARCHICAL MODEL:
//   Instead of fitting culture + mesocosm + coretop data jointly (as in
//   gen_logi_fixed_hier_crtp_multiv_no3ratio.stan), this model uses SUMMARY
//   STATISTICS from the culmeso posterior as fixed hyperpriors for the coretop
//   parameters. This is an approximation of the full hierarchical model that is
//   faster to run and allows the coretop stage to be re-run independently.
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
//   RI += β_{G₂/₃} · (gdgt23ratio)                                          [Eq. 6]
//   RI += β_{NO₃}  · log₁₀(NO₃ / no3_cutoff)  [only where 0 < NO₃ < cutoff] [Eq. 7c]
//
// DIFFERENCE FROM gen_logi_fixed_hier_crtp_multiv_priorApprox.stan:
//   The NO₃ correction uses log₁₀(NO₃ / no3_cutoff) instead of log₁₀(NO₃).
//   This centres the correction at zero exactly at the threshold, ensuring
//   continuity: correction = 0 when NO₃ = no3_cutoff, and becomes increasingly
//   negative as NO₃ → 0. There is no discontinuous jump at the cutoff boundary.
//   β_{NO₃} retains the same magnitude (centering does not change the slope).
// ═══════════════════════════════════════════════════════════════════════════════

data {
    // ─── Coretop (sediment) data ──────────────────────────────────────────────
    int<lower=1> N_crtp;
    vector[N_crtp] t_crtp;         // Modern instrumental temperature at each site (°C)
    vector[N_crtp] proxy_param_crtp;  // Observed scaled Ring Index from sediment

    // ─── Optional non-thermal predictors ──────────────────────────────────────
    vector[N_crtp] gdgt23ratio_crtp;
    int<lower=0, upper=1> use_gdgt23ratio;

    vector[N_crtp] no3_crtp;
    int<lower=0, upper=1> use_no3;
    real<lower=0> no3_cutoff;

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
    real<lower=10, upper=50>      t0_crtp;
    real<lower=0.01, upper=0.5>   k_crtp;   // k: steepness
    real<lower=0.1,  upper=1.0>   b_crtp;   // b: lower asymptote (upper=1 matches joint model)
    real<lower=0.1>               v_crtp;

    // ─── Non-thermal correction coefficients ──────────────────────────────────
    real<lower=-1, upper=0>  beta_G23_crtp;
    real<lower=-1, upper=0>  beta_NO3_crtp;

    // ─── Residual observation noise ───────────────────────────────────────────
    real<lower=0>  sigma_proxy_param_crtp;
}

model {
    // ─── 1. Priors from culmeso posterior (Stage-1 approximate hyperpriors) ───
    t0_crtp ~ normal(prior_mean_t0, prior_sd_t0);
    k_crtp  ~ normal(prior_mean_k,  prior_sd_k);
    b_crtp  ~ normal(prior_mean_b,  prior_sd_b);
    v_crtp  ~ normal(prior_mean_v,  prior_sd_v);

    beta_G23_crtp ~ normal(0, 0.05);
    beta_NO3_crtp ~ normal(0, 0.05);

    // ─── 2. Likelihood for coretop data ───────────────────────────────────────
    //
    // Step A: Base thermal term — vectorized over all N_crtp sites.
    vector[N_crtp] mu_proxy_param_crtp = b_crtp + (1 - b_crtp)
        ./ pow(1 + exp(-k_crtp * (t_crtp - t0_crtp)), 1.0 / v_crtp);

    // Step B: Ecology correction (if enabled) — vectorized element-wise multiply.
    if (use_gdgt23ratio == 1)
        mu_proxy_param_crtp += beta_G23_crtp * gdgt23ratio_crtp;

    // Step C: NO₃ correction (if enabled) — loop required for threshold check.
    //   Uses log₁₀(NO₃ / no3_cutoff) so correction = 0 at the boundary (Eq. 7c).
    if (use_no3 == 1) {
        for (i in 1:N_crtp) {
            if (no3_crtp[i] > 0 && no3_crtp[i] < no3_cutoff)
                mu_proxy_param_crtp[i] += beta_NO3_crtp * log10(no3_crtp[i] / no3_cutoff);
        }
    }

    sigma_proxy_param_crtp ~ normal(0.01, 0.1);
    proxy_param_crtp ~ normal(mu_proxy_param_crtp, sigma_proxy_param_crtp);
}
