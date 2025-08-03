import numpy as np

def logistic(x, x0=None, t0=None, L=None, k=None, b=None):
    """Four-parameter logistic function."""
    x0 = x0 if x0 is not None else t0
    if None in (x0, L, k, b):
        raise ValueError("Missing required parameters: x0/t0, L, k, b")
    return L / (1 + np.exp(-k * (x - x0))) + b


def logistic_fixed_upper(x, x0=None, t0=None, k=None, b=None):
    """Three-parameter logistic with upper asymptote 1."""
    x0 = x0 if x0 is not None else t0
    if None in (x0, k, b):
        raise ValueError("Missing required parameters: x0/t0, k, b")
    return (1 - b) / (1 + np.exp(-k * (x - x0))) + b


def inverse_logistic_fixed_upper(y, x0=None, t0=None, k=None, b=None):
    """Inverse of three-parameter logistic with upper asymptote 1."""
    x0 = x0 if x0 is not None else t0
    if None in (x0, k, b):
        raise ValueError("Missing required parameters: x0/t0, k, b")
    return x0 + np.log((1 - b)/y - 1) / -k


def generalized_logistic(x, x0=None, t0=None, a=None, b=None, k=None, v=None, Q=None):
    """Generalized logistic function."""
    x0 = x0 if x0 is not None else t0
    if None in (x0, a, b, k, v, Q):
        raise ValueError("Missing required parameters.")
    return b + ((a - b) / np.power(1 + Q * np.exp(-k * (x - x0)), 1/v))


def generalized_logistic_fixed_upper(x, x0=None, t0=None, b=None, k=None, v=None, Q=None):
    """Generalized logistic with upper asymptote = 1."""
    x0 = x0 if x0 is not None else t0
    if None in (x0, b, k, v, Q):
        raise ValueError("Missing required parameters.")
    return b + ((1 - b) / np.power(1 + Q * np.exp(-k * (x - x0)), 1/v))
