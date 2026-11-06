# TEXAS/models/logistics.py
"""
Plain-Python logistic curves used to evaluate and plot TEXAS calibrations.

In every function the forward direction is temperature ``x`` (°C) in, proxy
value ``y`` (e.g. Scaled RI) out; the ``inverse_*`` functions go the other
way, for a single parameter set. ``x0`` is accepted everywhere as a legacy
alias for ``t0``.
"""

import numpy as np

def logistic(x, t0=None, x0=None, L=None, k=None, b=None):
    """
    Four-parameter logistic function: ``y = L / (1 + exp(-k*(x - t0))) + b``.

    Parameters
    ----------
    x : array-like
        Input (temperature, etc.).
    t0, x0 : float
        Inflection point (prefer t0; x0 allowed for legacy).
    L : float
        Amplitude: the curve rises from ``b`` to an upper asymptote of ``b + L``.
    k : float
        Steepness (growth rate).
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
    Three-parameter logistic with upper asymptote 1:
    ``y = b + (1 - b) / (1 + exp(-k*(x - t0)))``.

    Parameters
    ----------
    x : array-like
        Temperature (°C).
    t0, x0 : float
        Inflection point (prefer t0; x0 allowed for legacy).
    k : float
        Steepness (growth rate).
    b : float
        Lower asymptote.

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
    Inverse of three-parameter logistic with upper asymptote 1 (proxy → temperature).

    Parameters
    ----------
    y : array-like
        Proxy values.
    t0, x0 : float
        Inflection point (prefer t0; x0 allowed for legacy).
    k : float
        Steepness (growth rate).
    b : float
        Lower asymptote.

    Returns
    -------
    x : np.ndarray
        Temperature (°C).
    """
    inflection = t0 if t0 is not None else x0
    if inflection is None or k is None or b is None:
        raise ValueError("Missing required parameters: t0 (or x0), k, b")
    y = np.asarray(y).squeeze()
    return inflection + np.log((1 - b) / (y - b) - 1) / -k


def generalized_logistic_fixed_upper(
    x: np.ndarray,
    t0: float = None,
    x0: float = None,
    b: float = None,
    k: float = None,
    v: float = None,
) -> np.ndarray:
    """
    4-parameter generalized logistic with upper asymptote fixed at 1 and Q=1
    (paper Eq. 9 with a = 1, Q = C = 1)::

        y = b + (1 - b) / (1 + exp(-k*(x - t0)))^(1/v)

    ``t0`` is the curve's location, not its inflection point unless v = 1:
    the steepest response is at ``t0 - ln(v)/k``. v defaults to 1.0 if not
    provided.
    """
    inflection = t0 if t0 is not None else x0
    if inflection is None or b is None or k is None:
        raise ValueError("Missing required parameters: t0 (or x0), b, k")

    v_val = v if v is not None else 1.0

    x = np.asarray(x).squeeze()
    return b + (1 - b) / ((1 + np.exp(-k * (x - inflection))) ** (1 / v_val))


def inverse_generalized_logistic_fixed_upper(
    y: np.ndarray,
    t0: float = None,
    x0: float = None,
    b: float = None,
    k: float = None,
    v: float = None,
) -> np.ndarray:
    """
    Inverse of generalized_logistic_fixed_upper: given proxy y, return temperature x::

        x = t0 - ln(((1-b)/(y-b))^v - 1) / k

    Defined only for b < y < 1. v defaults to 1.0 if not provided.
    """
    inflection = t0 if t0 is not None else x0
    if inflection is None or b is None or k is None:
        raise ValueError("Missing required parameters: t0 (or x0), b, k")

    v_val = v if v is not None else 1.0

    y = np.asarray(y).squeeze()
    return inflection - np.log(((1 - b) / (y - b)) ** v_val - 1) / k


