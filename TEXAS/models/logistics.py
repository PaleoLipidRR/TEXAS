import numpy as np

def logistic(x, x0, L, k, b):
    """Four-parameter logistic function"""
    return L / (1 + np.exp(-k * (x - x0))) + b

def logistic_fixed_upper(x, x0, k, b):
    """Three-parameter logistic with upper asymptote 1"""
    return (1 - b) / (1 + np.exp(-k * (x - x0))) + b


def inverse_logistic_fixed_upper(y, x0, k, b):
    return x0 + np.log((1 - b)/y - 1) / -k

def generalized_logistic(x, x0, a, b, k, v, Q):
    """Generalized logistic function"""
    return b + ((a - b) / np.power(1 + Q * np.exp(-k * (x - x0)), 1/v))

def generalized_logistic_fixed_upper(x, x0, b, k, v, Q):
    return b + ((1 - b) / np.power(1 + Q * np.exp(-k * (x - x0)), 1/v))
