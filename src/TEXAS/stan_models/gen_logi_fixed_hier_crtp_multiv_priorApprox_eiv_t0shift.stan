// ═══════════════════════════════════════════════════════════════════════════════
// gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_t0shift.stan
//
// PURPOSE: Coretop forward calibration of the Scaled Ring Index against
//          temperature, with non-thermal predictors (G₂/₃ ratio, NO₃),
//          Bayesian errors-in-variables on those predictors, and explicit
//          separation of analytical measurement error from process noise.
//
// ─── THE CALIBRATION CURVE ────────────────────────────────────────────────────
// A generalized logistic (Richards) curve with the upper asymptote fixed at 1
// and Q fixed at 1, in which the non-thermal predictors shift the curve's
// location parameter T₀:
//
//     T₀_eff[i] = T₀ + γ_G23·g23_true[i] + γ_NO3·log₁₀(no3_true[i])
//     mu[i]     = b + (1 − b) / (1 + exp(−k(T[i] − T₀_eff[i])))^(1/ν)
//
// Because the predictors enter inside the logistic, mu is confined to (b, 1) for
// every finite value of the predictors and coefficients. The Scaled Ring Index is
// a bounded ratio, and this parameterization reproduces that bound by
// construction — no truncation, rejection or post-hoc clipping is involved. The
// generated quantities report mu_min and mu_max so the property can be checked
// draw by draw.
//
// T₀ is the curve's LOCATION parameter, not its inflection point. The steepest
// response sits at T₀ − ln(ν)/k, which for the fitted ν is several °C below T₀.
// Do not quote a single thermal sensitivity for this curve.
//
// ─── THE NON-THERMAL COEFFICIENTS ─────────────────────────────────────────────
// γ carries units of °C per predictor unit, and reads directly: a sample with
// this much G₂/₃ behaves like water that is γ_G23·g23 °C colder. These are
// ecological and physiological offsets to the temperature the archaeal community
// records.
//
// Both γ are declared positive, which is what the data support:
//   • mu decreases as T₀_eff increases.
//   • Higher G₂/₃ accompanies lower Scaled RI  ⇒  γ_G23 > 0.
//   • Below the cutoff log₁₀(no3) < 0, so a positive γ_NO3 LOWERS T₀_eff and
//     raises Scaled RI — the direction observed in nutrient-depleted settings.
//
// The half-normal priors, N(0, 1.0) °C/unit and N(0, 5.0) °C/log₁₀-unit, are
// several times wider than the posteriors they produce.
//
// ─── THE NO₃ GATE ─────────────────────────────────────────────────────────────
// The NO₃ term applies only at sites whose OBSERVED nitrate falls inside
// (0, no3_cutoff); above the cutoff the nutrient effect is taken to be absent and
// the site contributes no NO₃ term. Gating on the observed rather than the latent
// value keeps the set of sites receiving the correction fixed across draws.
//
// ─── ERRORS IN VARIABLES AND THE NOISE MODEL ──────────────────────────────────
//   1. Per-site analytical error on the proxy, sd_proxyObs, enters the likelihood
//      in quadrature:  total_sd = sqrt(sd_proxyObs² + sigma_proxyObs_crtp²).
//      sigma_proxyObs_crtp is therefore PROCESS noise only — oceanographic
//      scatter, bioturbation, model misfit — and not total Scaled RI scatter.
//   2. Its prior is scaled to the residual SE left after the thermal curve:
//      sigma ~ N(0, mean(sd_proxyObs) · sqrt(1 − R²_thermal)). R2_thermal is
//      supplied as data from a thermal-only coretop fit.
//   3. G₂/₃ has a latent true value per site, true_gdgt23ratio_crtp ~ N(0, 2),
//      with a normal measurement model. Sites with sd_gdgt23ratio_crtp = 0
//      receive the prior only.
//   4. NO₃ has a latent true value per site on the LINEAR scale,
//      true_no3_crtp ~ lognormal(log 0.3, 1.0), bounded above by no3_cutoff so
//      that log10() cannot overflow during HMC, with a normal measurement model.
//      Sites with sd_no3_crtp = 0 receive the prior only. There is no CV-gating.
//
// ─── WORKFLOW (two-stage priorApprox) ─────────────────────────────────────────
//   Stage 1: fit gen_logi_fixed_culmeso.stan on the culture and mesocosm data,
//            and pass the posterior mean and SD of {t0, k, b, v} in as
//            prior_mean_* / prior_sd_*. Compute R²_thermal from a thermal-only
//            coretop fit and pass it as R2_thermal.
//   Stage 2: this model, which fits the coretop parameters conditional on those
//            hyperpriors.
//
// The data block is a drop-in for build_fwd_data() output. Generated quantities
// are R2_full, bayesR2_full, RMSE_full, and the boundedness witnesses mu_min and
// mu_max.
// ═══════════════════════════════════════════════════════════════════════════════

