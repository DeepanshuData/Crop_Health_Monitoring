"""NDVI date comparison using the common valid-pixel mask."""

from __future__ import annotations

from datetime import date

import ee

from gee.sentinel2_fetcher import select_best_image
from gee.sentinel2_processor import calculate_ndvi, common_valid_change


def compare_dates(
    geometry,
    first_date: date | str,
    second_date: date | str,
    search_days: int = 7,
    scale: int = 20,
) -> dict:
    if str(first_date) == str(second_date):
        raise ValueError("Select two different dates.")
    first_image, first_metadata = select_best_image(
        str(first_date), geometry, search_days=search_days, scale=scale
    )
    second_image, second_metadata = select_best_image(
        str(second_date), geometry, search_days=search_days, scale=scale
    )
    first_ndvi = calculate_ndvi(first_image)
    second_ndvi = calculate_ndvi(second_image)
    _, _, change, common_mask = common_valid_change(first_ndvi, second_ndvi)

    def stats(image):
        return image.reduceRegion(
            reducer=ee.Reducer.mean().combine(
                reducer2=ee.Reducer.count(), sharedInputs=True
            ),
            geometry=geometry,
            scale=scale,
            maxPixels=1e10,
            tileScale=4,
            bestEffort=True,
        ).getInfo()

    common_pixels = stats(change)
    pixel_count = int(
        common_pixels.get("NDVI_Change_count")
        or ee.Image.constant(1).updateMask(common_mask).reduceRegion(
            reducer=ee.Reducer.count(),
            geometry=geometry,
            scale=scale,
            maxPixels=1e10,
            tileScale=4,
            bestEffort=True,
        ).get("constant").getInfo()
        or 0
    )
    common_area = (
        ee.Image.pixelArea().updateMask(common_mask).reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=geometry,
            scale=scale,
            maxPixels=1e10,
            tileScale=4,
            bestEffort=True,
        ).get("area").getInfo()
    )
    common_area = float(common_area or 0)
    first_stats = stats(first_ndvi)
    second_stats = stats(second_ndvi)
    change_stats = stats(change)
    return {
        "first_ndvi": first_ndvi,
        "second_ndvi": second_ndvi,
        "change": change,
        "common_mask": common_mask,
        "first_metadata": first_metadata,
        "second_metadata": second_metadata,
        "first_mean": first_stats.get("NDVI_mean"),
        "second_mean": second_stats.get("NDVI_mean"),
        "mean_change": change_stats.get("NDVI_Change_mean"),
        "common_valid_pixels": pixel_count,
        "common_valid_area_ha": common_area / 10000,
    }
