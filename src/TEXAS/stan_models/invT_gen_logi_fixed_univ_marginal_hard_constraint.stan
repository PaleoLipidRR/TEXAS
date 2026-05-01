// ═══════════════════════════════════════════════════════════════════════════════
// invT_gen_logi_fixed_univ_marginal_hard_constraint.stan
//
// PURPOSE: Bayesian paleotemperature reconstruction from observed Ring Index
//          values. Univariate (no non-thermal predictors) counterpart of the
//          multivariate model, using the generalized logistic (Richards) curve.
//
// APPROACH — "Marginal" (direct sampling):
//   The forward calibration introduces uncertainty in the RI–T curve parameters
//   θ = {T₀, k, b, ν, σ}. We marginalize (integrate) over this uncertainty:
//
//     p(RI_obs | T) = ∫ p(RI_obs | T, θ) · p(θ | calib. data) dθ
//                   ≈ (1/M) Σ_{m=1}^{M}  Normal(RI_obs | f(T; θ_m), σ_m)
//
//   where θ_m is the m-th draw from the forward calibration posterior.
//   This is a Monte Carlo approximation of the integral using M pre-sampled
//   calibration curves. The only free parameter in this Stan model is T.
//
//   Compare to the ENSEMBLE approach (invT_gen_logi_fixed_univ.stan) which
//   instead estimates N×M temperatures simultaneously — much slower.
//
// CRITICAL: ALL PARAMETERS MUST USE THE SAME DRAW INDEX m
//   {T₀_m, k_m, b_m, ν_m, σ_m} are all indexed by m in the inner loop.
//   Mixing indices across parameters would break their posterior correlations
//   and artificially inflate calibration uncertainty.
//   This constraint is enforced in build_invT_inputData() (Python side).
//
// TEMPERATURE CONSTRAINT: "hard_constraint" variant
//   t_est is declared as vector<lower=min_temp>[N], which imposes a strict
//   physical lower bound on all reconstructed temperatures. Stan enforces this
//   via an internal change-of-variables (log-Jacobian adjustment), so HMC
//   never proposes temperatures below min_temp.
//   Typical value: min_temp = -1.8°C (seawater freezing point).
//   Use the "_unconstrained" variant if no lower bound is needed.
// ═══════════════════════════════════════════════════════════════════════════════

data {
    // ─── Proxy observations to reconstruct ────────────────────────────────────
    int<lower=1> N;            // Number of sediment samples (downcore or coretop)
    vector[N] proxyObs;        // Observed scaled Ring Index for each sample (∈ [0,1])

    // ─── Prior on paleotemperature ─────────────────────────────────────────────
    // A normal prior T ~ Normal(prior_mu_t, prior_sigma_t) encodes any independent
    // knowledge about the expected temperature range (e.g., from site location,
    // foram assemblages, or Mg/Ca). Use prior_sigma_t = 10–15°C for a diffuse prior.
    vector[N] prior_mu_t;      // Prior mean temperature for each sample (°C)
    real prior_sigma_t;        // Prior SD (shared across all samples) (°C)

    // ─── Forward calibration posterior — M draws of all curve parameters ───────
    // Loaded from the forward calibration .nc file by build_invT_inputData().
    // Increasing M improves the integral approximation at the cost of O(N×M)
    // likelihood evaluations per HMC step. Typical range: M = 100–500.
    //
    // IMPORTANT: each vector below has length M. Row m contains ONE complete,
    // self-consistent parameter set from the forward posterior. Using all
    // parameters at index [m] preserves their joint correlations.
    int<lower=1> M;
    vector[M] t0;              // T₀_m: reference temperature of each calibration draw (°C)
    vector[M] k;               // k_m: steepness
    vector[M] b;               // b_m: lower asymptote
    vector[M] v;               // ν_m: shape
    vector[M] sigma_proxyObs;  // σ_m: residual calibration noise

    // ─── Hard temperature constraint ──────────────────────────────────────────
    // Physical lower bound imposed on all reconstructed temperatures.
    // Stan enforces this by transforming t_est to an unconstrained space
    // during sampling (log-Jacobian corrects the density). No sample will
    // ever fall below min_temp in the posterior.
    // Set via predict_T_from_proxyObs(..., constraint_type='hard_constraint', min_temp=-1.8).
    real min_temp;             // Minimum physically plausible temperature (°C)
}

parameters {
    // ─── Paleotemperature estimates ───────────────────────────────────────────
    // One temperature per sample — the ONLY parameter block in this model.
    // The <lower=min_temp> bound is a hard constraint: Stan reparameterizes
    // internally so HMC never proposes values below min_temp. This differs
    // from a soft penalty — it is strictly enforced by construction.
    vector<lower=min_temp>[N] t_est;
}

model {
    // ─── Prior ────────────────────────────────────────────────────────────────
    t_est ~ normal(prior_mu_t, prior_sigma_t);

    // ─── Likelihood: Monte Carlo marginalization over calibration uncertainty ──
    // For each sample n, we average the Normal likelihood over all M calibration
    // curves. The log-sum-exp trick computes this average in log-space:
    //
    //   log p(RI_n | T_n) ≈ log[ (1/M) Σ_m exp(log N(RI_n | μ_m, σ_m)) ]
    //                     = log_sum_exp(lp_1, …, lp_M) - log(M)
    //
    // log_sum_exp is numerically stable (avoids floating-point underflow/overflow
    // that would occur from taking exp of very negative log-probabilities).

    real log_M = log(M);  // Precomputed once; used N times in the loop below

    for (n in 1:N) {
        vector[M] lp;   // Log-likelihood of RI_n under each of the M calibration draws

        for (m in 1:M) {
            // Compute expected RI using the m-th calibration curve (Eq. 1).
            // ALL parameters use the same draw index [m] to preserve correlations.
            real mu = b[m] + (1 - b[m])
                / pow(1 + exp(-k[m] * (t_est[n] - t0[m])), 1.0 / v[m]);

            // Log-likelihood: how well does this calibration curve explain RI_n?
            lp[m] = normal_lpdf(proxyObs[n] | mu, sigma_proxyObs[m]);
        }

        // Average over all M calibration draws (marginalization).
        // Equivalent to: log[ (1/M) Σ_m exp(lp[m]) ]
        target += log_sum_exp(lp) - log_M;
    }
}
