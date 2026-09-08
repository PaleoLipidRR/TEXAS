"""Axis-range helpers for the prior/posterior plots.

These three are exported from the package top level, so they need docstrings
and they need to behave predictably on the two inputs that actually occur:
an empty sample, and a pooled set assembled by ``plotting.prior_plot``.
"""
import numpy as np
import pytest

from TEXAS.plotting.range_utils import (
    compute_dataset_specific_range,
    compute_sample_range,
    compute_suffix_specific_range,
)

ALL_FUNCS = [compute_sample_range, compute_suffix_specific_range,
             compute_dataset_specific_range]


@pytest.mark.parametrize("fn", ALL_FUNCS, ids=lambda f: f.__name__)
def test_has_a_real_docstring(fn):
    """Public API standard: >= 3 lines, and it says what it returns."""
    doc = (fn.__doc__ or "").strip()
    assert len(doc.splitlines()) >= 3, f"{fn.__name__} has no usable docstring"
    assert "Returns:" in doc, f"{fn.__name__} does not document its return value"


def test_sample_range_pads_outward():
    """The 1-99 span is widened by 20% on each side, so tails are not clipped."""
    samples = np.linspace(0.0, 100.0, 1001)
    lo, hi = compute_sample_range(samples)
    p1, p99 = np.percentile(samples, [1, 99])
    assert lo < p1 and hi > p99
    assert lo == pytest.approx(p1 - 0.2 * (p99 - p1))
    assert hi == pytest.approx(p99 + 0.2 * (p99 - p1))


def test_sample_range_of_empty_is_none():
    assert compute_sample_range([]) == (None, None)


def _entry(samples, ds_idx, label):
    """One row of the (samples, dataset_index, label, model, use_g23, use_no3) tuple."""
    return (np.asarray(samples), ds_idx, label, "gen_logi_fixed", 0, 0)


def test_suffix_range_pools_only_matching_labels():
    """A suffix that appears in one label must not pull in the other dataset."""
    entries = [_entry(np.zeros(100), 0, "t0_crtp"),
               _entry(np.full(100, 50.0), 1, "t0_culmeso")]
    lo, hi = compute_suffix_specific_range(entries, "crtp")
    assert hi < 25.0, "the culmeso samples leaked into the crtp range"


def test_suffix_range_with_no_match_is_none():
    entries = [_entry(np.zeros(10), 0, "t0_crtp")]
    assert compute_suffix_specific_range(entries, "meso") == (None, None)


def test_dataset_range_pools_by_index_not_label():
    """Same labels, different dataset index -- the index is what selects."""
    entries = [_entry(np.zeros(100), 0, "t0_crtp"),
               _entry(np.full(100, 50.0), 1, "t0_crtp")]
    lo, hi = compute_dataset_specific_range(entries, 1)
    assert lo > 25.0, "dataset 0 leaked into dataset 1's range"


def test_dataset_range_with_no_match_is_none():
    entries = [_entry(np.zeros(10), 0, "t0_crtp")]
    assert compute_dataset_specific_range(entries, 7) == (None, None)
