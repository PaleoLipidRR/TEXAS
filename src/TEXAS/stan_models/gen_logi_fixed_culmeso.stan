// ===============================================================================
// gen_logi_fixed_culmeso.stan
//
// PURPOSE: Stage-1 forward calibration. Fits one generalized logistic curve
//          jointly to the culture and mesocosm data, which are the controlled
//          experiments in the training set and therefore constrain the SHAPE of
//          the Scaled RI - temperature response.
//
//          Its posterior mean and SD for {t0, k, b, v} are what the coretop
//          models take as hyperpriors, so this fit is a prerequisite for every
//          priorApprox model in this directory.
//
// CALIBRATION CURVE - generalized logistic (Richards), upper asymptote fixed at
// 1 and Q fixed at 1:
//
//   RI = b + (1 - b) / (1 + exp(-k * (T - T0)))^(1/nu)
//
// T0 is the curve's LOCATION parameter, not its inflection point; the steepest
// response sits at T0 - ln(nu)/k.
//
// The two data sources share all four curve parameters and differ only in their
// residual scale: sigma_proxyObs_cul and sigma_proxyObs_meso are estimated
// separately, since culture and mesocosm experiments do not have the same
// analytical and environmental scatter.
//
// Priors are weakly informative and truncated to match each parameter's declared
// bounds, so the truncation and the constraint agree and the normalizing constant
// stays correct.
// ===============================================================================

data {
  int<lower=1> N_cul;
  vector[N_cul] t_cul;
  vector[N_cul] proxyObs_cul;

  int<lower=1> N_meso;
  vector[N_meso] t_meso;
  vector[N_meso] proxyObs_meso;
}

parameters {
  real<lower=-1.8> t0_culmeso;        // Curve location (steepest response is at t0 - ln(v)/k)
  real<lower=0, upper=0.5>  k_culmeso;   // Growth rate
  real<lower=0.1, upper=10>  v_culmeso;             // Shape (nu); >0, often >0.1 to avoid numerical issues
  real<lower=0, upper=1>    b_culmeso;    // Lower asymptote (A)

  real<lower=0> sigma_proxyObs_cul;
  real<lower=0> sigma_proxyObs_meso;
}

model {
  // Priors
  t0_culmeso ~ normal(30, 10) T[-1.8, ];
  k_culmeso      ~ normal(0, 0.2) T[0, 0.5];
  v_culmeso      ~ normal(1, 2) T[0.1, 10];
  b_culmeso      ~ beta(2, 5);
  sigma_proxyObs_cul  ~ normal(0, 0.1);
  sigma_proxyObs_meso ~ normal(0, 0.1);

  // Generalized logistic mean vectors (Q fixed to 1)
  vector[N_cul] mu_proxyObs_cul = b_culmeso + (1 - b_culmeso)
    ./ pow(1 + exp(-k_culmeso * (t_cul - t0_culmeso)), 1 / v_culmeso);
  vector[N_meso] mu_proxyObs_meso = b_culmeso + (1 - b_culmeso)
    ./ pow(1 + exp(-k_culmeso * (t_meso - t0_culmeso)), 1 / v_culmeso);

  // Likelihood
  proxyObs_cul  ~ normal(mu_proxyObs_cul, sigma_proxyObs_cul);
  proxyObs_meso ~ normal(mu_proxyObs_meso, sigma_proxyObs_meso);
}