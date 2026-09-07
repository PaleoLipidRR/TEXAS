// invT_gen_logi_fixed_univ_reduce_sum.stan
functions {
  real partial_sum_lpdf(array[] real scaledRI_slice,
                        int start, int end,
                        matrix t_est,
                        vector prior_mu_t,
                        real prior_sigma_t,
                        int M,
                        vector t0, vector k, vector b, vector Q, vector v,
                        vector sigma_scaledRI) {

    real lp = 0;
    int N_slice = end - start + 1;
    // Subset the relevant data for this slice
    vector[N_slice] prior_mu_t_slice = prior_mu_t[start:end];

    for (m in 1:M) {
      vector[N_slice] t_col_slice = t_est[start:end, m];
      lp += normal_lpdf(t_col_slice | prior_mu_t_slice, prior_sigma_t);

      vector[N_slice] mu_scaledRI_slice = b[m] + elt_divide(1 - b[m],
                     pow(1 + Q[m] * exp(-k[m] * (t_col_slice - t0[m])), 1 / v[m]));

      lp += normal_lpdf(scaledRI_slice | mu_scaledRI_slice, sigma_scaledRI[m]);
    }
    return lp;
  }
}
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
  // Add grainsize for reduce_sum
  int<lower=1> grainsize;
}
parameters {
  matrix<lower=-1.8>[N,M] t_est;
}
model {
  // The model block is now much simpler
  target += reduce_sum(partial_sum_lpdf, to_array_1d(scaledRI), grainsize,
                       t_est, prior_mu_t, prior_sigma_t, M,
                       t0, k, b, Q, v, sigma_scaledRI);
}