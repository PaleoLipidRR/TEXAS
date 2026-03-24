// ═══════════════════════════════════════════════════════════════════════════════
// gen_logi_fixed_hier_crtp_multiv_no3ratio.stan
//
// PURPOSE: Hierarchical Bayesian forward calibration.
//          Fits a generalized logistic (Richards) curve to culture, mesocosm,
//          AND coretop data jointly. This is the PRIMARY forward calibration
//          model in TEXAS-PSM.
//
// MODEL DESIGN:
//   Two-group hierarchy: culture+mesocosm (culmeso) data constrain the
//   SHAPE of the RI–T curve; coretop (crtp) parameters are drawn from
//   hierarchical priors centered on the culmeso estimates (partial pooling).
//   Optional ecology corrections are applied to coretop data only.
//
// CALIBRATION CURVE — generalized logistic (Richards, upper asymptote fixed = 1, Q fixed = 1):
//   RI = b + (1 - b) / (1 + exp(-k · (T - T₀)))^(1/ν)    [Eq. 1]
//
// NON-THERMAL CORRECTIONS (if enabled, coretop only):
//   RI += β_{G₂/₃} · (gdgt23ratio)                                          [Eq. 6]
//   RI += β_{NO₃}  · log₁₀(NO₃ / no3_cutoff)  [only where 0 < NO₃ < cutoff] [Eq. 7c]
//
// DIFFERENCE FROM gen_logi_fixed_hier_crtp_multiv.stan:
//   The NO₃ correction uses log₁₀(NO₃ / no3_cutoff) instead of log₁₀(NO₃).
//   This centres the correction at zero exactly at the threshold, ensuring
//   continuity: correction = 0 when NO₃ = no3_cutoff, and becomes increasingly
//   negative as NO₃ → 0. There is no discontinuous jump at the cutoff boundary.
//   β_{NO₃} retains the same magnitude (centering does not change the slope).
// ═══════════════════════════════════════════════════════════════════════════════

data {
    // ─── Culture data ─────────────────────────────────────────────────────────
    int<lower=1> N_cul;
    vector[N_cul] t_cul;           // Known temperature for each culture experiment (°C)
    vector[N_cul] proxy_param_cul;    // Observed scaled Ring Index (∈ [0,1])

    // ─── Mesocosm data ────────────────────────────────────────────────────────
    int<lower=1> N_meso;
    vector[N_meso] t_meso;         // Known temperature for each mesocosm experiment (°C)
    vector[N_meso] proxy_param_meso;

    // ─── Coretop (sediment) data ──────────────────────────────────────────────
    int<lower=1> N_crtp;
    vector[N_crtp] t_crtp;         // Modern instrumental temperature at each site (°C)
    vector[N_crtp] proxy_param_crtp;  // Observed scaled Ring Index from sediment

    // ─── Optional non-thermal predictors (coretop only) ───────────────────────
    // Flags (0 or 1) control whether each correction is applied in the model.
    vector[N_crtp] gdgt23ratio_crtp;
    int<lower=0, upper=1> use_gdgt23ratio;

    vector[N_crtp] no3_crtp;       // Nitrate concentration (μmol/L)
    int<lower=0, upper=1> use_no3;
    real<lower=0> no3_cutoff;      // Threshold: NO₃ correction applied below this value
}

parameters {
    // ─── Generalized-logistic curve parameters (culture + mesocosm) ───────────
    real<lower=10, upper=50>  t0_culmeso;
    real<lower=0, upper=0.5>  k_culmeso;
    real<lower=0, upper=1>    b_culmeso;
    real<lower=0.1>           v_culmeso;

    // ─── Coretop curve parameters (hierarchically linked to culmeso) ──────────
    real<lower=10, upper=50>  t0_crtp;
    real<lower=0, upper=0.5>  k_crtp;
    real<lower=0, upper=1>    b_crtp;
    real<lower=0.1>           v_crtp;

    // ─── Non-thermal regression coefficients (coretop only) ───────────────────
    real<lower=-1, upper=0>   beta_G23_crtp;
    real<lower=-1, upper=0>   beta_NO3_crtp;

    // ─── Hierarchical scale parameters (hyperparameters) ──────────────────────
    real<lower=0>  sigma_t0_culmeso;
    real<lower=0>  sigma_k_culmeso;
    real<lower=0>  sigma_b_culmeso;
    real<lower=0>  sigma_v_culmeso;

    // ─── Residual observation noise ───────────────────────────────────────────
    real<lower=0>  sigma_proxy_param_cul;
    real<lower=0>  sigma_proxy_param_meso;
    real<lower=0>  sigma_proxy_param_crtp;
}

