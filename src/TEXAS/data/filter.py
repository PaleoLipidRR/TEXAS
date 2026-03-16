from typing import Dict, Any
import numpy as np


def filter_stan_compatible(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a shallow copy of `data` containing only types compatible with Stan inputs.
    Allowed types: int, float, list, numpy.ndarray.
    """
    allowed_types = (int, float, list, np.ndarray)
    return {k: v for k, v in data.items() if isinstance(v, allowed_types)}


def ensure_numpy(x):
    """
    Ensure the input is a numpy.ndarray.
    Handles pandas Series, xarray DataArray (via .values), plain lists, and arrays.
    """
    if hasattr(x, 'values'):
        x = x.values
    if not isinstance(x, np.ndarray):
        x = np.asarray(x)
    return x
