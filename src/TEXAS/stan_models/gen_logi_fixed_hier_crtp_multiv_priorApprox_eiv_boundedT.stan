// ═══════════════════════════════════════════════════════════════════════════════
// ⚠ UNDER REVIEW — NOT THE PUBLISHED TEXAS CALIBRATION.
//
// This model was written in response to a reviewer comment on the TEXAS manuscript
// and has NOT been accepted. It is shipped so the revision is reproducible and
// inspectable, not as a recommendation. The published calibration remains
// gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv.stan.
//
// ⚠ THE PACKAGE API CANNOT USE THIS MODEL YET. Its covariate parameters are named
// gamma_G23_crtp / gamma_NO3_crtp and act as a SHIFT OF T0, whereas every helper in
// TEXAS assumes the parent's beta_G23_crtp / beta_NO3_crtp acting additively on the
// response. Specifically:
//   * TEXAS.ensemble.generate_ensemble_auto  -> raises "Missing parameters: beta_*"
//   * TEXAS.predict.predict_T_from_proxyObs  -> SILENTLY selects the ADDITIVE inverse
//     (TEXAS/stan/invT.py builds the invT model name without any boundedT branch), so
//     it would return temperatures reconstructed under a model that was never fitted,
//     with no error raised.
// Until those paths learn about gamma_*, drive this model directly: build the Stan data
// yourself and pair it with invT_gen_logi_fixed_multiv_marginal_unconstrained_boundedT.stan.
// ═══════════════════════════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════════════════════════
// gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT.stan
//
// PURPOSE: Bounded-response variant of gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv.
//          Identical data block, priors, EIV structure and noise model — the ONLY
//          change is WHERE the non-thermal predictors enter the calibration curve.
//
// ─── THE PROBLEM THIS ADDRESSES (reviewer comment) ────────────────────────────
// In the response-space parent model the corrections are additive on RI:
//
//     mu = b + (1 − b)/(1 + exp(−k(T − T₀)))^(1/ν)  +  β_G23·g23  +  β_NO3·log₁₀(no3)
//          └──────────── bounded on [b, 1] ────────────┘  └──── unbounded shift c ────┘
//
// The logistic term is bounded, but c slides the whole curve vertically, so the
// effective range becomes [b + c, 1 + c]. Nothing holds that inside [0, 1].
//
// What that costs in practice. QUOTE THE GRIDDED COLUMN: the published fit
// (SI_code2_TEXAS_analysis.ipynb) uses the gridded, screened compilation at
// N=1513, NOT the raw per-sample compilation at N=2043. Both are given because an
// earlier revision of this header quoted the raw set by mistake.
//
//                                       raw N=2043        PUBLISHED N=1513
//   upper asymptote 1 + c > 1        587 (28.7 %)         297 (19.6 %)
//     …its maximum                        1.177                1.156
//   lower asymptote b + c < 0          1 (0.05 %)      0 rows — NEVER
//     …its minimum                       −0.076               +0.238
//   spread of b + c across coretops        0.677                0.355
//   fitted mean at the data          0.006 … 0.954        0.340 … 0.946
//   frac(mu > 1) / frac(mu < 0)            0 / 0                0 / 0
//
//   • On the published set the violation lives ENTIRELY at the ceiling. One in five
//     coretops sits on a curve whose upper asymptote exceeds 1; the lower asymptote
//     is violated zero times and never comes within 0.23 of zero.
//   • At the observed (T, G₂/₃, NO₃) of the calibration points themselves the
//     fitted mean stays in range on both sets, across all posterior draws.
//
//   Figures recomputed 2026-07-30 in the revision workspace (not shipped) at
//   posterior-median coefficients. A still earlier revision quoted a
//   median-coefficient sweep over T ∈ [−2, 40] °C spanning −0.372 … 1.083; that is
//   an extrapolation exercise rather than a property of the fit and is retracted —
//   do not quote it.
//
// So the defect is structural rather than currently-realised: the parameterization
// carries no bound, the fitted curves do leave [0, 1] away from the data, and the
// guarantee fails under extrapolation — but the published calibration fit is not
// itself producing out-of-range values. A Scaled Ring Index is a bounded ratio, so
// the guarantee is still worth having by construction.
//
// ON THIS MODEL'S SCOPE — a fair objection, tested and answered.
// Because the published-set violation is purely at the ceiling, pinning the FLOOR
// as well (which is what this file does — b is a single scalar shared by every
// community) is not paid for by the diagnostic above: it discards 0.355 of fitted
// lower-asymptote spread to fix a problem that occurs only at the top.
//
// So the less restrictive alternative was built and fitted:
// a ceiling-only variant (boundedCeil, kept in the revision workspace and NOT shipped)
// pins only the ceiling and lets the floor move
// per community via b_eff = inv_logit(logit(b) + β·covariates).
//
// IT FITS WORSE — on the published set, on every metric (2026-07-30, same seed,
// same folds, zero R̂ > 1.01):
//
//                     R²(in)  RMSE(in)  RMSE(spatial CV)    elpd
//     parent          0.7964    0.0516            0.0574  2328.2
//     boundedT (this) 0.8034    0.0507            0.0572  2352.8
//     boundedCeil     0.7892    0.0525            0.0590  2302.8
//
//     elpd(boundedCeil − boundedT) = −49.9 ± 16.0  (−3.13 SE)
//
// The per-community floors do spread (b_eff_spread median 0.355), and p_waic is the
// LOWEST of the three (9.93) — so boundedCeil under-fits rather than over-fits. The
// reading: the non-thermal predictors move the community along the TEMPERATURE axis,
// which is what T0_eff encodes, not up and down the cold-end baseline.
//
// This file therefore stays the headline model, and the shared floor is a choice the
// data support rather than a restriction imposed for convenience.
//
// ─── THE FIX ──────────────────────────────────────────────────────────────────
// Move the predictors INSIDE the logistic, as a shift of the inflection point:
//
//     T₀_eff[i] = T₀ + γ_G23·g23_true[i] + γ_NO3·log₁₀(no3_true[i])
//     mu[i]     = b + (1 − b)/(1 + exp(−k(T[i] − T₀_eff[i])))^(1/ν)
//
// mu is now confined to (b, 1) for every finite value of the predictors and
// coefficients — bounded BY CONSTRUCTION, with no truncation or rejection.
//
// ─── INTERPRETATION AND SIGN ──────────────────────────────────────────────────
// γ carries units of °C per predictor unit: "a sample with this much G₂/₃ behaves
// like water that is γ·g23 °C colder". This is arguably the more physical reading
// — these are ecological/physiological offsets to the temperature the archaeal
// community records, not additive contamination of the ratio itself.
//
// Signs are defined so both γ are POSITIVE, matching the parent's β ∈ [−1, 0]:
//   • mu decreases as T₀_eff increases.
//   • Parent: β_G23 < 0, so more G₂/₃ lowers RI  ⇒  γ_G23 > 0.
//   • Parent: β_NO3 < 0 and log₁₀(no3) < 0 below the cutoff, so the NO₃ term
//     RAISES RI there ⇒ T₀_eff must fall ⇒ γ_NO3 > 0 (γ·log₁₀(no3) < 0).
//
// Rough scale for the priors: near the inflection dRI/dT ≈ 0.028 RI/°C for the
// published coefficients, so the parent's β_G23 = −0.0057 RI/unit corresponds to
// γ_G23 ≈ 0.2 °C/unit and β_NO3 = −0.046 RI/log₁₀-unit to γ_NO3 ≈ 1.6 °C/log₁₀-unit.
// The half-normal priors below are deliberately several times wider than that.
//
// ─── WHAT IS UNCHANGED ────────────────────────────────────────────────────────
// Data block (drop-in compatible with build_fwd_data output), stage-1 hyperpriors
// on {t0, k, b, v}, the G₂/₃ and NO₃ EIV latent-variable structure, the
// quadrature noise model, and the R²/RMSE generated quantities. Only the two
// correction coefficients are renamed β → γ and relocated.
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
                // Same gating as the parent model: the NO₃ term applies only to
                // sites whose OBSERVED value falls inside (0, cutoff).
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

    // Half-normal (the <lower=0> bound truncates), scaled well above the
    // response-space equivalents of the published β coefficients.
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
    // Boundedness witnesses — with this parameterization mu_min > b and
    // mu_max < 1 in EVERY draw, which is the claim to show the reviewer.
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
