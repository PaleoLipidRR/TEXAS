# Understanding `reduce_sum` and `ll_chunk` in TEXAS-PSM
## A visual guide for paleogeologists

This note explains two important pieces of computational machinery used in the TEXAS
inverse-temperature Stan models — `reduce_sum` and `ll_chunk` — using a small toy
example you can trace by hand.

---

## Background in one sentence

When we reconstruct past temperatures from Ring Index (RI) values, the Stan model must
evaluate — for every proposed temperature — how well it fits the data under every one of
the M calibration curves drawn from the forward posterior. For large N (many downcore
samples) and large M (many calibration draws), this gets expensive fast. `reduce_sum`
and `ll_chunk` are how we split that work across CPU cores.

---

## 1. The Problem: N × M evaluations per sampling step

Suppose you have:
- **N = 100** downcore sediment samples (each with a measured RI value)
- **M = 200** plausible calibration curves drawn from the forward posterior

For every step the sampler takes, it must evaluate the likelihood:

```
For each sample n (1 to 100):
    For each calibration draw m (1 to 200):
        Compute: expected RI = f(T_n ; curve_m)
        Ask:     how likely is the observed RI given this expected RI?
    Average the M likelihoods for sample n

Total evaluations per step: 100 × 200 = 20,000
Total evaluations (4 chains × 1,500 steps): 120,000,000
```

That's a lot of repeated computation. If your computer has 8 CPU cores, why not use
all of them at the same time?

---

## 2. The Solution: Split N samples across CPU cores

`reduce_sum` divides the N samples into **chunks** and assigns each chunk to a
separate CPU core. All cores work simultaneously; their results are summed at the end.

```
                      N = 8 samples to process
                      ┌───┬───┬───┬───┬───┬───┬───┬───┐
Observations (n):     │ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │ 7 │ 8 │
                      └───┴───┴───┴───┴───┴───┴───┴───┘
                            │               │
           ┌────────────────┤               ├────────────────┐
           ▼                ▼               ▼                ▼
      ┌─────────┐      ┌─────────┐    ┌─────────┐      ┌─────────┐
      │ Core 1  │      │ Core 2  │    │ Core 3  │      │ Core 4  │
      │ n=1,2   │      │ n=3,4   │    │ n=5,6   │      │ n=7,8   │
      │         │      │         │    │         │      │         │
      │ll_chunk │      │ll_chunk │    │ll_chunk │      │ll_chunk │
      │(1 → 2)  │      │(3 → 4)  │    │(5 → 6)  │      │(7 → 8)  │
      └────┬────┘      └────┬────┘    └────┬────┘      └────┬────┘
           │                │              │                 │
           └────────────────┴──────────────┴─────────────────┘
                                     │
                                     ▼
                         lp_1 + lp_2 + lp_3 + lp_4
                         = total log-probability
```

The `grainsize` parameter controls the chunk size. `grainsize = 1` makes the
smallest possible chunks (maximum parallelism); larger values reduce overhead.

---

## 3. What `ll_chunk` does inside each core

`ll_chunk` is the function that processes one chunk of samples. For each sample `n`
in the chunk, it:

1. Applies the **prior** on temperature: "how plausible is this T given our prior knowledge?"
2. Loops over all **M calibration draws** and computes how well each curve predicts the observed RI
3. **Averages** those M likelihoods (the log-sum-exp step)
4. Adds the result to the chunk's running total

Here is the flow for a single sample inside `ll_chunk`:

