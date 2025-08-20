// invT_logistic_fixed_multiv_marginal.stan

functions {
  real ll_chunk(int start, int end,
                vector T, vector scaledRI,
                vector prior_mu_t, real prior_sigma_t,
                // optional predictors
                int use_gd, int use_no3,
                vector gd, vector no3, real no3_cutoff,
                // forward posterior draws
                vector t0, vector k, vector b,
                vector beta_gd, vector beta_no3,
                vector sigma) {
    int M = rows(t0);
    real lp = 0;

    // prior contribution for this chunk
    lp += normal_lpdf(T[start:end] | prior_mu_t[start:end], prior_sigma_t);

    // loop over observations in this chunk
    for (n in start:end) {
      vector[M] llk;

      // loop over ensemble members
      for (m in 1:M) {
        // base logistic
        real mu = b[m] + (1 - b[m]) / (1 + exp(-k[m] * (T[n] - t0[m])));

        // optional gdgt23ratio correction
        if (use_gd == 1) {
          mu += beta_gd[m] * gd[n];
        }

        // optional nitrate correction w/ cutoff
        if (use_no3 == 1) {
          real logno3 = 0.0;
          if (no3[n] > 0.0 && no3[n] < no3_cutoff) {
            logno3 = log10(no3[n] + 1e-9);  // epsilon to avoid log(0)
          }
          mu += beta_no3[m] * logno3;
        }

        // likelihood for this (n,m)
        llk[m] = normal_lpdf(scaledRI[n] | mu, sigma[m]);
      }

      // average across ensemble members (marginalization)
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

  // Optional predictors: pass zeros if unused
  int<lower=0,upper=1> use_gdgt23ratio;
  int<lower=0,upper=1> use_no3;
  vector[N] gdgt23ratio;
  vector[N] no3;
  real<lower=0> no3_cutoff; 

  // Forward posterior draws (length M each)
  vector[M] t0;
  vector[M] k;
  vector[M] b;
  vector[M] beta0_gdgt23ratio;  // zeros if unused
  vector[M] beta0_no3;          // zeros if unused
  vector[M] sigma_scaledRI;

  int<lower=1> grainsize;       // for reduce_sum
}

parameters {
  vector[N] t_est;
}

model {
  target += reduce_sum(
    ll_chunk, 1, N, grainsize,
    t_est, scaledRI,
    prior_mu_t, prior_sigma_t,
    use_gdgt23ratio, use_no3,
    gdgt23ratio, no3, no3_cutoff,
    t0, k, b, beta0_gdgt23ratio, beta0_no3, sigma_scaledRI
  );
}