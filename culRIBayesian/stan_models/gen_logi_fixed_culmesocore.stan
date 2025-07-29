data {
  int<lower=1> N_cul;         // number of culture observations
  vector[N_cul] t_cul;        // temperatures
  vector[N_cul] scaledRI_cul; // scaled ring index

  int<lower=1> N_meso;        
  vector[N_meso] t_meso;
  vector[N_meso] scaledRI_meso;

  int<lower=1> N_crtp;        
  vector[N_crtp] t_crtp;
  vector[N_crtp] scaledRI_crtp;
}

parameters {
  real<lower=-4> center_culmesocore;   // center of generalized logistic
  real<lower=0>  k_culmesocore;        // growth rate
  real<lower=0.01> Q_culmesocore;      // curve start factor (Q), must be > 0
  real<lower=0.1>  v_culmesocore;      // shape/asymmetry (ν), must be > 0
  real<lower=0>    b_culmesocore;      // lower asymptote

  real<lower=0> sigma_scaledRI_cul;
  real<lower=0> sigma_scaledRI_meso;
  real<lower=0> sigma_scaledRI_crtp;
}

model {
  // Priors
  center_culmesocore ~ normal(30, 10) T[-1.8, ];
  k_culmesocore       ~ normal(0, 0.25);
  Q_culmesocore       ~ lognormal(0, 1);
  v_culmesocore       ~ lognormal(0, 0.5);
  b_culmesocore       ~ beta(2, 5);

  sigma_scaledRI_cul  ~ cauchy(0, 0.1);
  sigma_scaledRI_meso ~ cauchy(0, 0.1);
  sigma_scaledRI_crtp ~ cauchy(0, 0.1);

  // Generalized logistic curve (fixed upper bound = 1)
  vector[N_cul] mu_scaledRI_cul = b_culmesocore 
    + (1 - b_culmesocore) ./ pow(1 + Q_culmesocore * exp(-k_culmesocore * (t_cul - center_culmesocore)), 1 / v_culmesocore);

  vector[N_meso] mu_scaledRI_meso = b_culmesocore 
    + (1 - b_culmesocore) ./ pow(1 + Q_culmesocore * exp(-k_culmesocore * (t_meso - center_culmesocore)), 1 / v_culmesocore);

  vector[N_crtp] mu_scaledRI_crtp = b_culmesocore 
    + (1 - b_culmesocore) ./ pow(1 + Q_culmesocore * exp(-k_culmesocore * (t_crtp - center_culmesocore)), 1 / v_culmesocore);

  // Likelihoods
  scaledRI_cul   ~ normal(mu_scaledRI_cul, sigma_scaledRI_cul);
  scaledRI_meso  ~ normal(mu_scaledRI_meso, sigma_scaledRI_meso);
  scaledRI_crtp  ~ normal(mu_scaledRI_crtp, sigma_scaledRI_crtp);
}

generated quantities {
  real inflection_point;
  inflection_point = center_culmesocore + log(v_culmesocore) / k_culmesocore;
}