```
For sample n=2 (RI_obs = 0.68, T_proposed = 22.5°C):

   ┌──────────────────────────────────────────────────────────┐
   │  Step 1 – Prior                                          │
   │  Is T = 22.5°C consistent with our prior guess?         │
   │  prior_mu_t[2] = 20°C, prior_sigma_t = 10°C             │
   │  → log N(22.5 | 20, 10) = −2.33                         │
   └──────────────────────────────────────────────────────────┘

   ┌──────────────────────────────────────────────────────────┐
   │  Step 2 – Likelihood under each calibration draw         │
   │                                                          │
   │  Draw m=1: T₀=28, k=0.18, b=0.15, Q=1.2, ν=0.9, σ=0.05 │
   │    → expected RI = 0.65   → log N(0.68 | 0.65, 0.05)   │
   │    → lp[1] = −1.58                                       │
   │                                                          │
   │  Draw m=2: T₀=27, k=0.20, b=0.12, Q=1.0, ν=1.1, σ=0.06 │
   │    → expected RI = 0.67   → log N(0.68 | 0.67, 0.06)   │
   │    → lp[2] = −1.39                                       │
   │                                                          │
   │  Draw m=3: T₀=30, k=0.15, b=0.18, Q=0.9, ν=0.8, σ=0.04 │
   │    → expected RI = 0.60   → log N(0.68 | 0.60, 0.04)   │
   │    → lp[3] = −3.13                                       │
   └──────────────────────────────────────────────────────────┘

   ┌──────────────────────────────────────────────────────────┐
   │  Step 3 – Average over M draws (log-sum-exp trick)       │
   │                                                          │
   │  We want:  log[ (1/3) × (e^lp[1] + e^lp[2] + e^lp[3]) ]│
   │          = log_sum_exp(lp) − log(3)                      │
   │          = log_sum_exp(−1.58, −1.39, −3.13) − 1.10      │
   │          ≈ −1.23                                         │
   │                                                          │
   │  This is the marginalized likelihood for sample n=2.     │
   └──────────────────────────────────────────────────────────┘

   Contribution of sample n=2 to log-probability:
       prior + likelihood = −2.33 + (−1.23) = −3.56
```

---

## 4. Why the same draw index `m` matters

Each calibration draw `m` represents **one self-consistent set of curve parameters**
sampled together from the forward posterior. Think of it like a single geochemist's
"best guess" for the entire calibration curve — all parameters in that guess were
estimated together and are correlated.

```
           Forward calibration posterior: 3 draws
           ─────────────────────────────────────
           Draw │  T₀   │  k   │  b   │  σ
           ─────┼───────┼──────┼──────┼──────
             1  │ 28.0  │ 0.18 │ 0.15 │ 0.05   ← always use ALL from row 1
             2  │ 27.0  │ 0.20 │ 0.12 │ 0.06   ← always use ALL from row 2
             3  │ 30.0  │ 0.15 │ 0.18 │ 0.04   ← always use ALL from row 3
```

**What we do (correct ✅):**
For draw m=1, use `T₀[1]=28.0`, `k[1]=0.18`, `b[1]=0.15`, `σ[1]=0.05` together.

**What we must NOT do (wrong ❌):**
Mix parameters from different rows — e.g., `T₀[1]` + `k[3]` + `b[2]`.
This would break the correlations among parameters and overestimate uncertainty.

In the Stan code, this constraint is enforced because every parameter uses the
same index `[m]` inside the inner loop:

```stan
for (m in 1:M) {
    real mu = b[m] + (1 - b[m])
        / pow(1 + Q[m] * exp(-k[m] * (t_est[n] - t0[m])), 1.0 / v[m]);
    //   ^^^          ^^^          ^^^               ^^^         ^^^
    //   same m      same m       same m            same m     same m
}
```

---

## 5. The log-sum-exp trick explained

When averaging probabilities across M calibration draws, we work in **log-space** to
avoid numerical underflow (very small probabilities becoming exactly zero in a computer).

**The naive (unstable) way:**
```
average_likelihood = (1/M) × (exp(lp[1]) + exp(lp[2]) + exp(lp[3]))
```
If lp values are very negative (e.g., −300), `exp(−300) = 0` in floating-point — lost!

**The log-sum-exp way (stable):**
```
log_average_likelihood = log_sum_exp(lp[1], lp[2], lp[3]) − log(M)
```
Stan's `log_sum_exp` shifts all values by the maximum before exponentiating, keeping
numbers in a safe range. The result is mathematically identical but numerically stable.

