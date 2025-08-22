# TEXAS/plotting/range_utils.py

import numpy as np
import scipy.stats as stats
from typing import Sequence, Optional, List, Tuple

def compute_sample_range(samples: Sequence[float]) -> Tuple[Optional[float], Optional[float]]:
    if len(samples) == 0:
        return None, None
    p1, p99 = np.percentile(samples, [1, 99])
    span = p99 - p1
    return p1 - 0.2 * span, p99 + 0.2 * span

def compute_density_based_range(
    samples: Sequence[float],
    kde_bw: float = 0.3,
    density_threshold: float = 0.01
) -> Tuple[Optional[float], Optional[float]]:
    if len(samples) == 0:
        return None, None
    p1, p99 = np.percentile(samples, [1, 99])
    xs = np.linspace(p1, p99, 1000)
    kde = stats.gaussian_kde(samples, bw_method=kde_bw)
    dens = kde(xs)
    mask = dens > (density_threshold * dens.max())
    if not mask.any():
        return compute_sample_range(samples)
    lo, hi = xs[mask][[0, -1]]
    pad = 0.1 * (hi - lo)
    return lo - pad, hi + pad

def compute_suffix_specific_range(
    all_samples: List[Tuple[np.ndarray,int,str,str,int,int]],
    target_suffix: str
) -> Tuple[Optional[float], Optional[float]]:
    suffix_samples = [
        samp for samp, ds_i, label, mdl, use_gdgt, use_no3 in all_samples
        if target_suffix in label
    ]
    if not suffix_samples:
        return None, None
    combined = np.concatenate(suffix_samples)
    if combined.size == 0:
        return None, None
    p5, p95 = np.percentile(combined, [5, 95])
    pad = 0.05 * (p95 - p5)
    return p5 - pad, p95 + pad

def compute_dataset_specific_range(
    all_samples: List[Tuple[np.ndarray,int,str,str,int,int]],
    target_dataset_idx: int
) -> Tuple[Optional[float], Optional[float]]:
    ds_samples = [
        samp for samp, ds_i, label, mdl, use_gdgt, use_no3 in all_samples
        if ds_i == target_dataset_idx
    ]
    if not ds_samples:
        return None, None
    combined = np.concatenate(ds_samples)
    if combined.size == 0:
        return None, None
    p1, p99 = np.percentile(combined, [1, 99])
    pad = 0.05 * (p99 - p1)
    return p1 - pad, p99 + pad
