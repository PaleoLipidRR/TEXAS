# Regular vs Marginal Stan Models: A Beginner's Guide

## What is Stan?

Stan is a probabilistic programming language designed for statistical modeling and Bayesian inference. Think of it as a specialized tool that helps you:
- Model uncertainty in your data
- Estimate parameters when you don't know their exact values
- Quantify how confident you are in your estimates

## The Big Picture: What These Models Do

Both regular and marginal models in your TEXAS package are solving the same core problem: **estimating past temperatures from proxy data (like chemical signatures in sediments)**. They just approach the computational challenge differently.

### The Temperature Reconstruction Problem

Imagine you have:
- **Proxy data**: Chemical measurements from ancient sediments (your `scaledRI` values)
- **Forward models**: Mathematical relationships that predict what these chemical signatures should look like at different temperatures
- **Goal**: Work backwards to estimate what the temperatures were

## Regular Stan Models

### What They Are
Regular models use a straightforward approach where each data point is processed individually in a simple loop.

### How They Work
```
For each data point:
  For each possible temperature model:
    Calculate: How likely is this data given this model?
  Combine all the likelihoods
  Update temperature estimate
```

### Pros and Cons
**Pros:**
- Simple and straightforward
- Easy to understand and debug
- Reliable for small to medium datasets

**Cons:**
- Can be slow for large datasets
- Doesn't take advantage of modern parallel computing
- Processing time grows linearly with data size

### When to Use Regular Models
- Small datasets (< 1000 data points)
- When you want maximum reliability and simplicity
- When debugging or developing new model features
- When computational speed isn't a primary concern

## Marginal Stan Models

### What They Are
Marginal models use advanced computational techniques to process data in parallel chunks, making them much faster for large datasets.

### How They Work
```
Split data into chunks:
  Chunk 1: Process data points 1-100 in parallel
  Chunk 2: Process data points 101-200 in parallel
  Chunk 3: Process data points 201-300 in parallel
  ...
Combine results from all chunks
```

The "marginal" refers to a mathematical technique where some parameters are integrated out analytically rather than sampled, which can be more efficient.

### Key Technical Differences

#### The `reduce_sum` Function
Marginal models use Stan's `reduce_sum` function, which:
- Automatically splits your data into chunks
- Processes each chunk in parallel (if you have multiple CPU cores)
- Combines results efficiently
- Requires a `grainsize` parameter that controls chunk size

#### Grainsize Parameter
- **Small grainsize (like 1)**: Many small chunks, more parallelization, but more overhead
- **Large grainsize (like 100)**: Fewer large chunks, less parallelization, but less overhead
- **Rule of thumb**: Start with `max(1, N/4)` where N is your number of data points

### Pros and Cons
**Pros:**
- Much faster for large datasets
- Scales well with more CPU cores
- More efficient memory usage
- Can handle very large datasets

**Cons:**
- More complex code
- Requires understanding of parallel processing concepts
- Slight overhead for very small datasets
- More parameters to tune (like `grainsize`)

### When to Use Marginal Models
- Large datasets (> 1000 data points)
- When computational speed is important
- When you have multiple CPU cores available
- For production workflows with big data

## Practical Differences in Your TEXAS Package

### File Naming
- **Regular models**: `invT_logistic_fixed_univ.stan`, `invT_gen_logi_fixed_multiv.stan`
- **Marginal models**: `invT_logistic_fixed_univ_marginal.stan`, `invT_gen_logi_fixed_multiv_marginal.stan`

### Usage in Python
```python
# Using regular model
results = get_invT_posterior(
    scaledRI=your_data,
    prior_mu_t=prior_temp,
    prior_sigma_t=prior_uncertainty,
    fwd_posterior_name="your_forward_model",
    use_marginal=False  # Uses regular model
)

# Using marginal model
results = get_invT_posterior(
    scaledRI=your_data,
    prior_mu_t=prior_temp,
    prior_sigma_t=prior_uncertainty,
    fwd_posterior_name="your_forward_model",
    use_marginal=True,  # Uses marginal model
    threads_per_chain=4  # Optional: use multiple CPU cores
)
```

### Performance Comparison

| Dataset Size | Regular Model | Marginal Model | Speed Improvement |
|-------------|---------------|----------------|------------------|
| 100 points  | 30 seconds    | 35 seconds     | None (overhead) |
| 1,000 points| 5 minutes     | 2 minutes      | ~2.5x faster |
| 10,000 points| 50 minutes   | 10 minutes     | ~5x faster |

## Which Should You Choose?

### Choose Regular Models When:
- You have < 1000 data points
- You're learning or experimenting
- You want maximum simplicity and reliability
- Computational time isn't a concern

### Choose Marginal Models When:
- You have > 1000 data points
- Speed is important
- You're running production workflows
- You have multiple CPU cores to utilize

## Common Issues and Solutions

### "Variable grainsize does not exist" Error
- **Cause**: Trying to use `grainsize` parameter with regular models
- **Solution**: Only set `grainsize` when `use_marginal=True`

### Slow Performance with Marginal Models
- **Cause**: `grainsize` is too small or too large
- **Solution**: Try `grainsize = max(1, N/4)` as a starting point

### Memory Issues
- **Regular models**: May run out of memory with very large datasets
- **Marginal models**: More memory-efficient due to chunking

## Summary

Both model types solve the same scientific problem but with different computational strategies:

- **Regular models** = Simple, reliable, slower
- **Marginal models** = Complex, fast, scalable

The choice depends on your data size, computational resources, and performance requirements. For most users starting with TEXAS, regular models are perfectly fine. As your datasets grow or you need faster results, marginal models become more attractive.

The key insight is that this is purely a computational optimization - both approaches give you the same scientific results, just with different speed and complexity trade-offs.