// ===============================================================================
// gen_logi_fixed_culmesocore.stan
//
// PURPOSE: Forward calibration fitting ONE generalized logistic curve jointly to
//          all three data sources - culture, mesocosm and coretop - with a
//          single shared parameter set and no hierarchy between them.
//
//          This is the fully pooled fit: it treats a coretop sample as exchangeable
//          with a culture experiment. That is the assumption it exists to
//          represent, and it is a strong one.
//
// CALIBRATION CURVE - generalized logistic (Richards), upper asymptote fixed at
// 1 and Q fixed at 1:
//
//   RI = b + (1 - b) / (1 + exp(-k * (T - T0)))^(1/nu)
//
// T0 is the curve's LOCATION parameter, not its inflection point; the steepest
// response sits at T0 - ln(nu)/k, reported as max_slope_temp.
//
// Only the residual scales are estimated per data source; all four curve
// parameters are shared.
// ===============================================================================

data {
  int<lower=1> N_cul;         // number of culture observations
  vector[N_cul] t_cul;        // temperatures
  vector[N_cul] proxyObs_cul; // scaled ring index

  int<lower=1> N_meso;        
  vector[N_meso] t_meso;
  vector[N_meso] proxyObs_meso;

  int<lower=1> N_crtp;        
  vector[N_crtp] t_crtp;
  vector[N_crtp] proxyObs_crtp;
}

parameters {
  real<lower=-4> t0_culmesocore;   // center of generalized logistic
  real<lower=0, upper=0.5>  k_culmesocore;  // growth rate
  real<lower=0.1, upper=10>  v_culmesocore;  // shape/asymmetry (nu)
  real<lower=0, upper=1>    b_culmesocore;  // lower asymptote

  real<lower=0> sigma_proxyObs_cul;
  real<lower=0> sigma_proxyObs_meso;
  real<lower=0> sigma_proxyObs_crtp;
}

model {
  // Priors
  t0_culmesocore  ~ normal(30, 10) T[-1.8, ];
  k_culmesocore       ~ normal(0, 0.2) T[0, 0.5];
  v_culmesocore       ~ normal(1, 2) T[0.1, 10];
  b_culmesocore       ~ beta(2, 5);

  sigma_proxyObs_cul  ~ normal(0, 0.1);
  sigma_proxyObs_meso ~ normal(0, 0.1);
  sigma_proxyObs_crtp ~ normal(0, 0.1);

  // Generalized logistic curve (fixed upper bound = 1, Q fixed to 1)
  vector[N_cul] mu_proxyObs_cul = b_culmesocore
    + (1 - b_culmesocore) ./ pow(1 + exp(-k_culmesocore * (t_cul - t0_culmesocore)), 1 / v_culmesocore);

  vector[N_meso] mu_proxyObs_meso = b_culmesocore
    + (1 - b_culmesocore) ./ pow(1 + exp(-k_culmesocore * (t_meso - t0_culmesocore)), 1 / v_culmesocore);

  vector[N_crtp] mu_proxyObs_crtp = b_culmesocore
    + (1 - b_culmesocore) ./ pow(1 + exp(-k_culmesocore * (t_crtp - t0_culmesocore)), 1 / v_culmesocore);

  // Likelihoods
  proxyObs_cul   ~ normal(mu_proxyObs_cul, sigma_proxyObs_cul);
  proxyObs_meso  ~ normal(mu_proxyObs_meso, sigma_proxyObs_meso);
  proxyObs_crtp  ~ normal(mu_proxyObs_crtp, sigma_proxyObs_crtp);
}

generated quantities {
  // Temperature of steepest response for the Richards curve. Setting
  // d2f/dT2 = 0 gives exp(-k(T - T0)) = nu, hence T = T0 - ln(nu)/k, which lies
  // BELOW T0 for nu > 1. T0 itself is only the location parameter.
  real max_slope_temp;
  max_slope_temp = t0_culmesocore - log(v_culmesocore) / k_culmesocore;
}
