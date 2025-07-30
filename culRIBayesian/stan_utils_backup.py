# ─── INVERSE TEMPERATURE ENSEMBLE FUNCTIONS ──────────────────────────────

def generate_invT_ensemble(
    posterior_ds,
    scaledRI_vals,
    percentiles=[5, 50, 95],
    return_full_ensemble=False,
    **kwargs
):
    """
    Generate temperature ensemble from inverse T model posteriors.
    
    This function works with inverse temperature models (invT_logistic_*) that
    estimate temperature values (t_est) from given scaledRI observations.
    
    Parameters
    ----------
    posterior_ds : xr.Dataset
        Posterior dataset from invT_logistic_* model
    scaledRI_vals : np.ndarray
        Scaled RI values corresponding to the t_est parameters
    percentiles : List[float], default [5, 50, 95]
        Percentiles to compute from ensemble
    return_full_ensemble : bool, default False
        If True, returns full t_est ensemble
        
    Returns
    -------
    Dict[str, np.ndarray]
        Dictionary containing:
        - 'p{percentile}': Temperature arrays for each percentile
        - 'ensemble': Full t_est ensemble (if requested)
        - 'scaledRI_vals': Input scaledRI values
        - 'metadata': Generation metadata
        
    Examples
    --------
    >>> # Generate temperature estimates from inverse model
    >>> scaledRI_obs = np.array([0.4, 0.5, 0.6, 0.7])
    >>> results = generate_invT_ensemble(
    ...     posterior_ds=invT_posterior,
    ...     scaledRI_vals=scaledRI_obs
    ... )
    >>> temp_median = results['p50']
    >>> temp_lower = results['p5']
    >>> temp_upper = results['p95']
    """
    import numpy as np
    
    # Extract t_est from posterior
    if 't_est' not in posterior_ds.data_vars:
        raise ValueError("Posterior dataset must contain 't_est' variable")
    
    t_est_data = posterior_ds['t_est'].values  # Shape: (n_draws, n_observations)
    n_draws, n_obs = t_est_data.shape
    
    if len(scaledRI_vals) != n_obs:
        raise ValueError(f"Length mismatch: scaledRI_vals={len(scaledRI_vals)} vs t_est observations={n_obs}")
    
    # Compute percentiles
    results = {
        'scaledRI_vals': scaledRI_vals,
        'metadata': {
            'n_draws': n_draws,
            'n_observations': n_obs,
            'model_type': 'inverse_temperature',
            'stan_model_name': posterior_ds.attrs.get('stan_model_name', 'unknown'),
            'percentiles': percentiles,
            'return_full_ensemble': return_full_ensemble
        }
    }
    
    for percentile in percentiles:
        key = f'p{int(percentile)}'
        results[key] = np.percentile(t_est_data, percentile, axis=0)
    
    if return_full_ensemble:
        results['ensemble'] = t_est_data
    
    return results


def generate_invT_ensemble_auto(
    posterior_ds,
    scaledRI_vals,
    **kwargs
):
    """
    Auto-detect and generate inverse temperature ensemble.
    
    This function automatically detects inverse temperature models and
    generates temperature estimates from scaledRI observations.
    
    Parameters
    ----------
    posterior_ds : xr.Dataset
        Posterior dataset
    scaledRI_vals : np.ndarray
        Scaled RI values
    **kwargs
        Additional arguments passed to generate_invT_ensemble
        
    Returns
    -------
    Dict[str, np.ndarray]
        Results from generate_invT_ensemble
        
    Examples
    --------
    >>> # Auto-detect inverse model and generate ensemble
    >>> scaledRI_obs = np.array([0.4, 0.5, 0.6])
    >>> results = generate_invT_ensemble_auto(
    ...     posterior_ds=my_posterior,
    ...     scaledRI_vals=scaledRI_obs
    ... )
    >>> estimated_temps = results['p50']
    """
    # Check if this is an inverse T model
    model_name = posterior_ds.attrs.get('stan_model_name', '')
    
    if 'invT_' in model_name or 't_est' in posterior_ds.data_vars:
        print(f"🔬 Detected inverse temperature model: {model_name}")
        return generate_invT_ensemble(posterior_ds, scaledRI_vals, **kwargs)
    else:
        raise ValueError(f"Dataset does not appear to be from an inverse T model. Model: {model_name}")


def _detect_model_and_params(posterior_ds, suffix):
    """Helper function to detect model type and parameters."""
    available_vars = list(posterior_ds.data_vars)
    
    # Check for v and Q parameters
    has_v = f'v_{suffix}' in available_vars
    has_Q = f'Q_{suffix}' in available_vars
    
    # Check for multivariate parameters
    use_gdgt23ratio = posterior_ds.attrs.get('use_gdgt23ratio', 0) == 1
    use_no3 = posterior_ds.attrs.get('use_no3', 0) == 1
    
    # Import the model functions (assuming they're defined elsewhere)
    from . import (
        generalized_logistic_model_fixed_upper_multivariate,
        generalized_logistic_model_fixed_upper,
        simple_logistic_model_fixed_upper_multivariate,
        simple_logistic_model_fixed_upper
    )
    
    if has_v and has_Q:
        # Generalized logistic
        param_names = ['t0', 'k', 'b', 'v', 'Q']
        if use_gdgt23ratio or use_no3:
            model_function = generalized_logistic_model_fixed_upper_multivariate
            if use_gdgt23ratio:
                param_names.append('beta0_gdgt23ratio')
            if use_no3:
                param_names.append('beta0_no3')
        else:
            model_function = generalized_logistic_model_fixed_upper
    else:
        # Simple logistic
        param_names = ['t0', 'k', 'b']
        if use_gdgt23ratio or use_no3:
            model_function = simple_logistic_model_fixed_upper_multivariate
            if use_gdgt23ratio:
                param_names.append('beta0_gdgt23ratio')
            if use_no3:
                param_names.append('beta0_no3')
        else:
            model_function = simple_logistic_model_fixed_upper
    
    return {
        'model_function': model_function,
        'param_names': param_names,
        'has_v': has_v,
        'has_Q': has_Q,
        'use_gdgt23ratio': use_gdgt23ratio,
        'use_no3': use_no3
    }