// ─── The bounded mean, shared by the model and generated quantities ───────────
functions {
    vector bounded_mu(vector t, real t0, real k, real b, real v,
                      int use_gd, int use_n3, real gamma_gd, real gamma_n3,
                      vector gd_true, vector n3_true, vector n3_obs, real cutoff) {
        int N = num_elements(t);
        vector[N] t0_eff = rep_vector(t0, N);

        if (use_gd == 1)
            t0_eff += gamma_gd * gd_true;

        if (use_n3 == 1) {
            for (i in 1:N) {
                // The NO₃ term applies only to sites whose OBSERVED value falls
                // inside (0, cutoff), so the set of corrected sites is fixed
                // across draws rather than moving with the latent value.
                if (n3_obs[i] > 0 && n3_obs[i] < cutoff)
                    t0_eff[i] += gamma_n3 * log10(n3_true[i]);
            }
        }

        // Bounded on (b, 1) for every finite t0_eff — this is the whole point.
        return b + (1.0 - b) ./ pow(1.0 + exp(-k * (t - t0_eff)), 1.0 / v);
    }
}

data {
    // ─── Coretop (sediment) data ──────────────────────────────────────────────
    int<lower=1> N_crtp;
    vector[N_crtp] t_crtp;
    vector[N_crtp] proxyObs_crtp;
    vector<lower=0>[N_crtp] sd_proxyObs;

    // ─── Optional non-thermal predictors ──────────────────────────────────────
    vector[N_crtp] gdgt23ratio_crtp;
    vector<lower=0>[N_crtp] sd_gdgt23ratio_crtp;
    int<lower=0, upper=1> use_gdgt23ratio;

    vector[N_crtp] no3_crtp;
    vector<lower=0>[N_crtp] sd_no3_crtp;
    int<lower=0, upper=1> use_no3;
    real no3_cutoff;

    // ─── Stage-1 hyperpriors (culmeso posterior summary statistics) ───────────
    real prior_mean_t0;   real prior_sd_t0;
    real prior_mean_k;    real prior_sd_k;
    real prior_mean_b;    real prior_sd_b;
    real prior_mean_v;    real prior_sd_v;

    // ─── Thermal R² from a thermal-only preliminary fit ───────────────────────
    real<lower=0, upper=1> R2_thermal;
}

transformed data {
    real mean_sd_proxyObs = mean(sd_proxyObs);
    real proxyObs_res_se  = mean_sd_proxyObs * sqrt(1.0 - R2_thermal);
}