Visually:
```
lp = [−1.58, −1.39, −3.13]
                   │
                   ▼
     shift by max = −1.39:  [−0.19, 0.00, −1.74]
                   │
                   ▼
     exp:  [0.83, 1.00, 0.18]   ← safe numbers, no underflow
                   │
                   ▼
     sum:  2.01   →  log(2.01) = 0.70
                   │
                   ▼
     shift back:  0.70 + (−1.39) − log(3) = −1.79
```

---

## 6. Putting it all together: the full picture

```
                     TEXAS Inverse-T Model (marginal + reduce_sum)

  INPUT: N=4 RI observations, M=3 calibration draws, 4 CPU cores

  Forward posterior (M=3 draws):
  ┌──────────────────────────────────────────────────────────┐
  │  m=1: T₀=28  k=0.18  b=0.15  Q=1.2  ν=0.9  σ=0.05     │
  │  m=2: T₀=27  k=0.20  b=0.12  Q=1.0  ν=1.1  σ=0.06     │
  │  m=3: T₀=30  k=0.15  b=0.18  Q=0.9  ν=0.8  σ=0.04     │
  └──────────────────────────────────────────────────────────┘

  Downcore samples:   n=1      n=2      n=3      n=4
  RI_obs:            0.72     0.68     0.55     0.41
  prior_mu_t:         25       20       15       10

                       ↓ reduce_sum splits across cores ↓

  ┌──────────────────────┐    ┌──────────────────────┐
  │  Core A: n=1, n=2    │    │  Core B: n=3, n=4    │
  │                      │    │                      │
  │  For n=1:            │    │  For n=3:            │
  │    prior(T_1)        │    │    prior(T_3)        │
  │    lp[1,2,3]         │    │    lp[1,2,3]         │
  │    log_sum_exp − logM│    │    log_sum_exp − logM│
  │                      │    │                      │
  │  For n=2:            │    │  For n=4:            │
  │    prior(T_2)        │    │    prior(T_4)        │
  │    lp[1,2,3]         │    │    lp[1,2,3]         │
  │    log_sum_exp − logM│    │    log_sum_exp − logM│
  │                      │    │                      │
  │  return lp_A         │    │  return lp_B         │
  └──────────┬───────────┘    └──────────┬───────────┘
             │                           │
             └────────────┬──────────────┘
                          ▼
               target += lp_A + lp_B
               (total log-posterior for this proposed T vector)
```

Stan's HMC sampler repeats this for thousands of proposed temperature vectors until
it has drawn enough samples from the posterior distribution of temperatures.

---

## 7. Summary table

| Concept | What it means in plain language |
|---|---|
| `ll_chunk` | A function that computes the "score" (log-probability) for one batch of sediment samples |
| `reduce_sum` | Runs `ll_chunk` on multiple batches simultaneously using different CPU cores |
| `grainsize` | How many samples go into each batch (1 = smallest, N = no parallelism) |
| `log_sum_exp` | A numerically safe way to average M likelihoods in log-space |
| Same index `[m]` | Ensures all calibration parameters in each draw came from the same original MCMC sample, preserving their correlations |
| `segment(v, start, n)` | Extracts the portion of vector `v` from position `start` with length `n` — used to give each core its own slice of data |

---

## 8. When does parallelism help?

`reduce_sum` only speeds things up when compiled with `STAN_THREADS=True` and
`threads_per_chain > 1`. Otherwise it runs sequentially (same result, no speedup).

Rule of thumb: parallelism helps most when N is large (hundreds of samples) and
the calibration integral (M loop) is expensive. For small reconstructions (N < 20),
the overhead of parallelism may outweigh the benefit.

---

*See also: `marginalization_explainer.md` (why marginal > ensemble) and
`stan_reduce_sum_notes.md` (technical implementation notes).*
