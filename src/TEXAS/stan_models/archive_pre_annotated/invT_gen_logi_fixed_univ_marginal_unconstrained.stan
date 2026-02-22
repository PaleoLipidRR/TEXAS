// invT_gen_logi_fixed_univ_marginal_unconstrained.stan
// 
// Inverse temperature prediction from Ring Index (RI) using Bayesian marginalization
// over forward calibration uncertainty. This model predicts temperatures from observed
// RI values by integrating over M posterior samples from the forward calibration model.

data {
  // ═══════════════════════════════════════════════════════════════════════════
  // OBSERVATIONS TO PREDICT
  // ═══════════════════════════════════════════════════════════════════════════
  int<lower=1> N;              // Number of observations (e.g., coretop samples)
  vector[N] scaledRI;          // Observed Ring Index values (target proxy data)
  
  // ═══════════════════════════════════════════════════════════════════════════
  // TEMPERATURE PRIORS (Informative constraints on plausible temperature range)
  // ═══════════════════════════════════════════════════════════════════════════
  vector[N] prior_mu_t;        // Prior mean temperature for each observation
                               // (e.g., 20°C for tropical sites, 5°C for high-latitude)
  real prior_sigma_t;          // Prior standard deviation (e.g., 10°C for wide uncertainty)
  
  // ═══════════════════════════════════════════════════════════════════════════
  // FORWARD CALIBRATION POSTERIOR (M samples from forward model)
  // These are FIXED values loaded from your forward calibration results.
  // Each [m] represents one plausible calibration curve from p(θ | coretop_data)
  // ═══════════════════════════════════════════════════════════════════════════
  int<lower=1> M;              // Number of posterior samples from forward calibration
                               // (e.g., M=1000 samples from 4 chains × 250 draws)
  
  // Generalized logistic function parameters (one value per posterior sample):
  vector[M] t0;                // Inflection point temperature (°C)
  vector[M] k;                 // Growth rate (steepness of sigmoid)
  vector[M] b;                 // Lower asymptote (baseline RI at cold temperatures)
  vector[M] Q;                 // Asymmetry parameter (fixed at 1 for standard logistic)
  vector[M] v;                 // Affects near-asymptote behavior
  vector[M] sigma_scaledRI;    // Residual error in RI predictions
}

parameters {
  // ═══════════════════════════════════════════════════════════════════════════
  // PARAMETERS TO ESTIMATE
  // ═══════════════════════════════════════════════════════════════════════════
  vector[N] t_est;             // Estimated temperature for each observation
                               // This is the ONLY parameter being sampled
                               // (vs. ensemble models that sample N×M parameters)
}

model {
  // ═══════════════════════════════════════════════════════════════════════════
  // PRIOR: Informative constraint on plausible temperature range
  // ═══════════════════════════════════════════════════════════════════════════
  t_est ~ normal(prior_mu_t, prior_sigma_t);
  
  // ═══════════════════════════════════════════════════════════════════════════
  // LIKELIHOOD: Marginalizing over forward calibration uncertainty
  // 
  // For each observation n, we compute:
  //   p(RI[n] | T[n]) = ∫ p(RI[n] | T[n], θ) p(θ | coretop_data) dθ
  //                   ≈ (1/M) Σ_{m=1}^M p(RI[n] | T[n], θ_m)
  //
  // This integrates out uncertainty in the calibration parameters by averaging
  // over all M posterior samples from the forward model.
  // ═══════════════════════════════════════════════════════════════════════════
  
  for (n in 1:N) {  // Loop over each observation
    vector[M] lp;   // Log-probabilities for each calibration sample
    
    for (m in 1:M) {  // Loop over each forward posterior sample
      
      // ─────────────────────────────────────────────────────────────────────
      // STEP 1: Compute expected RI using the m-th calibration curve
      // Generalized logistic function: RI = f(T; t0, k, b, Q, v)
      // ─────────────────────────────────────────────────────────────────────
      real mu = b[m] + (1 - b[m]) / pow(1 + Q[m] * exp(-k[m] * (t_est[n] - t0[m])), 1.0 / v[m]);
      
      // ─────────────────────────────────────────────────────────────────────
      // STEP 2: Evaluate likelihood of observed RI given this calibration
      // p(RI[n] | T[n], θ_m) ~ Normal(μ_m, σ_m)
      // ─────────────────────────────────────────────────────────────────────
      lp[m] = normal_lpdf(scaledRI[n] | mu, sigma_scaledRI[m]);
    }
    
    // ───────────────────────────────────────────────────────────────────────
    // STEP 3: Monte Carlo integration via log-sum-exp trick
    // Computes: log[ (1/M) Σ exp(lp[m]) ] = log(Σ exp(lp[m])) - log(M)
    // This is numerically stable averaging in log-space
    // ───────────────────────────────────────────────────────────────────────
    target += log_sum_exp(lp) - log(M);
  }
}