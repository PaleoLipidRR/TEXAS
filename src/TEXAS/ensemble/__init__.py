# TEXAS/ensemble/__init__.py

from .generator import generate_ensemble, generate_ensemble_auto
from .detection import detect_model_and_params

__all__ = [
    "generate_ensemble",
    "generate_ensemble_auto",
    "detect_model_and_params",
]
