"""Small NumPy helpers for validating raster date comparisons."""

import numpy as np


def common_valid_change(first, second, first_valid=None, second_valid=None):
    """Calculate second-minus-first only where both rasters have valid data."""
    first = np.asarray(first)
    second = np.asarray(second)
    if first.shape != second.shape:
        raise ValueError("Date-comparison rasters must have identical dimensions.")
    valid_first = np.isfinite(first)
    valid_second = np.isfinite(second)
    if first_valid is not None:
        valid_first &= np.asarray(first_valid, dtype=bool)
    if second_valid is not None:
        valid_second &= np.asarray(second_valid, dtype=bool)
    common = valid_first & valid_second
    first_result = np.full(first.shape, np.nan, dtype=np.float64)
    second_result = np.full(second.shape, np.nan, dtype=np.float64)
    change = np.full(first.shape, np.nan, dtype=np.float64)
    first_result[common] = first[common]
    second_result[common] = second[common]
    change[common] = second[common] - first[common]
    return first_result, second_result, change, common
