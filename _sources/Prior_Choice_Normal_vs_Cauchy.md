# Why Normal Instead of Cauchy Priors? 🤔

## The Problem with Cauchy Priors

### 1. **Heavy Tails = Extreme Values**
- **Cauchy(0,1)**: Has infinite variance, very heavy tails
- **Problem**: Allows extreme parameter values that are unrealistic
- **Example**: `sigma_scaledRI ~ cauchy(0, 0.1)` can generate noise levels of 10+ (completely unrealistic for scaled RI)

### 2. **Poor Hierarchical Performance** 
```stan
// BAD: Cauchy hyperpriors
sigma_t0_culmeso ~ cauchy(0, 1);    // Can be huge!
t0_crtp ~ normal(t0_culmeso, sigma_t0_culmeso);  // Unstable hierarchy
```
- **Issue**: Huge `sigma` values → weak hierarchical shrinkage
- **Result**: Coretop parameters don't learn from culture+mesocosm data

### 3. **Sampling Difficulties**
- **Cauchy**: Hard for Stan to sample efficiently
- **Symptoms**: Slow convergence, divergent transitions, high Rhat
- **Cause**: Extreme tail behavior confuses NUTS sampler

## Why Normal Priors Are Better

### 1. **Realistic Constraints**
```stan
// GOOD: Informative normal priors
sigma_scaledRI_cul ~ normal(0, 0.1);        // Half-normal (lower=0): realistic noise levels
sigma_t0_culmeso ~ normal(0, 5);            // Reasonable temperature variation
sigma_k_culmeso ~ normal(0, 0.2);           // Respects k ∈ [0,1] bounds
```

### 2. **Better Hierarchical Shrinkage**
```stan
// Proper hierarchical structure
t0_culmeso ~ normal(30, 10);                    // Culture+mesocosm center
sigma_t0_culmeso ~ normal(0, 5);                // Reasonable scale
t0_crtp ~ normal(t0_culmeso, sigma_t0_culmeso); // Coretop inherits info
```
- **Result**: Purple line (coretop) properly positioned relative to orange/blue lines

### 3. **Computational Efficiency**
- **Faster sampling**: Normal distributions are Stan's "native" format
- **Better convergence**: Avoids extreme values that break sampler
- **Fewer divergences**: Smoother posterior geometry

## Scientific Justification

### **For Observation Noise** (`sigma_scaledRI`)
```stan
// OLD: sigma_scaledRI ~ cauchy(0, 0.1)
// NEW: sigma_scaledRI ~ normal(0, 0.1)   // half-normal, lower=0
```
- **Expectation**: Scaled RI measurements precise to ~0.01-0.05 units
- **Cauchy problem**: Allows noise > 1.0 (larger than signal!)
- **Normal solution**: Concentrates mass around realistic values

### **For Hierarchical Scales** (`sigma_*_culmeso`)
```stan
// OLD: sigma_t0_culmeso ~ cauchy(0, 1)  
// NEW: sigma_t0_culmeso ~ normal(0, 5)
```
- **Expectation**: Coretop temperatures vary ±2-10°C from culture+mesocosm
- **Cauchy problem**: Allows ±100°C variations (nonsensical)
- **Normal solution**: Reasonable biological variation

## The "Weakly Informative" Myth

### **Cauchy ≠ Weakly Informative**
- **Common misconception**: "Cauchy(0,1) is non-informative"
- **Reality**: Cauchy is **strongly informative toward extreme values**
- **Better approach**: Use normal priors scaled to domain knowledge

### **True Weak Information**
```stan
// Domain-appropriate weak priors
sigma_t0_culmeso ~ normal(0, 5);     // "Could be 1-10°C variation"
sigma_k_culmeso ~ normal(0, 0.2);    // "k usually 0.1-0.8, so σ < 0.5"
```

## Expected Improvements in Your Models

### 1. **Faster Stan Sampling**
- Fewer divergent transitions
- Better Rhat values (< 1.01)
- Higher effective sample size

### 2. **Sensible Parameter Estimates**
- Observation noise: 0.01-0.1 range (realistic)
- Hierarchical scales: Reasonable biological variation
- No extreme outlier estimates

### 3. **Proper Hierarchical Behavior**
- Coretop estimates informed by culture+mesocosm data
- Purple line positioned correctly relative to other data
- Better uncertainty quantification

## Summary

**Normal priors** provide the right balance of:
- ✅ **Flexibility**: Allow parameter exploration
- ✅ **Constraint**: Prevent unrealistic values  
- ✅ **Efficiency**: Fast, stable Stan sampling
- ✅ **Interpretability**: Match scientific expectations

**Cauchy priors** are often:
- ❌ **Too permissive**: Allow extreme unrealistic values
- ❌ **Computationally expensive**: Slow sampling, divergences  
- ❌ **Scientifically inappropriate**: Don't match domain knowledge
- ❌ **Hierarchically weak**: Poor information sharing

## Practical Guidelines for Prior Choice

### **Use Normal Priors When:**
- You have domain knowledge about reasonable parameter ranges
- Working with hierarchical models (always!)
- Parameter bounds are important (e.g., k ∈ [0,1])
- Computational efficiency matters

### **Consider Other Distributions When:**
- **Beta**: For bounded [0,1] parameters (like proportions)
- **Gamma/Lognormal**: For positive-only parameters with skew
- **Student-t**: When you need slightly heavier tails than normal
- **Half-normal**: For positive scale parameters

### **Avoid Cauchy Unless:**
- You specifically need very heavy tails
- You're modeling rare extreme events
- Other distributions have failed for theoretical reasons

## References and Further Reading

1. **Gelman et al. (2017)**: "Prior distributions for variance parameters in hierarchical models" - Argues against uniform/Cauchy hyperpriors
2. **Stan User's Guide**: Section on "Priors for Hierarchical Models"  
3. **McElreath (2020)**: Statistical Rethinking - Chapter on weakly informative priors
4. **Betancourt (2017)**: "A Conceptual Introduction to Hamiltonian Monte Carlo" - On computational considerations

---
*Prior-standardization note for the TEXAS Stan models. The current observation-noise
prior is the half-normal `normal(0, 0.1)` on `sigma_proxyObs_*` (see the variance-partitioning
update, 2026-04-08).*
