// invT_logistic_fixed_multiv_marginal.stan (UPDATED reduce_sum API)

functions {
  real ll_chunk(
      array[] int slice_indices,  // NEW API: array of indices for this chunk
      int start, int end,
      vector scaledRI,                 // full vector; slice inside
      vector T, vector prior_mu_t, real prior_sigma_t,
      int use_gd, int use_no3,
      vector gd, vector no3, real no3_cutoff,
      vector t0, vector k, vector b,
      vector beta_gd, vector beta_no3,
      vector sigma
  ) {
    int M = rows(t0);
    int n_chunk = end - start + 1;
    real lp = 0;

    // slice inputs for this chunk
    vector[n_chunk] y      = segment(scaledRI,  start, n_chunk);
    vector[n_chunk] T_seg  = segment(T,         start, n_chunk);
    vector[n_chunk] mu_seg = segment(prior_mu_t,start, n_chunk);
    vector[n_chunk] gd_seg = segment(gd,        start, n_chunk);
    vector[n_chunk] n3_seg = segment(no3,       start, n_chunk);

    // prior
    lp += normal_lpdf(T_seg | mu_seg, prior_sigma_t);

    // likelihood (marginalize over ensemble m = 1..M)
    for (i in 1:n_chunk) {
      vector[M] llk;
      for (m in 1:M) {
        real lin = b[m];

        if (use_gd == 1)
          lin += beta_gd[m] * gd_seg[i];

        if (use_no3 == 1) {
          real logno3 = 0.0;
          if (n3_seg[i] > 0 && n3_seg[i] < no3_cutoff)
            logno3 = log10(n3_seg[i] + 1e-9);
          lin += beta_no3[m] * logno3;
        }

        // logistic mean (L = 1)
        real mu = lin + (1 - b[m]) / (1 + exp(-k[m] * (T_seg[i] - t0[m])));
        llk[m] = normal_lpdf(y[i] | mu, sigma[m]);
      }
      lp += log_sum_exp(llk) - log(M);
    }
    return lp;
  }
}

data {
  int<lower=1> N;
  int<lower=1> M;
  vector[N] scaledRI;
  vector[N] prior_mu_t;
  real<lower=0> prior_sigma_t;

  int<lower=0,upper=1> use_gdgt23ratio;
  int<lower=0,upper=1> use_no3;
  vector[N] gdgt23ratio;
  vector[N] no3;
  real<lower=0> no3_cutoff;

  vector[M] t0;
  vector[M] k;
  vector[M] b;
  vector[M] beta0_gdgt23ratio;
  vector[M] beta0_no3;
  vector[M] sigma_scaledRI;

  int<lower=1> grainsize;
}

parameters {
  vector[N] t_est;
}

model {
  // NEW API: Create array of indices to pass to reduce_sum
  array[N] int indices = linspaced_int_array(N, 1, N);
  
  // NEW API: array of indices as second argument, grainsize as third argument
  target += reduce_sum(
    ll_chunk, indices, grainsize,
    scaledRI, t_est, prior_mu_t, prior_sigma_t,
    use_gdgt23ratio, use_no3, gdgt23ratio, no3, no3_cutoff,
    t0, k, b, beta0_gdgt23ratio, beta0_no3, sigma_scaledRI
  );
}