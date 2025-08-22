# TEXAS/models/logistics.py

import numpy as np

def logistic(x, t0=None, x0=None, L=None, k=None, b=None):
    """
    Four-parameter logistic function.

    Parameters
    ----------
    x : array-like
        Input (temperature, etc.).
    t0, x0 : float
        Inflection point (prefer t0; x0 allowed for legacy).
    L : float
        Upper asymptote.
    k : float
        Slope.
    b : float
        Lower asymptote.

    Returns
    -------
    y : np.ndarray
        Model output.
    """
    inflection = t0 if t0 is not None else x0
    if inflection is None or L is None or k is None or b is None:
        raise ValueError("Missing required parameters: t0 (or x0), L, k, b")
    x = np.asarray(x).squeeze()
    return L / (1 + np.exp(-k * (x - inflection))) + b


def logistic_fixed_upper(x, t0=None, x0=None, k=None, b=None):
    """
    Three-parameter logistic with upper asymptote 1.

    Parameters
    ----------
    x : array-like
    t0, x0 : float
    k : float
    b : float

    Returns
    -------
    y : np.ndarray
    """
    inflection = t0 if t0 is not None else x0
    if inflection is None or k is None or b is None:
        raise ValueError("Missing required parameters: t0 (or x0), k, b")
    x = np.asarray(x).squeeze()
    return (1 - b) / (1 + np.exp(-k * (x - inflection))) + b


def inverse_logistic_fixed_upper(y, t0=None, x0=None, k=None, b=None):
    """
    Inverse of three-parameter logistic with upper asymptote 1.

    Parameters
    ----------
    y : array-like
    t0, x0 : float
    k : float
    b : float

    Returns
    -------
    x : np.ndarray
    """
    inflection = t0 if t0 is not None else x0
    if inflection is None or k is None or b is None:
        raise ValueError("Missing required parameters: t0 (or x0), k, b")
    y = np.asarray(y).squeeze()
    return inflection + np.log((1 - b)/y - 1) / -k


def generalized_logistic(x, t0=None, x0=None, a=None, b=None, k=None, v=None, Q=None):
    """
    Generalized logistic function.

    Parameters
    ----------
    x : array-like
    t0, x0 : float
    a, b : float
        Upper/lower asymptotes.
    k, v, Q : float

    Returns
    -------
    y : np.ndarray
    """
    inflection = t0 if t0 is not None else x0
    if inflection is None or a is None or b is None or k is None or v is None or Q is None:
        raise ValueError("Missing required parameters: t0 (or x0), a, b, k, v, Q")
    x = np.asarray(x).squeeze()
    return b + ((a - b) / np.power(1 + Q * np.exp(-k * (x - inflection)), 1/v))


def generalized_logistic_fixed_upper(x, t0=None, x0=None, b=None, k=None, v=None, Q=None):
    """
    Generalized logistic with upper asymptote = 1.

    Parameters
    ----------
    x : array-like
    t0, x0 : float
    b : float
    k, v, Q : float

    Returns
    -------
    y : np.ndarray
    """
    inflection = t0 if t0 is not None else x0
    if inflection is None or b is None or k is None or v is None or Q is None:
        raise ValueError("Missing required parameters: t0 (or x0), b, k, v, Q")
    x = np.asarray(x).squeeze()
    return b + ((1 - b) / np.power(1 + Q * np.exp(-k * (x - inflection)), 1/v))
