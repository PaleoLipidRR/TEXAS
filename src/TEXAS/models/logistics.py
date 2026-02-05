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


def generalized_logistic(
    x: np.ndarray, 
    t0: float = None, 
    x0: float = None, 
    a: float = None, 
    b: float = None, 
    k: float = None, 
    v: float = None, 
    Q: float = None
):
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


def generalized_logistic_fixed_upper(
    x: np.ndarray,
    t0: float = None,
    x0: float = None,
    b: float = None,
    k: float = None,
    v: float = None,
    Q: float = None
) -> np.ndarray:
    """
    5-parameter generalized logistic with upper asymptote fixed at 1.
    y = b + (1 - b) / (1 + Q*exp(-k*(x - inflection)))^(1/v)
    
    If v or Q are None, they default to 1.0.
    """
    inflection = t0 if t0 is not None else x0
    
    # Check required parameters
    if inflection is None or b is None or k is None:
        raise ValueError("Missing required parameters: t0 (or x0), b, k")
    
    # Default v and Q to 1.0 if not provided (allows fixing them)
    v_val = v if v is not None else 1.0
    Q_val = Q if Q is not None else 1.0
    
    x = np.asarray(x).squeeze()
    exponent = -k * (x - inflection)
    denominator = 1 + Q_val * np.exp(exponent)
    return b + (1 - b) / (denominator ** (1 / v_val))
