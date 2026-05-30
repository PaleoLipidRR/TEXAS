# Module 4 — What MCMC Actually Does

> **Coming soon.** This module will demystify Markov Chain Monte Carlo sampling using animated trace plots.

## Preview

TEXAS uses Stan's No-U-Turn Sampler (NUTS) to draw samples from the posterior. Instead of computing the posterior analytically (impossible for complex models), MCMC *explores* the posterior by taking many small steps, accumulating a cloud of samples that represent the distribution.

Key ideas this module will cover:

- Why we sample instead of solve
- Reading a trace plot: what good mixing looks like vs. pathological chains
- R-hat: a simple convergence diagnostic
- Effective sample size (ESS): why 4,000 draws ≠ 4,000 independent estimates
- Divergences: what they signal and why TEXAS reports them
