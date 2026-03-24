// ═══════════════════════════════════════════════════════════════════════════════
// invT_gen_logi_fixed_univ_marginal_unconstrained.stan
//
// PURPOSE: Bayesian paleotemperature reconstruction from observed Ring Index
//          values. Given proxyObs observations and a forward calibration
//          posterior, infers the posterior distribution of temperature for
//          each sample.
//
// APPROACH — "Marginal" (direct sampling):
//   The forward calibration introduces uncertainty in the RI–T curve parameters
//   θ = {T₀, k, b, Q, ν, σ}. We marginalize (integrate) over this uncertainty:
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
//   {T₀_m, k_m, b_m, Q_m, ν_m, σ_m} are all indexed by m in the inner loop.
//   Mixing indices across parameters would break their posterior correlations
//   and artificially inflate calibration uncertainty.
//   This constraint is enforced in build_invT_inputData() (Python side).
//
// TEMPERATURE CONSTRAINT: "unconstrained" variant
//   t_est has no lower bound — temperatures can be reconstructed below 0°C.
//   Use the "_hard_constraint" variant for a physical lower bound (e.g., -1.8°C).
// ═══════════════════════════════════════════════════════════════════════════════

data {
    // ─── Proxy observations to reconstruct ────────────────────────────────────
    int<lower=1> N;            // Number of sediment samples (downcore or coretop)
    vector[N] proxyObs;        // Observed scaled Ring Index for each sample (∈ [0,1])

    // ─── Prior on paleotemperature ─────────────────────────────────────────────
    // A normal prior T ~ Normal(prior_mu_t, prior_sigma_t) encodes any independent
    // knowledge about the expected temperature range (e.g., from site location,
    // foram assemblages, or Mg/Ca). Use prior_sigma_t = 10°C for a diffuse prior.
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
    vector[M] Q;               // Q_m: asymmetry; Q=1 → standard logistic
    vector[M] v;               // ν_m: shape
    vector[M] sigma_proxyObs;  // σ_m: residual calibration noise
}

parameters {
    // ─── Paleotemperature estimates ───────────────────────────────────────────
    // One temperature per sample — the ONLY parameter block in this model.
    // "Unconstrained" means no lower bound; Stan samples over all of ℝ.
    vector[N] t_est;
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
                / pow(1 + Q[m] * exp(-k[m] * (t_est[n] - t0[m])), 1.0 / v[m]);

            // Log-likelihood: how well does this calibration curve explain RI_n?
            lp[m] = normal_lpdf(proxyObs[n] | mu, sigma_proxyObs[m]);
        }

        // Average over all M calibration draws (marginalization).
        // Equivalent to: log[ (1/M) Σ_m exp(lp[m]) ]
        target += log_sum_exp(lp) - log_M;
    }
}
