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
  real<lower=0.1, upper=10>  v_culmesocore;  // shape/asymmetry (ν)
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
  real inflection_point;
  inflection_point = t0_culmesocore + log(v_culmesocore) / k_culmesocore;
}