model {
    // ─── 1. Priors for culmeso curve parameters ───────────────────────────────
    t0_culmeso ~ normal(30, 10) T[10, 50];
    k_culmeso  ~ normal(0, 1) T[0, 0.5];
    b_culmeso  ~ beta(2, 5);
    v_culmeso  ~ normal(0, 10) T[0.1, ];

    // ─── 2. Hyperpriors for hierarchical scale parameters ─────────────────────
    sigma_t0_culmeso ~ normal(0, 5)   T[0, ];
    sigma_k_culmeso  ~ normal(0, 0.2) T[0, ];
    sigma_b_culmeso  ~ normal(0, 0.2) T[0, ];
    sigma_v_culmeso  ~ normal(0, 2)   T[0, ];

    // ─── 3. Priors for residual noise ─────────────────────────────────────────
    sigma_proxy_param_cul  ~ normal(0.01, 0.1);
    sigma_proxy_param_meso ~ normal(0.01, 0.1);

    // ─── 4. Likelihood for culture + mesocosm data ────────────────────────────
    vector[N_cul] mu_proxy_param_cul = b_culmeso + (1 - b_culmeso)
        ./ pow(1 + exp(-k_culmeso * (t_cul - t0_culmeso)), 1.0 / v_culmeso);
    vector[N_meso] mu_proxy_param_meso = b_culmeso + (1 - b_culmeso)
        ./ pow(1 + exp(-k_culmeso * (t_meso - t0_culmeso)), 1.0 / v_culmeso);

    proxy_param_cul  ~ normal(mu_proxy_param_cul,  sigma_proxy_param_cul);
    proxy_param_meso ~ normal(mu_proxy_param_meso, sigma_proxy_param_meso);

    // ─── 5. Hierarchical priors linking coretop parameters to culmeso ─────────
    t0_crtp ~ normal(t0_culmeso, sigma_t0_culmeso) T[10, 50];
    k_crtp  ~ normal(k_culmeso,  sigma_k_culmeso)  T[0, 0.5];
    b_crtp  ~ normal(b_culmeso,  sigma_b_culmeso)  T[0, 1];
    v_crtp  ~ normal(v_culmeso,  sigma_v_culmeso)  T[0.1, ];

    beta_G23_crtp ~ normal(0, 0.05);
    beta_NO3_crtp ~ normal(0, 0.05);

    // ─── 6. Likelihood for coretop data (with optional non-thermal corrections) ─
    //
    // Step A: Base thermal term — vectorized over all N_crtp sites at once.
    vector[N_crtp] mu_proxy_param_crtp = b_crtp + (1 - b_crtp)
        ./ pow(1 + exp(-k_crtp * (t_crtp - t0_crtp)), 1.0 / v_crtp);

    // Step B: Ecology correction (if enabled) — vectorized element-wise multiply.
    if (use_gdgt23ratio == 1)
        mu_proxy_param_crtp += beta_G23_crtp * gdgt23ratio_crtp;

    // Step C: NO₃ correction (if enabled) — loop required for threshold check.
    //   Uses log₁₀(NO₃ / no3_cutoff) so correction = 0 at the boundary (Eq. 7c).
    //   For NO₃ ∈ (0, no3_cutoff): log₁₀(ratio) < 0, and with β_{NO₃} < 0,
    //   the correction is positive (increases mu), reflecting the oligotrophic warm bias.
    if (use_no3 == 1) {
        for (i in 1:N_crtp) {
            if (no3_crtp[i] > 0 && no3_crtp[i] < no3_cutoff)
                mu_proxy_param_crtp[i] += beta_NO3_crtp * log10(no3_crtp[i] / no3_cutoff);
        }
    }

    sigma_proxy_param_crtp ~ normal(0.01, 0.1);
    proxy_param_crtp ~ normal(mu_proxy_param_crtp, sigma_proxy_param_crtp);
}
