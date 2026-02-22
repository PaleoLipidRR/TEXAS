// ═══════════════════════════════════════════════════════════════════════════════
// gen_logi_fixed_hier_crtp_multiv.stan
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
// CALIBRATION CURVE — generalized logistic (Richards, upper asymptote fixed = 1):
//   RI = b + (1 - b) / (1 + Q · exp(-k · (T - T₀)))^(1/ν)    [Eq. 1]
//
// NON-THERMAL CORRECTIONS (if enabled, coretop only):
//   RI += β_{G₂/₃} · (gdgt23ratio)                            [Eq. 6]
//   RI += β_{NO₃}  · log₁₀(NO₃)   [only where 0 < NO₃ < cutoff]  [Eq. 7]
// ═══════════════════════════════════════════════════════════════════════════════

data {
    // ─── Culture data ─────────────────────────────────────────────────────────
    int<lower=1> N_cul;
    vector[N_cul] t_cul;           // Known temperature for each culture experiment (°C)
    vector[N_cul] scaledRI_cul;    // Observed scaled Ring Index (∈ [0,1])

    // ─── Mesocosm data ────────────────────────────────────────────────────────
    int<lower=1> N_meso;
    vector[N_meso] t_meso;         // Known temperature for each mesocosm experiment (°C)
    vector[N_meso] scaledRI_meso;

    // ─── Coretop (sediment) data ──────────────────────────────────────────────
    int<lower=1> N_crtp;
    vector[N_crtp] t_crtp;         // Modern instrumental temperature at each site (°C)
    vector[N_crtp] scaledRI_crtp;  // Observed scaled Ring Index from sediment

    // ─── Optional non-thermal predictors (coretop only) ───────────────────────
    // Flags (0 or 1) control whether each correction is applied in the model.
    vector[N_crtp] gdgt23ratio_crtp;
    int<lower=0, upper=1> use_gdgt23ratio;

    vector[N_crtp] no3_crtp;       // Nitrate concentration (μmol/L)
    int<lower=0, upper=1> use_no3;
    real no3_cutoff;               // Threshold: NO₃ correction applied below this value
}

parameters {
    // ─── Generalized-logistic curve parameters (culture + mesocosm) ───────────
    // These describe the shape of the RI–T relationship.
    // Eq. 1: RI = b + (1 - b) / (1 + Q · exp(-k · (T - T₀)))^(1/ν)
    //
    // NOTE: T₀ is NOT the inflection point of the curve in general —
    //   it is the reference temperature where the logistic term equals 1/(1+Q)^(1/ν).
    //   Q and ν together shift and skew the inflection away from T₀.
    real<lower=10, upper=50>  t0_culmeso;  // T₀: reference (center) temperature (°C)
    real<lower=0, upper=1>    k_culmeso;   // k: steepness of the RI–T slope
    real<lower=0, upper=1>    b_culmeso;   // b: lower asymptote (RI at very cold T)
    real<lower=0.01>          Q_culmeso;   // Q: asymmetry; Q=1 → standard logistic
    real<lower=0.1>           v_culmeso;   // ν: shape; ν=1 → symmetric logistic

    // ─── Coretop curve parameters (hierarchically linked to culmeso) ──────────
    // Each parameter is drawn from a normal centered on the culmeso value
    // (see hierarchical priors in the model block). This "partial pooling"
    // regularizes coretop estimates when data are sparse.
    real<lower=10, upper=50>  t0_crtp;
    real<lower=0, upper=1>    k_crtp;
    real<lower=0, upper=1>    b_crtp;
    real<lower=0.01>          Q_crtp;
    real<lower=0.1>           v_crtp;

    // ─── Non-thermal regression coefficients (coretop only) ───────────────────
    // Bounded negative: these correct for warm bias in RI.
    real<lower=-1, upper=0>   beta_G23_crtp;  // β_{G₂/₃}: ecology correction coefficient
    real<lower=-1, upper=0>   beta_NO3_crtp;  // β_{NO₃}: nutrient correction coefficient

    // ─── Hierarchical scale parameters (hyperparameters) ──────────────────────
    // Controls how much each coretop parameter can deviate from its culmeso mean.
    // Large sigma → weak pooling (coretop data dominant).
    // Small sigma → strong pooling (culmeso data dominant).
    // These are inferred from data, so the model learns the appropriate balance.
    real<lower=0>  sigma_t0_culmeso;
    real<lower=0>  sigma_k_culmeso;
    real<lower=0>  sigma_b_culmeso;
    real<lower=0>  sigma_Q_culmeso;
    real<lower=0>  sigma_v_culmeso;

    // ─── Residual observation noise ───────────────────────────────────────────
    // Captures RI variability not explained by temperature (or ecology corrections).
    real<lower=0>  sigma_scaledRI_cul;
    real<lower=0>  sigma_scaledRI_meso;
    real<lower=0>  sigma_scaledRI_crtp;
}