parameters {
    // ─── Coretop generalized-logistic curve parameters ────────────────────────
    real<lower=10, upper=50>   t0_crtp;
    real<lower=0.01>           k_crtp;
    real<lower=0.1, upper=1.0> b_crtp;
    real<lower=0.1, upper=10>  v_crtp;

    // ─── Non-thermal offsets, in °C (see sign note in the header) ─────────────
    real<lower=0, upper=5>  gamma_G23_crtp;   // °C per unit G₂/₃
    real<lower=0, upper=20> gamma_NO3_crtp;   // °C per log₁₀ unit NO₃

    // ─── Residual process noise ───────────────────────────────────────────────
    real<lower=0> sigma_proxyObs_crtp;

    // ─── Latent true predictor values ─────────────────────────────────────────
    vector[N_crtp]                             true_gdgt23ratio_crtp;
    vector<lower=0, upper=no3_cutoff>[N_crtp]  true_no3_crtp;
}

model {
    // ─── 1. Stage-1 hyperpriors ───────────────────────────────────────────────
    t0_crtp ~ normal(prior_mean_t0, prior_sd_t0);
    k_crtp  ~ normal(prior_mean_k,  prior_sd_k);
    b_crtp  ~ normal(prior_mean_b,  prior_sd_b);
    v_crtp  ~ normal(prior_mean_v,  prior_sd_v);

    // Half-normal (the <lower=0> bound truncates), in °C per predictor unit and
    // deliberately several times wider than the posteriors they produce.
    gamma_G23_crtp ~ normal(0, 1.0);
    gamma_NO3_crtp ~ normal(0, 5.0);

    sigma_proxyObs_crtp ~ normal(0, proxyObs_res_se);

    // ─── 2. EIV: G₂/₃ ratio ──────────────────────────────────────────────────
    true_gdgt23ratio_crtp ~ normal(0, 2);
    if (use_gdgt23ratio == 1)
        gdgt23ratio_crtp ~ normal(true_gdgt23ratio_crtp, sd_gdgt23ratio_crtp);

    // ─── 3. EIV: NO₃ concentration ───────────────────────────────────────────
    true_no3_crtp ~ lognormal(log(0.3), 1.0);
    if (use_no3 == 1) {
        for (i in 1:N_crtp) {
            if (no3_crtp[i] > 0 && no3_crtp[i] < no3_cutoff && sd_no3_crtp[i] > 0)
                no3_crtp[i] ~ normal(true_no3_crtp[i], sd_no3_crtp[i]);
        }
    }

    // ─── 4. Likelihood ────────────────────────────────────────────────────────
    vector[N_crtp] mu = bounded_mu(
        t_crtp, t0_crtp, k_crtp, b_crtp, v_crtp,
        use_gdgt23ratio, use_no3, gamma_G23_crtp, gamma_NO3_crtp,
        true_gdgt23ratio_crtp, true_no3_crtp, no3_crtp, no3_cutoff);

    vector[N_crtp] total_sd = sqrt(square(sd_proxyObs) + square(sigma_proxyObs_crtp));
    proxyObs_crtp ~ normal(mu, total_sd);
}

generated quantities {
    real R2_full;
    real bayesR2_full;
    real RMSE_full;
    // Boundedness witnesses: mu_min > b and mu_max < 1 hold in every draw, so
    // the bound can be verified from the posterior rather than assumed.
    real mu_min;
    real mu_max;

    {
        vector[N_crtp] mu = bounded_mu(
            t_crtp, t0_crtp, k_crtp, b_crtp, v_crtp,
            use_gdgt23ratio, use_no3, gamma_G23_crtp, gamma_NO3_crtp,
            true_gdgt23ratio_crtp, true_no3_crtp, no3_crtp, no3_cutoff);

        mu_min = min(mu);
        mu_max = max(mu);

        vector[N_crtp] resid = proxyObs_crtp - mu;
        real ybar    = mean(proxyObs_crtp);
        real TSS     = dot_self(proxyObs_crtp - ybar);
        real RSS     = dot_self(resid);
        R2_full      = 1.0 - RSS / TSS;
        RMSE_full    = sqrt(RSS / N_crtp);

        real var_mu  = variance(mu);
        bayesR2_full = var_mu / (var_mu + square(sigma_proxyObs_crtp));
    }
}
