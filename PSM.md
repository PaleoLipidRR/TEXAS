# TEXAS Proxy System Model — Bayesian Inference Workflow

## 1. Overview

The TEXAS Proxy System Model (PSM) is designed to link **environmental variables** (e.g., sea surface temperature, archaeal community composition, nutrient availability) to **proxy measurements** (e.g., GDGT-based Ring Index, TEX₈₆) using a **Bayesian framework**.

It has two complementary components:

1. **Forward Model** — Predicts proxy values from known environmental conditions.
2. **Inverse Model (Bayesian Inference)** — Infers environmental conditions from observed proxy values.

---

## 2. Why Bayesian?

Bayesian inference provides a natural way to:
- Combine **prior knowledge** (from culture experiments, core-top datasets, or theory) with **new data**.
- Quantify **uncertainty** in both model parameters and reconstructions.
- Explicitly propagate uncertainties from forward models into reconstructions.

The heart of Bayesian statistics is **Bayes' Theorem**:

$$
P(\theta \mid D) = \frac{P(D \mid \theta) \, P(\theta)}{P(D)}
$$

Where:
- $$ \theta $$ = parameters we want to estimate (e.g., S-curve shape parameters, nutrient effect coefficients).
- $$ D $$ = observed data (e.g., GDGT fractions, Ring Index values).
- $$ P(\theta \mid D) $$ = **posterior** — our updated beliefs about parameters given the data.
- $$ P(D \mid \theta) $$ = **likelihood** — how well a given set of parameters explains the data.
- $$ P(\theta) $$ = **prior** — what we believed about parameters before seeing the data.
- $$ P(D) $$ = **evidence** — a normalization constant ensuring probabilities sum to 1.

---

## 3. Forward Model (Environmental Variables → Proxy Values)

The forward model predicts **scaled Ring Index** ($$ RI_{\text{scaled}} $$) from environmental predictors.

Example for a **generalized logistic forward model**:

$$
RI_{\text{scaled}}(T, X) = t_0 + \frac{L}{\left( 1 + Q \cdot e^{-k (T - T_{0})} \right)^{1/v}} + \sum_{j} \beta_j X_j
$$

Where:
- $$ T $$ = temperature.
- $$ X_j $$ = additional predictors (e.g., GDGT-2/GDGT-3 ratio, nitrate concentration).
- $$ t_0, L, Q, k, v $$ = logistic curve parameters (control inflection point, steepness, shape).
- $$ \beta_j $$ = coefficients for optional predictors.
- $$ RI_{\text{scaled}} $$ is normalized between 0 and 1 for comparability.

**Forward Model Role:**  
Given **true environmental conditions**, the model produces a distribution of possible GDGT-based proxy values, including natural variability and measurement noise.

---

## 4. Bayesian Inference (Proxy Values → Environmental Variables)

The inverse problem is: *Given an observed proxy value (e.g., RI), what is the most likely temperature?*

Using Bayes’ theorem:

$$
P(T \mid RI_{\text{obs}}) \propto P(RI_{\text{obs}} \mid T) \, P(T)
$$

- $$ P(T) $$ — **prior temperature distribution** (e.g., from regional climate models, modern analogs, or culture constraints).
- $$ P(RI_{\text{obs}} \mid T) $$ — **likelihood** from the forward model.
- The result $$ P(T \mid RI_{\text{obs}}) $$ is the **posterior** distribution of temperatures consistent with the observation.

---

### 4.1 Likelihood Function

The likelihood assumes a statistical error model:

$$
P(RI_{\text{obs}} \mid T, \theta) = \mathcal{N} \left( RI_{\text{obs}} \,\middle|\, RI_{\text{pred}}(T, X; \theta), \sigma_{RI} \right)
$$

- $$ RI_{\text{pred}} $$ — forward model prediction.
- $$ \sigma_{RI} $$ — residual standard deviation (accounts for unmodeled variability).

---

### 4.2 Priors

- **From cultures** — tightly constrain curve shape parameters ($$ t_0, k, v, Q $$) for known archaeal clades.
- **From core-tops** — set broader priors for environmental effects ($$ \beta_j $$).

Example prior for the temperature:

$$
T \sim \mathcal{N}(\mu_T, \sigma_T)
$$

Where $$\mu_T$$ and $$\sigma_T$$ come from prior knowledge (e.g., modern climatology).

---

## 5. Putting It Together

1. **Forward Step**  
   - Start with priors for all parameters.
   - Use the forward logistic model to simulate RI given environmental conditions.
   - Compare to observed RI values via the likelihood.

2. **Bayesian Updating**  
   - The posterior combines **likelihood** and **priors**.
   - We sample from the posterior (e.g., via MCMC in Stan/CmdStanPy).

3. **Inference Output**  
   - Posterior temperature distribution for each site/sample.
   - Full uncertainty range, not just a single “best estimate.”

---

## 6. Advantages for Paleoceanography

- **Mechanistic**: Based on GDGT biosynthesis behavior, not just empirical regression.
- **Flexible**: Can include ecological and nutrient effects.
- **Transparent Uncertainty**: Directly quantifies confidence intervals on temperature estimates.
- **Culture Integration**: Uses lab data as informative priors, bridging modern process understanding with ancient climate reconstructions.

---

## 7. Key Equations Summary

1. **Bayes' Theorem**
$$
P(\theta \mid D) = \frac{P(D \mid \theta) \, P(\theta)}{P(D)}
$$

2. **Forward Logistic Model**
$$
RI_{\text{scaled}}(T, X) = t_0 + \frac{L}{\left( 1 + Q \cdot e^{-k (T - T_{0})} \right)^{1/v}} + \sum_{j} \beta_j X_j
$$

3. **Likelihood**
$$
P(RI_{\text{obs}} \mid T, \theta) = \mathcal{N} \left( RI_{\text{obs}} \,\middle|\, RI_{\text{pred}}, \sigma_{RI} \right)
$$

---

*This workflow ensures that your TEXAS-PSM reconstructions combine the best available culture, modern, and paleo data in a statistically rigorous way, providing more reliable temperature estimates for past climates.*
