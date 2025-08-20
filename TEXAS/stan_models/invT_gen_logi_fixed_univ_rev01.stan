// invT_gen_logi_fixed_univ_rev01.stan
data {
  int<lower=1> N;       
  int<lower=1> M;       

  vector[N] scaledRI;    
  vector[N] prior_mu_t;
  real prior_sigma_t;

  vector[M] t0;
  vector[M] k;
  vector[M] b;
  vector[M] Q;
  vector[M] v;
  vector[M] sigma_scaledRI;
}

parameters {
  matrix<lower=-1.8>[N,M] t_est;  // estimated temperatures
}

model {
  for (m in 1:M) {
    vector[N] t_col = t_est[:, m];
    target += normal_lpdf(t_col | prior_mu_t, prior_sigma_t);

    // 1. Calculate the base for the power function, ensuring it's non-negative.
    vector[N] power_base = fmax(0.0, 1 + Q[m] * exp(-k[m] * (t_col - t0[m])));

    // 2. Calculate the denominator, adding a small epsilon to the base
    //    to prevent pow(0, negative_number), which causes a crash.
    vector[N] denominator = pow(power_base + 1e-9, 1 / v[m]);
    
    // 3. Calculate the final expected value.
    vector[N] mu_scaledRI = b[m] + elt_divide(1 - b[m], denominator);


    target += normal_lpdf(scaledRI | mu_scaledRI, sigma_scaledRI[m]);
  }
}