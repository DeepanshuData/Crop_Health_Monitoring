"""Shared Sentinel-2 masking and vegetation-index calculations."""

from __future__ import annotations

import ee


def mask_sentinel2_clouds(image):
    """Keep SCL classes 2, 4, 5 and 6; mask invalid, cloud and snow classes."""
    scl = image.select("SCL")
    clear = scl.eq(2).Or(scl.eq(4)).Or(scl.eq(5)).Or(scl.eq(6))
    return image.updateMask(clear)


def calculate_ndvi(image):
    """Calculate NDVI from Sentinel-2 NIR (B8) and red (B4)."""
    return image.normalizedDifference(["B8", "B4"]).rename("NDVI")


def calculate_ndre(image):
    """Calculate NDRE from Sentinel-2 NIR (B8) and red-edge (B5)."""
    return image.normalizedDifference(["B8", "B5"]).rename("NDRE")


def calculate_ndwi(image):
    """Calculate green-NIR NDWI from Sentinel-2 B3 and B8."""
    return image.normalizedDifference(["B3", "B8"]).rename("NDWI")


def calculate_indices(image):
    """Return all three indices from one consistently cloud-masked image."""
    masked = mask_sentinel2_clouds(image)
    return masked.addBands(
        [calculate_ndvi(masked), calculate_ndre(masked), calculate_ndwi(masked)]
    )


def calculate_index_mean(index_image, geometry, scale=10):
    """Calculate regional mean and valid-pixel count for an index."""
    return index_image.reduceRegion(
        reducer=ee.Reducer.mean().combine(
            reducer2=ee.Reducer.count(), sharedInputs=True
        ),
        geometry=geometry,
        scale=scale,
        maxPixels=1e10,
        tileScale=4,
    )


def common_valid_change(first, second):
    """Return first/second images masked to their common valid pixels and change."""
    common = first.mask().reduce(ee.Reducer.min()).And(
        second.mask().reduce(ee.Reducer.min())
    )
    first_common = first.updateMask(common)
    second_common = second.updateMask(common)
    change = second_common.subtract(first_common).rename("NDVI_Change")
    return first_common, second_common, change, common