model {
    // ─── 1. Priors for culmeso curve parameters ───────────────────────────────
    // Weakly informative: broad enough to let data dominate, but anchored to
    // the known range of the RI–T relationship.
    t0_culmeso ~ normal(30, 10) T[10, 50];  // Truncated to match declared bounds
    k_culmeso  ~ beta(2, 5);
    b_culmeso  ~ beta(2, 5);
    Q_culmeso  ~ normal(1, 30) T[0, ];       // Half-normal: Q must be > 0
    v_culmeso  ~ normal(1, 10) T[0, ];       // Half-normal: ν must be > 0

    // ─── 2. Hyperpriors for hierarchical scale parameters ─────────────────────
    // Half-normal (truncated at 0): scales must be positive; penalize very
    // large deviations to prevent complete independence of the two data groups.
    sigma_t0_culmeso ~ normal(0, 5)   T[0, ];
    sigma_k_culmeso  ~ normal(0, 0.2) T[0, ];
    sigma_b_culmeso  ~ normal(0, 0.2) T[0, ];
    sigma_Q_culmeso  ~ normal(0, 2)   T[0, ];
    sigma_v_culmeso  ~ normal(0, 2)   T[0, ];

    // ─── 3. Priors for residual noise ─────────────────────────────────────────
    sigma_scaledRI_cul  ~ normal(0.01, 0.1);
    sigma_scaledRI_meso ~ normal(0.01, 0.1);

    // ─── 4. Likelihood for culture + mesocosm data ────────────────────────────
    // Compute expected RI at each known temperature using the Richards curve.
    // Vectorized: Stan evaluates all N_cul / N_meso points in one expression.
    vector[N_cul] mu_scaledRI_cul = b_culmeso + (1 - b_culmeso)
        ./ pow(1 + Q_culmeso * exp(-k_culmeso * (t_cul - t0_culmeso)), 1.0 / v_culmeso);
    vector[N_meso] mu_scaledRI_meso = b_culmeso + (1 - b_culmeso)
        ./ pow(1 + Q_culmeso * exp(-k_culmeso * (t_meso - t0_culmeso)), 1.0 / v_culmeso);

    scaledRI_cul  ~ normal(mu_scaledRI_cul,  sigma_scaledRI_cul);
    scaledRI_meso ~ normal(mu_scaledRI_meso, sigma_scaledRI_meso);

    // ─── 5. Hierarchical priors linking coretop parameters to culmeso ─────────
    // Each coretop parameter is drawn from a normal centered on the culmeso
    // estimate: crtp_param ~ Normal(culmeso_param, sigma_culmeso).
    // Truncation mirrors the bounds in the parameters block.
    // This is the key "borrowing strength" step: coretop estimates are pulled
    // toward the lab calibration shape, reducing overfitting to sparse coretop data.
    t0_crtp ~ normal(t0_culmeso, sigma_t0_culmeso) T[10, 50];
    k_crtp  ~ normal(k_culmeso,  sigma_k_culmeso)  T[0, 1];
    b_crtp  ~ normal(b_culmeso,  sigma_b_culmeso)  T[0, 1];
    Q_crtp  ~ normal(Q_culmeso,  sigma_Q_culmeso)  T[0.01, ];
    v_crtp  ~ normal(v_culmeso,  sigma_v_culmeso)  T[0.1, ];

    // Tight priors on correction coefficients (expected small effect sizes).
    beta_G23_crtp ~ normal(0, 0.05);
    beta_NO3_crtp ~ normal(0, 0.05);

    // ─── 6. Likelihood for coretop data (with optional non-thermal corrections) ─
    //
    // Step A: Base thermal term — vectorized over all N_crtp sites at once.
    //   Computes the Richards curve at each measured temperature.
    vector[N_crtp] mu_scaledRI_crtp = b_crtp + (1 - b_crtp)
        ./ pow(1 + Q_crtp * exp(-k_crtp * (t_crtp - t0_crtp)), 1.0 / v_crtp);

    // Step B: Ecology correction (if enabled) — add β_{G₂/₃} × gdgt23ratio.
    //   Fully vectorized (element-wise multiply, no loop needed).
    if (use_gdgt23ratio == 1)
        mu_scaledRI_crtp += beta_G23_crtp * gdgt23ratio_crtp;

    // Step C: NO₃ correction (if enabled) — add β_{NO₃} × log₁₀(NO₃).
    //   Requires a loop because the threshold condition (0 < NO₃ < cutoff)
    //   must be checked for each site individually.
    if (use_no3 == 1) {
        for (i in 1:N_crtp) {
            if (no3_crtp[i] > 0 && no3_crtp[i] < no3_cutoff)
                mu_scaledRI_crtp[i] += beta_NO3_crtp * log10(no3_crtp[i]);
        }
    }

    sigma_scaledRI_crtp ~ normal(0.01, 0.1);
    scaledRI_crtp ~ normal(mu_scaledRI_crtp, sigma_scaledRI_crtp);
}
