"""NDVI comparisons that restrict change to common valid observations."""

import ee

from gee.config import ANALYSIS_SCALE_METERS
from gee.sentinel2_fetcher import select_best_image
from gee.sentinel2_processor import calculate_ndvi, common_valid_change


def _regional_statistics(image, geometry, scale):
    reducer = ee.Reducer.mean().combine(
        reducer2=ee.Reducer.minMax(), sharedInputs=True
    ).combine(
        reducer2=ee.Reducer.count(), sharedInputs=True
    )
    return image.reduceRegion(
        reducer=reducer,
        geometry=geometry,
        scale=scale,
        maxPixels=1e10,
        tileScale=4,
    ).getInfo() or {}


def compare_ndvi_dates(
    first_date,
    second_date,
    region,
    search_days=7,
    scale=ANALYSIS_SCALE_METERS,
):
    """Return date-specific NDVI, common-pixel change, and valid-area metrics."""
    if first_date == second_date:
        raise ValueError("Choose two different target dates.")
    first_image, first_metadata = select_best_image(
        first_date, region, search_days=search_days, scale=scale
    )
    second_image, second_metadata = select_best_image(
        second_date, region, search_days=search_days, scale=scale
    )
    first_ndvi = calculate_ndvi(first_image)
    second_ndvi = calculate_ndvi(second_image)
    _, _, change, common_mask = common_valid_change(
        first_ndvi, second_ndvi
    )
    valid_area = (
        ee.Image.pixelArea()
        .updateMask(common_mask)
        .reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=region,
            scale=scale,
            maxPixels=1e10,
            tileScale=4,
        )
        .get("area")
    )
    district_area = region.area(maxError=1).getInfo()
    common_area_m2 = ee.Number(ee.Algorithms.If(valid_area, valid_area, 0)).getInfo()
    statistics = {
        "first_date": _regional_statistics(first_ndvi, region, scale),
        "second_date": _regional_statistics(second_ndvi, region, scale),
        "change_common_pixels": _regional_statistics(change, region, scale),
    }
    metrics = {
        "first_valid_pixels": int(
            statistics["first_date"].get("NDVI_count") or 0
        ),
        "second_valid_pixels": int(
            statistics["second_date"].get("NDVI_count") or 0
        ),
        "common_valid_pixels": int(
            statistics["change_common_pixels"].get("NDVI_Change_count") or 0
        ),
        "common_valid_area_m2": common_area_m2,
        "district_area_m2": district_area,
        "common_valid_area_percent": (
            100 * common_area_m2 / district_area if district_area else 0
        ),
    }
    return {
        "first_ndvi": first_ndvi,
        "second_ndvi": second_ndvi,
        "change": change,
        "first_image": first_image,
        "second_image": second_image,
        "first_metadata": first_metadata,
        "second_metadata": second_metadata,
        "metrics": metrics,
        "statistics": statistics,
    }
