data {
    int<lower=0> N; // number of culture obs
    int<lower=0> M; // number of core top obs
    int<lower=1> J; // number of culture groups
    int<lower=1> K; // number of coretop groups
    int<lower=1,upper=J> id_c[N];  // vector of culture group indices
    int<lower=1,upper=K> id[M];  // vector of coretop group indices
    real<lower=0> betat_m; // prior on betaT mean
    real<lower=0> betat_s; // prior on betaT sigma
    real<lower=0> betas_m; // prior on betaS mean
    real<lower=0> betas_s; // prior on betaS sigma
    real<upper=0> betap_m; // prior on betaP mean
    real<lower=0> betap_s; // prior on betaP sigma
    real<upper=0> betao_m; // prior on betaO mean
    real<lower=0> betao_s; // prior on betaO sigma
    real<lower=0> betac_m; // prior on betaC mean
    real<lower=0> betac_s; // prior on betaC sigma
    real<lower=0> sig_t; // prior on betaT sigma halfcauchy
    real alpha_1; // prior on alpha lower bound
    real alpha_2; // prior on alpha upper bound
    real<lower=0> sig_p; // prior on sigma upper bound
    vector[N] t_c; // temperature predictor cultures
    vector[N] s_c; // salinity predictor cultures
    vector[N] ph_c; // pH predictor cultures
    vector[N] mg_c; // mgca in ln units cultures
    vector[M] t; // temperature predictor coretops
    vector[M] s; // salinity predictor coretops
    vector[M] ph; // pH predictor coretops
    vector[M] omega; // omega predictor coretops
    vector[M] clean; // clean predictor coretops
    vector[M] mg; // mgca in ln units coretops 
}
parameters {
   real<lower=0> mu_betaT_c; // culture betaT mean hyperparameter
   real<lower=0,upper=0.05> sig_betaT_c; // culture betaT sigma hyperparameter
   real<lower=0> betaT_c; // culture betaT 
   real<lower=0> betaS_c; // culture betaS
   real<upper=0> betaP_c; // culture betaP
   real<lower=0,upper=0.3> sigma_c; // culture sigma parameter
   vector[J] alpha_c; // culture intercept by group
   real<lower=0> betaT; // coretop betaT by group
   real<upper=0> betaO; // coretop betaO
   real<lower=0> betaC; // coretop betaC
   vector[K] alpha; // coretop intercept by group
   vector<lower=0>[K] sigma; // coretop sigma by group
}
model {
   vector[N] mu_c; //linear predictor culture
   vector[N] sig_c; //linear predictor sigma culture
   vector[M] mu; //linear predictor coretops
   vector[M] sig; //linear predictor sigma coretops
   //T hyperparameter priors
   mu_betaT_c ~ normal(betat_m,betat_s);
   sig_betaT_c ~ cauchy(0,sig_t);
   //fill in prior quantities for group culture alpha
for(j in 1:J) {
   alpha_c[j] ~ uniform(alpha_1,alpha_2);
 }
   //define priors for culture parameters
   betaT_c ~ normal(mu_betaT_c,sig_betaT_c);
   betaS_c ~ normal(betas_m,betas_s);
   betaP_c ~ normal(betap_m,betap_s);
   //culture data model  
for(n in 1:N){
   if (id_c[n] > 3) {
      mu_c[n] = alpha_c[id_c[n]] + t_c[n] * betaT_c + s_c[n] * betaS_c;
      sig_c[n] = sigma_c;
   } else {
      mu_c[n] = alpha_c[id_c[n]] + t_c[n] * betaT_c + s_c[n] * betaS_c + ph_c[n] * betaP_c;
      sig_c[n] = sigma_c;
   }
 }
    mg_c ~ normal(mu_c,sig_c);
    //core top priors
for(k in 1:K) {
    alpha[k] ~ uniform(alpha_1,alpha_2);
    sigma[k] ~ uniform(0,sig_p);
 }
    betaT ~ normal(betaT_c,sig_betaT_c);
    betaO ~ normal(betao_m,betao_s);
    betaC ~ normal(betac_m,betac_s);
    //core top model
for(m in 1:M){
   if (id[m] < 3) {
      mu[m] = alpha[id[m]] + t[m] * betaT + s[m] * betaS_c + ph[m] * betaP_c + omega[m] * betaO + (1 - clean[m] * betaC);
      sig[m] = sigma[id[m]];
   } else {
      mu[m] = alpha[id[m]] + t[m] * betaT + s[m] * betaS_c + omega[m] * betaO + (1 - clean[m] * betaC);
      sig[m] = sigma[id[m]];
  }
}
    mg ~ normal(mu,sig);
}

generated quantities {
  vector[N] log_lik_c;
  vector[N] mg_hat_c;
  vector[N] sig_hat_c;
  vector[M] log_lik;
  vector[M] mg_hat;
  vector[M] sig_hat;
//culture data
for(n in 1:N){
   if (id_c[n] > 3) {
      mg_hat_c[n] = alpha_c[id_c[n]] + t_c[n] * betaT_c + s[n] * betaS_c;
      sig_hat_c[n] = sigma_c;
   } else {
      mg_hat_c[n] = alpha_c[id_c[n]] + t_c[n] * betaT_c + s[n] * betaS_c + ph_c[n] * betaP_c;
      sig_hat_c[n] = sigma_c;
   }
 }
  for (n in 1:N) {
    log_lik_c[n] = normal_lpdf(mg_c[n] | mg_hat_c[n],sig_hat_c[n]);
}
 //core tops
   for(m in 1:M){
   if (id[m] < 3) {
    mg_hat[m] = alpha[id[m]] + t[m] * betaT + s[m] * betaS_c + ph[m] * betaP_c + omega[m] * betaO + (1 - clean[m] * betaC);
    sig_hat[m] = sigma[id[m]];
   } else {
    mg_hat[m] = alpha[id[m]] + t[m] * betaT + s[m] * betaS_c + omega[m] * betaO + (1 - clean[m] * betaC);
    sig_hat[m] = sigma[id[m]];
  }
}
  for (m in 1:M) {
    log_lik[m] = normal_lpdf(mg[m] | mg_hat[m],sig_hat[m]);
}
}