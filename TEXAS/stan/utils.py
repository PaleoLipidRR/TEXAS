# stan/utils.py
import os
import warnings
import re
from typing import Dict, Any
from TEXAS.constants import OPTIONAL_PREDICTORS

def check_tbb_env():
    if "TBB_CXX_TYPE" not in os.environ:
        warnings.warn(
            "TBB_CXX_TYPE not set. Stan model compilation may fail. "
            "Run `export TBB_CXX_TYPE=gcc` before launching."
        )

def infer_use_flags_from_attrs(attrs: Dict[str, Any]) -> Dict[str, bool]:
    """
    Infer which optional predictors (e.g. gdgt23ratio, no3) were used,
    based on dataset.attrs. Returns a dict like:
    {'gdgt23ratio': True, 'no3': False}
    """
    return {
        key: bool(attrs.get(f"use_{key}", 0))
        for key in OPTIONAL_PREDICTORS
    }


def infer_optional_predictor_usage(data: dict) -> dict:
    """
    Inspect keys in a Stan data dict and infer which optional predictors
    are present AND actively used (e.g., gdgt23ratio, no3). 
    Returns a dict of use_* flags.
    """
    flags = {}
    # Only set flags to True if the use_* key exists and is truthy
    for pred in OPTIONAL_PREDICTORS:
        use_key = f"use_{pred}"
        if use_key in data and data[use_key]:
            flags[use_key] = True
        else:
            flags[use_key] = False
    return flags