// joint_culture_meso_generalized_logistic.stan
data {
  int<lower=1> N_cul;
  vector[N_cul] t_cul;
  vector[N_cul] scaledRI_cul;

  int<lower=1> N_meso;
  vector[N_meso] t_meso;
  vector[N_meso] scaledRI_meso;
}

parameters {
  real<lower=-1.8> t0_culmeso;        // Center of the curve (NOT necessarily inflection)
  real<lower=0>    k_culmeso;             // slope (k)
  real<lower=0>    Q_culmeso;             // Q: curve-start factor
  real<lower=0.1>  v_culmeso;             // Shape (nu); >0, often >0.1 to avoid numerical issues
  real<lower=0>    b_culmeso;             // Lower asymptote (b)
  real<lower=0>    a_culmeso;         // Upper asymptote (A)

  real<lower=0> sigma_scaledRI_cul;
  real<lower=0> sigma_scaledRI_meso;
}

model {
  // Priors
  t0_culmeso ~ normal(30, 10) T[-1.8, ];
  k_culmeso      ~ normal(0, 0.5) T[0, ];  // reverted - k is unbounded above in gen logistic
  Q_culmeso      ~ normal(1, 30) T[0, ]; 
  v_culmeso      ~ normal(1, 10) T[0, ]; 
  b_culmeso      ~ beta(2, 5);
  a_culmeso      ~ normal(1, 0.2);
  sigma_scaledRI_cul  ~ normal(0.01, 0.1);
  sigma_scaledRI_meso ~ normal(0.01, 0.1);

  // Generalized logistic mean vectors
  vector[N_cul] mu_scaledRI_cul = b_culmeso + (a_culmeso - b_culmeso)
    ./ pow(1 + Q_culmeso * exp(-k_culmeso * (t_cul - t0_culmeso)), 1 / v_culmeso);
  vector[N_meso] mu_scaledRI_meso = b_culmeso + (a_culmeso - b_culmeso)
    ./ pow(1 + Q_culmeso * exp(-k_culmeso * (t_meso - t0_culmeso)), 1 / v_culmeso);

  // Likelihood
  scaledRI_cul  ~ normal(mu_scaledRI_cul, sigma_scaledRI_cul);
  scaledRI_meso ~ normal(mu_scaledRI_meso, sigma_scaledRI_meso);
}

generated quantities {
  real<lower=0> sigma_scaledRI_culmeso;
  real inflection_point;

  sigma_scaledRI_culmeso = sqrt(
    (N_cul * square(sigma_scaledRI_cul) + N_meso * square(sigma_scaledRI_meso)) 
    / (N_cul + N_meso)
  );

  // Inflection point of generalized logistic
  inflection_point = t0_culmeso + log(v_culmeso) / k_culmeso;
}
