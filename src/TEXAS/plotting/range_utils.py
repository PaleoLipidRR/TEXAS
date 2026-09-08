# TEXAS/plotting/range_utils.py

import numpy as np
from typing import Sequence, Optional, List, Tuple

def compute_sample_range(samples: Sequence[float]) -> Tuple[Optional[float], Optional[float]]:
    """Compute a padded plotting range covering the central 98% of a sample.

    Args:
        samples: Posterior draws, or any 1-D numeric sequence.

    Returns:
        ``(lo, hi)``: the 1st and 99th percentiles, each pushed outward by 20%
        of the span between them, so a density curve is not clipped at the axis
        edge. ``(None, None)`` when *samples* is empty.
    """
    if len(samples) == 0:
        return None, None
    p1, p99 = np.percentile(samples, [1, 99])
    span = p99 - p1
    return p1 - 0.2 * span, p99 + 0.2 * span

def compute_suffix_specific_range(
    all_samples: List[Tuple[np.ndarray,int,str,str,int,int]],
    target_suffix: str
) -> Tuple[Optional[float], Optional[float]]:
    """Compute one padded range shared by every sample whose label carries a suffix.

    Puts all parameters estimated from one training set (``crtp``,
    ``culmesocore``, ``culmeso``, ``meso``, ``cul``) on a common axis, so the
    panels of a prior/posterior grid stay comparable across parameters.

    Args:
        all_samples: Tuples of ``(samples, dataset_index, label, model_name,
            use_gdgt23ratio, use_no3)``, as assembled by ``plotting.prior_plot``.
        target_suffix: Suffix to match; tested as ``target_suffix in label``,
            so ``"crtp"`` matches ``"t0_crtp"``.

    Returns:
        ``(lo, hi)``: the pooled 5th and 95th percentiles, padded by 5% of their
        span. ``(None, None)`` when nothing matches or the match is empty.
    """
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
    """Compute one padded range shared by every sample from one dataset.

    The dataset counterpart of :func:`compute_suffix_specific_range`: it pools
    by position in the caller's dataset list rather than by parameter suffix,
    which is what puts a whole column of a comparison grid on one axis.

    Args:
        all_samples: Tuples of ``(samples, dataset_index, label, model_name,
            use_gdgt23ratio, use_no3)``, as assembled by ``plotting.prior_plot``.
        target_dataset_idx: Index matched against each tuple's ``dataset_index``.

    Returns:
        ``(lo, hi)``: the pooled 1st and 99th percentiles, padded by 5% of their
        span. ``(None, None)`` when nothing matches or the match is empty.
    """
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
